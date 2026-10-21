from pydantic import BaseModel
from typing import Optional


class ExtractedInvoiceFields(BaseModel):
    counterparty_name: Optional[str] = None
    customer_email: Optional[str] = None
    invoice_no: Optional[str] = None
    amount_thb: Optional[float] = None
    amount_paid_thb: Optional[float] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    payment_status: Optional[str] = None


class InvoiceExtractResponse(BaseModel):
    direction: str  # "payable" | "receivable"
    extracted_fields: ExtractedInvoiceFields
    confidence: float
    record_id: Optional[str] = None
    requires_review: bool = False


class OverdueInvoice(BaseModel):
    invoice_id: str
    invoice_no: str
    counterparty_name: str
    customer_email: Optional[str] = None
    amount_thb: float
    amount_paid_thb: float
    remaining_balance: float
    due_date: str
    days_overdue: int
    stage: int  # 1, 2, or 3 (final)
    stage_label: str  # "Stage 1 - Gentle" | "Stage 2 - Firmer" | "Final - Pre-Legal"
    draft_reminder: Optional[str] = None
    blocked_by_1day_rule: bool = False
    pending_action_id: Optional[str] = None


class OverdueInvoicesResponse(BaseModel):
    as_of_date: str  # ISO date string
    overdue_invoices: list[OverdueInvoice]
    total_outstanding_thb: float
