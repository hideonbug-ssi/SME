import client from './client';
import type { RecommendationResponse, TriggerContext } from '../types/recommendation';

export async function getRecommendation(
  triggerContext: TriggerContext,
): Promise<RecommendationResponse> {
  const { data } = await client.post<RecommendationResponse>(
    '/api/v1/recommendations/products',
    { sme_id: 'SME-001', trigger_context: triggerContext, signals: {} },
  );
  return data;
}
