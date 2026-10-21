export type TaxpayerType = 'PIT' | 'CIT';

export interface TaxBand {
  range: string;
  rate: number;
  tax_amount: number;
}

export interface TaxCalculationResult {
  taxpayer_type: TaxpayerType;
  gross_assessable?: number;
  total_expenses?: number;
  total_allowances?: number;
  net_taxable_income: number;
  tax_by_band: TaxBand[];
  progressive_tax: number;
  wht_credit_applied: number;
  net_tax_payable: number;
  indicative_vat_monthly?: number;
  indicative_sbt_monthly?: number;
  applicable_deadlines: string[];
  flags: string[];
  guidance_disclaimer: string;
}

export interface TaxSessionInput {
  taxpayer_type: TaxpayerType;
  tax_year: number;
  annual_income: number;
  annual_expenses: number;
  allowances: number;
  wht_suffered: number;
  annual_turnover?: number;
}

export interface TaxSessionResponse {
  session_id: string;
  result: TaxCalculationResult;
  recommendation_trigger?: {
    trigger_context: 'tax_advisory';
    unused_headroom_thb: number;
  };
}
