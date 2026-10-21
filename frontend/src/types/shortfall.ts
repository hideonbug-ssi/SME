export type ShortfallTier = 'green' | 'yellow' | 'red';

export interface ProductTrigger {
  trigger_context: 'shortfall_yellow' | 'shortfall_red';
}

export interface ShortfallStatus {
  tier: ShortfallTier;
  shortfall_amount_thb?: number;
  shortfall_date?: string;
  recovery_plan?: string;
  product_trigger?: ProductTrigger;
}

export interface PendingAction {
  id: string;
  action_type: string;
  amount: number;
  source_account: string;
  dest_account: string;
  memo: string;
  status: string;
  created_at: string;
}

export interface PendingActionsResponse {
  pending_actions: PendingAction[];
}
