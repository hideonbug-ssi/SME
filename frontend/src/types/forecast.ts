export interface ForecastDataPoint {
  date: string;
  projected_balance: number;
  confidence: number;
}

export interface ForecastSummary {
  min_point: number;
  min_date: string;
  max_point: number;
  max_date: string;
  key_drivers: string[];
}

export type ConfidenceLevel = 'high' | 'low';

export interface HistoricalDataPoint {
  date: string;
  actual_balance: number;
}

export interface WithProductDataPoint {
  date: string;
  projected_balance: number;
}

export interface ForecastResponse {
  data_points: ForecastDataPoint[];
  summary: ForecastSummary;
  rolling_avg_monthly_outflow: number;
  confidence_overall: ConfidenceLevel;
  updated_at: string;
  alert_message?: string;
  alert_message_th?: string;
  surplus_detected?: boolean;
  shortfall_detected?: boolean;
  historical_data_points?: HistoricalDataPoint[];
  with_product_data_points?: WithProductDataPoint[];
  product_impact_description?: string;
}
