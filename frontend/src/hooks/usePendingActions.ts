import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPendingActions,
  confirmPendingAction,
  dismissPendingAction,
} from '../api/shortfall';

export const PENDING_ACTIONS_QUERY_KEY = ['pending-actions'] as const;

export function usePendingActions() {
  return useQuery({
    queryKey: PENDING_ACTIONS_QUERY_KEY,
    queryFn: getPendingActions,
    staleTime: 30_000,
    retry: 2,
  });
}

export function useConfirmPendingAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => confirmPendingAction(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PENDING_ACTIONS_QUERY_KEY });
    },
  });
}

export function useDismissPendingAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => dismissPendingAction(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PENDING_ACTIONS_QUERY_KEY });
    },
  });
}
