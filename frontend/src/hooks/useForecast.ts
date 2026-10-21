import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getForecast } from '../api/forecast';

export const FORECAST_QUERY_KEY = ['forecast'] as const;

export function useForecast(horizonDays = 90) {
  return useQuery({
    queryKey: [...FORECAST_QUERY_KEY, horizonDays],
    queryFn: () => getForecast(horizonDays),
    staleTime: 60_000, // 1 minute
    retry: 2,
  });
}

export function useRefreshForecast() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: FORECAST_QUERY_KEY });
}
