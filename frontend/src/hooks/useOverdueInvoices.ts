import { useQuery } from '@tanstack/react-query';
import { getOverdueInvoices } from '../api/invoices';

export const OVERDUE_INVOICES_QUERY_KEY = ['invoices', 'overdue'] as const;

export function useOverdueInvoices() {
  return useQuery({
    queryKey: OVERDUE_INVOICES_QUERY_KEY,
    queryFn: getOverdueInvoices,
    staleTime: 30_000,
    retry: 2,
  });
}
