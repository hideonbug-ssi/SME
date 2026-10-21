export type RepayabilityStatus = 'passed' | 'not_applicable';

export interface ProductRecommendation {
  product_id: string;
  product_name: string;
  rationale: string;
  relevance_score: number;
  signal_basis: string;
  repayability: RepayabilityStatus;
  disclosures: string[];
}

export interface RecommendationResponse {
  recommendation: ProductRecommendation | null;
}

export type TriggerContext =
  | 'tax_advisory'
  | 'shortfall_yellow'
  | 'shortfall_red'
  | 'opportunity';
