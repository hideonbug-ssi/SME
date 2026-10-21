import client from './client';
import type {
  InvoiceExtractResponse,
  OverdueInvoicesResponse,
} from '../types/invoice';

export async function extractInvoice(
  file: File,
  directionHint?: 'payable' | 'receivable',
): Promise<InvoiceExtractResponse> {
  const formData = new FormData();
  formData.append('document', file);
  if (directionHint) {
    formData.append('direction_hint', directionHint);
  }
  const { data } = await client.post<InvoiceExtractResponse>(
    '/api/v1/invoices/extract',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function getOverdueInvoices(): Promise<OverdueInvoicesResponse> {
  const { data } = await client.get<OverdueInvoicesResponse>('/api/v1/invoices/overdue');
  return data;
}

export async function approveReminder(invoiceId: string): Promise<void> {
  await client.post(`/api/v1/invoices/${invoiceId}/remind/confirm`);
}

export async function rejectReminder(invoiceId: string): Promise<void> {
  await client.post(`/api/v1/invoices/${invoiceId}/remind/reject`);
}
