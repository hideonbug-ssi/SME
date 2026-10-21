import { useQuery } from '@tanstack/react-query';
import { getShortfallStatus } from '../api/shortfall';

export const SHORTFALL_QUERY_KEY = ['shortfall'] as const;

export function useShortfall() {
  return useQuery({
    queryKey: SHORTFALL_QUERY_KEY,
    queryFn: getShortfallStatus,
    staleTime: 60_000,
    retry: 2,
  });
}
