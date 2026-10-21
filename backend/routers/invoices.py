"""
Invoice router — AIWSRT-3 (OCR extraction) and AIWSRT-7 (overdue reminders).
"""
import base64
import logging
import uuid
import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional
from config import settings
from models.invoice import InvoiceExtractResponse, ExtractedInvoiceFields, OverdueInvoicesResponse
from agents.overdue_agent import run_overdue_agent, log_reminder_sent, log_reminder_rejected
from services.approval_gateway import approval_gateway

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invoices", tags=["invoices"])

# In-memory store for extracted invoices (PoC)
_extracted_invoices: list[dict] = []

SUPPORTED_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}


@router.post("/extract", response_model=InvoiceExtractResponse)
async def extract_invoice(
    document: UploadFile = File(...),
    direction_hint: Optional[str] = Form(default=None),
):
    """
    AIWSRT-3: Upload an invoice image/PDF, extract fields via vision LLM.
    If confidence < 0.85, requires owner review (not auto-recorded).
    """
    if document.content_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {document.content_type}")

    file_bytes = await document.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Empty file uploaded")

    file_b64 = base64.b64encode(file_bytes).decode("utf-8")
    media_type = document.content_type

    direction_instruction = ""
    if direction_hint:
        direction_instruction = f" The document is expected to be a {direction_hint}."

    prompt = (
        f"You are an invoice data extraction assistant.{direction_instruction} "
        f"Extract all fields from this invoice and return them as a JSON object with exactly these keys: "
        f"direction (payable or receivable), counterparty_name, customer_email, invoice_no, "
        f"amount_thb (number), amount_paid_thb (number, 0 if none), issue_date (YYYY-MM-DD), "
        f"due_date (YYYY-MM-DD), payment_status (unpaid/partial/paid), confidence (0.0–1.0). "
        f"If a field cannot be extracted with confidence, set it to null. "
        f"Set confidence to the overall extraction confidence across all fields. "
        f"Return ONLY valid JSON, no explanation."
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.litellm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                json={
                    "model": settings.litellm_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{media_type};base64,{file_b64}"},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error("Invoice OCR LLM call failed: %s", exc)
        raise HTTPException(status_code=500, detail="OCR service error")

    # Parse JSON from LLM response
    import json as _json
    try:
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        extracted = _json.loads(content)
    except _json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Extraction failed: LLM returned invalid JSON")

    confidence = float(extracted.get("confidence", 0.0))
    requires_review = confidence < 0.85

    record_id = None
    if not requires_review:
        record_id = str(uuid.uuid4())
        _extracted_invoices.append({"record_id": record_id, **extracted})

    return InvoiceExtractResponse(
        direction=extracted.get("direction", "payable"),
        extracted_fields=ExtractedInvoiceFields(
            counterparty_name=extracted.get("counterparty_name"),
            customer_email=extracted.get("customer_email"),
            invoice_no=extracted.get("invoice_no"),
            amount_thb=extracted.get("amount_thb"),
            amount_paid_thb=extracted.get("amount_paid_thb", 0.0),
            issue_date=extracted.get("issue_date"),
            due_date=extracted.get("due_date"),
            payment_status=extracted.get("payment_status"),
        ),
        confidence=confidence,
        record_id=record_id,
        requires_review=requires_review,
    )


@router.get("/overdue", response_model=OverdueInvoicesResponse)
async def get_overdue_invoices(sme_id: str = "TH-SME-001"):
    """
    AIWSRT-7: Detect overdue invoices, assign stages, draft reminders, create pending actions.
    """
    try:
        return await run_overdue_agent(sme_id=sme_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Overdue agent unavailable: {exc}")


@router.post("/{invoice_id}/remind/confirm")
async def confirm_reminder(invoice_id: str, action_id: str):
    """Owner approves sending the reminder — marks as sent (stub: no real email)."""
    try:
        approval_gateway.confirm_action(action_id)
        log_reminder_sent(invoice_id)
        return {"status": "sent", "invoice_id": invoice_id, "note": "Reminder logged (stub — no real delivery in PoC)"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{invoice_id}/remind/reject")
async def reject_reminder(invoice_id: str, action_id: str):
    """Owner rejects the reminder — nothing sent."""
    try:
        approval_gateway.reject_action(action_id)
        log_reminder_rejected(invoice_id)
        return {"status": "rejected", "invoice_id": invoice_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
