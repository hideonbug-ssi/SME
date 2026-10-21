"""
Overdue Invoice Reminder Agent (AIWSRT-7).

Loads seed data, detects overdue invoices, assigns stages, drafts reminders
via LiteLLM, enforces the 1/day rule, and creates pending actions for owner approval.
Today is fixed at 2026-07-14 for the PoC.
"""
import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional
import httpx

from config import settings
from services.approval_gateway import approval_gateway
from models.invoice import OverdueInvoice, OverdueInvoicesResponse

logger = logging.getLogger(__name__)

TODAY = date(2026, 7, 14)
SEED_FILE = Path(__file__).parent.parent / "mock_data" / "aiwsrt7_seed.json"

# In-memory log of sent/rejected reminders
_reminder_log: dict[str, str] = {}  # invoice_id → "sent" | "rejected"


def _assign_stage(days_overdue: int) -> tuple[int, str]:
    if days_overdue <= 30:
        return 1, "Stage 1 - Gentle"
    elif days_overdue <= 90:
        return 2, "Stage 2 - Firmer"
    else:
        return 3, "Final - Pre-Legal"


def _is_overdue(invoice: dict) -> bool:
    try:
        due = date.fromisoformat(invoice["due_date"])
        return TODAY > due and invoice.get("payment_status") in ("unpaid", "partial")
    except (KeyError, ValueError):
        return False


def _remaining_balance(invoice: dict) -> float:
    return invoice.get("amount_thb", 0.0) - invoice.get("amount_paid_thb", 0.0)


def _blocked_by_1day_rule(invoice: dict) -> bool:
    last_sent = invoice.get("last_reminder_sent")
    if not last_sent:
        return False
    try:
        return date.fromisoformat(last_sent) == TODAY
    except ValueError:
        return False


async def _draft_reminder_via_llm(invoice: dict, stage: int, stage_label: str, remaining: float) -> str:
    """Call LiteLLM to generate a stage-appropriate reminder draft."""
    tone_guidance = {
        1: "polite and friendly — assume the oversight was accidental",
        2: "firmer and more direct — note the overdue period and request prompt payment",
        3: "formal and pre-legal in tone — reference potential legal escalation if unpaid",
    }
    prompt = (
        f"Draft a concise payment reminder email for the following overdue invoice. "
        f"Tone: {tone_guidance[stage]}.\n\n"
        f"Invoice Number: {invoice.get('invoice_no')}\n"
        f"Customer: {invoice.get('counterparty_name')}\n"
        f"Remaining Balance Due: ฿{remaining:,.2f}\n"
        f"Days Overdue: {(TODAY - date.fromisoformat(invoice['due_date'])).days}\n"
        f"Stage: {stage_label}\n\n"
        f"Write only the email body (no subject line). Keep it under 150 words. "
        f"Reference the invoice number and remaining balance. "
        f"Do not make threats — only state facts and request payment."
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.litellm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                json={
                    "model": settings.litellm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LiteLLM reminder draft failed: %s — using template fallback", exc)
        return _template_reminder(invoice, stage, remaining)


def _template_reminder(invoice: dict, stage: int, remaining: float) -> str:
    """Fallback template when LLM is unreachable."""
    days_overdue = (TODAY - date.fromisoformat(invoice["due_date"])).days
    if stage == 1:
        return (
            f"Dear {invoice.get('counterparty_name', 'Valued Customer')},\n\n"
            f"This is a friendly reminder that invoice {invoice.get('invoice_no')} "
            f"for ฿{remaining:,.2f} is now {days_overdue} day(s) overdue. "
            f"Please arrange payment at your earliest convenience.\n\n"
            f"Thank you for your business."
        )
    elif stage == 2:
        return (
            f"Dear {invoice.get('counterparty_name', 'Valued Customer')},\n\n"
            f"Invoice {invoice.get('invoice_no')} for ฿{remaining:,.2f} remains unpaid "
            f"and is now {days_overdue} days overdue. We request immediate payment. "
            f"Please contact us if you have any concerns.\n\nRegards."
        )
    else:
        return (
            f"Dear {invoice.get('counterparty_name', 'Valued Customer')},\n\n"
            f"Invoice {invoice.get('invoice_no')} for ฿{remaining:,.2f} is {days_overdue} days overdue. "
            f"If payment is not received within 7 days, we may have no choice but to escalate "
            f"this matter through formal collection channels. Please contact us immediately.\n\nRegards."
        )


async def run_overdue_agent(sme_id: str = "TH-SME-001") -> OverdueInvoicesResponse:
    """
    Detect overdue invoices, assign stages, draft reminders, create pending actions.
    """
    with open(SEED_FILE) as f:
        seed_data = json.load(f)

    invoices = seed_data if isinstance(seed_data, list) else seed_data.get("invoices", [])
    overdue_results = []
    total_outstanding = 0.0

    for inv in invoices:
        if not _is_overdue(inv):
            continue

        due = date.fromisoformat(inv["due_date"])
        days_overdue = (TODAY - due).days
        remaining = _remaining_balance(inv)
        total_outstanding += remaining
        stage, stage_label = _assign_stage(days_overdue)
        blocked = _blocked_by_1day_rule(inv)

        draft = None
        pending_action_id = None

        if not blocked:
            draft = await _draft_reminder_via_llm(inv, stage, stage_label, remaining)
            # Create pending action for owner approval
            try:
                action = approval_gateway.create_pending_action(
                    action_type="reminder_send",
                    memo=f"Send {stage_label} reminder for {inv.get('invoice_no')} to {inv.get('counterparty_name')} — ฿{remaining:,.2f} outstanding",
                    amount=remaining,
                    dest_account=inv.get("customer_email"),
                )
                pending_action_id = action.id
            except Exception as exc:
                logger.warning("Could not create pending action for invoice %s: %s", inv.get("invoice_id"), exc)

        overdue_results.append(OverdueInvoice(
            invoice_id=inv["invoice_id"],
            invoice_no=inv.get("invoice_no", ""),
            counterparty_name=inv.get("counterparty_name", ""),
            customer_email=inv.get("customer_email"),
            amount_thb=inv.get("amount_thb", 0.0),
            amount_paid_thb=inv.get("amount_paid_thb", 0.0),
            remaining_balance=remaining,
            due_date=inv["due_date"],
            days_overdue=days_overdue,
            stage=stage,
            stage_label=stage_label,
            draft_reminder=draft,
            blocked_by_1day_rule=blocked,
            pending_action_id=pending_action_id,
        ))

    return OverdueInvoicesResponse(
        as_of_date=str(TODAY),
        overdue_invoices=overdue_results,
        total_outstanding_thb=round(total_outstanding, 2),
    )


def log_reminder_sent(invoice_id: str):
    _reminder_log[invoice_id] = "sent"


def log_reminder_rejected(invoice_id: str):
    _reminder_log[invoice_id] = "rejected"
