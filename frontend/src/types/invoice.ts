export type InvoiceDirection = 'payable' | 'receivable';
export type PaymentStatus = 'unpaid' | 'partial' | 'paid';
export type OverdueStage = 'stage1' | 'stage2' | 'final';

export interface ExtractedInvoiceFields {
  counterparty_name: string;
  customer_email?: string;
  invoice_no: string;
  amount_thb: number;
  amount_paid_thb?: number;
  issue_date?: string;
  due_date: string;
}

export interface InvoiceExtractResponse {
  direction: InvoiceDirection;
  extracted_fields: ExtractedInvoiceFields;
  confidence: number;
  record_id?: string;
  field_confidences?: Record<string, number>;
}

export interface OverdueInvoice {
  id: string;
  invoice_no: string;
  customer_name: string;
  amount_thb: number;
  amount_paid_thb: number;
  due_date: string;
  days_overdue: number;
  stage: OverdueStage;
  payment_status: PaymentStatus;
  last_reminder_sent?: string;
  last_contacted?: string;
  reminder_draft?: string;
}

export interface OverdueInvoicesResponse {
  invoices: OverdueInvoice[];
}
