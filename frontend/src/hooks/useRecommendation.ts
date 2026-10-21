import { useQuery } from '@tanstack/react-query';
import { getRecommendation } from '../api/recommendations';
import type { TriggerContext } from '../types/recommendation';

export const RECOMMENDATION_QUERY_KEY = ['recommendation'] as const;

export function useRecommendation(triggerContext: TriggerContext, enabled = true) {
  return useQuery({
    queryKey: [...RECOMMENDATION_QUERY_KEY, triggerContext],
    queryFn: () => getRecommendation(triggerContext),
    staleTime: 120_000, // 2 minutes
    retry: 1,
    enabled,
  });
}
