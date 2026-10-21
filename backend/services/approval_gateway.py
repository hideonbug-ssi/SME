"""
In-memory pending-action store and audit log (AIWSRT-30 Approval Gateway).

Every proposed action (fund transfer, reminder send) creates a pending-action record.
The owner confirms or rejects via the UI — the agent never auto-executes.
"""
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PendingAction:
    id: str
    action_type: str  # "fund_transfer" | "reminder_send" | "tax_setaside"
    amount: Optional[float]
    source_account: Optional[str]
    dest_account: Optional[str]
    memo: str
    status: str  # "pending" | "confirmed" | "rejected"
    created_at: str
    resolved_at: Optional[str] = None
    resolution_log: Optional[str] = None


class ApprovalGateway:
    """Thread-unsafe in-memory store — sufficient for the PoC."""

    def __init__(self):
        self._store: dict[str, PendingAction] = {}
        self._audit_log: list[dict] = []

    def create_pending_action(
        self,
        action_type: str,
        memo: str,
        amount: Optional[float] = None,
        source_account: Optional[str] = None,
        dest_account: Optional[str] = None,
    ) -> PendingAction:
        action_id = str(uuid.uuid4())
        action = PendingAction(
            id=action_id,
            action_type=action_type,
            amount=amount,
            source_account=source_account,
            dest_account=dest_account,
            memo=memo,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._store[action_id] = action
        self._audit(action_id, "created", memo)
        return action

    def confirm_action(self, action_id: str) -> PendingAction:
        action = self._get_or_raise(action_id)
        if action.status != "pending":
            raise ValueError(f"Action {action_id} is not in pending state (current: {action.status})")
        action.status = "confirmed"
        action.resolved_at = datetime.now(timezone.utc).isoformat()
        action.resolution_log = "Owner confirmed. Action logged (stub: no real execution in PoC)."
        self._audit(action_id, "confirmed", action.memo)
        return action

    def reject_action(self, action_id: str) -> PendingAction:
        action = self._get_or_raise(action_id)
        if action.status != "pending":
            raise ValueError(f"Action {action_id} is not in pending state (current: {action.status})")
        action.status = "rejected"
        action.resolved_at = datetime.now(timezone.utc).isoformat()
        action.resolution_log = "Owner rejected. No action taken."
        self._audit(action_id, "rejected", action.memo)
        return action

    def list_pending(self) -> list[PendingAction]:
        return [a for a in self._store.values() if a.status == "pending"]

    def get_action(self, action_id: str) -> Optional[PendingAction]:
        return self._store.get(action_id)

    def _get_or_raise(self, action_id: str) -> PendingAction:
        action = self._store.get(action_id)
        if not action:
            raise KeyError(f"Pending action {action_id} not found")
        return action

    def _audit(self, action_id: str, event: str, memo: str):
        self._audit_log.append({
            "action_id": action_id,
            "event": event,
            "memo": memo,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Singleton for the PoC — injected into routers
approval_gateway = ApprovalGateway()
