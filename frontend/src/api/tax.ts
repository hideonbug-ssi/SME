import client from './client';
import type { TaxSessionInput, TaxSessionResponse } from '../types/tax';

export async function calculateTax(input: TaxSessionInput): Promise<TaxSessionResponse> {
  const { data } = await client.post<TaxSessionResponse>(
    '/api/v1/tax/session/calculate',
    input,
  );
  return data;
}

export async function createTaxSetAside(
  sessionId: string,
  amount: number,
): Promise<{ pending_action_id: string }> {
  const { data } = await client.post<{ pending_action_id: string }>(
    '/api/v1/tax/session/set-aside',
    { session_id: sessionId, amount_thb: amount },
  );
  return data;
}
