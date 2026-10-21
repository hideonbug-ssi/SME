import client from './client';
import type { ForecastResponse } from '../types/forecast';

export async function getForecast(horizonDays = 90): Promise<ForecastResponse> {
  const { data } = await client.get<ForecastResponse>('/api/v1/forecast/cashflow', {
    params: { horizon_days: horizonDays },
  });
  return data;
}
