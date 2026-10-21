import client from './client';
import type { ShortfallStatus, PendingActionsResponse } from '../types/shortfall';

export async function getShortfallStatus(): Promise<ShortfallStatus> {
  const { data } = await client.get<ShortfallStatus>('/api/v1/shortfall/status');
  return data;
}

export async function getPendingActions(): Promise<PendingActionsResponse> {
  const { data } = await client.get<PendingActionsResponse>('/api/v1/pending-actions');
  return data;
}

export async function confirmPendingAction(id: string): Promise<void> {
  await client.post(`/api/v1/pending-actions/${id}/confirm`);
}

export async function dismissPendingAction(id: string): Promise<void> {
  await client.delete(`/api/v1/pending-actions/${id}`);
}
