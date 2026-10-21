"""Unit tests for services/approval_gateway.py — 100% business logic coverage."""
import pytest

from services.approval_gateway import ApprovalGateway


def _fresh() -> ApprovalGateway:
    """Return a new, isolated ApprovalGateway — never share the singleton across tests."""
    return ApprovalGateway()


class TestCreatePendingAction:
    def test_create_returns_pending_status(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Test memo", amount=50000.0)
        assert action.status == "pending"

    def test_create_sets_action_type(self):
        gw = _fresh()
        action = gw.create_pending_action("reminder_send", "Send reminder")
        assert action.action_type == "reminder_send"

    def test_create_sets_memo(self):
        gw = _fresh()
        action = gw.create_pending_action("tax_setaside", "Reserve for Q4 tax")
        assert action.memo == "Reserve for Q4 tax"

    def test_create_sets_amount(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Transfer", amount=12345.67)
        assert action.amount == 12345.67

    def test_create_with_optional_fields(self):
        gw = _fresh()
        action = gw.create_pending_action(
            "fund_transfer",
            "Transfer to reserve",
            amount=20000.0,
            source_account="ACC-KTB-001",
            dest_account="ACC-RESERVE",
        )
        assert action.source_account == "ACC-KTB-001"
        assert action.dest_account == "ACC-RESERVE"

    def test_create_assigns_unique_ids(self):
        gw = _fresh()
        a1 = gw.create_pending_action("fund_transfer", "First")
        a2 = gw.create_pending_action("fund_transfer", "Second")
        assert a1.id != a2.id

    def test_create_sets_created_at_timestamp(self):
        gw = _fresh()
        action = gw.create_pending_action("reminder_send", "Memo")
        assert action.created_at is not None
        assert "T" in action.created_at  # ISO8601 format

    def test_create_resolved_at_is_none(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        assert action.resolved_at is None
        assert action.resolution_log is None


class TestConfirmAction:
    def test_confirm_changes_status_to_confirmed(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        confirmed = gw.confirm_action(action.id)
        assert confirmed.status == "confirmed"

    def test_confirm_sets_resolved_at(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        confirmed = gw.confirm_action(action.id)
        assert confirmed.resolved_at is not None

    def test_confirm_sets_resolution_log(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        confirmed = gw.confirm_action(action.id)
        assert confirmed.resolution_log is not None
        assert len(confirmed.resolution_log) > 0

    def test_confirm_nonexistent_raises_key_error(self):
        gw = _fresh()
        with pytest.raises(KeyError):
            gw.confirm_action("nonexistent-id")

    def test_confirm_already_confirmed_raises_value_error(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        gw.confirm_action(action.id)
        with pytest.raises(ValueError, match="not in pending state"):
            gw.confirm_action(action.id)

    def test_confirm_already_rejected_raises_value_error(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        gw.reject_action(action.id)
        with pytest.raises(ValueError, match="not in pending state"):
            gw.confirm_action(action.id)


class TestRejectAction:
    def test_reject_changes_status_to_rejected(self):
        gw = _fresh()
        action = gw.create_pending_action("reminder_send", "Memo")
        rejected = gw.reject_action(action.id)
        assert rejected.status == "rejected"

    def test_reject_sets_resolved_at(self):
        gw = _fresh()
        action = gw.create_pending_action("reminder_send", "Memo")
        rejected = gw.reject_action(action.id)
        assert rejected.resolved_at is not None

    def test_reject_nonexistent_raises_key_error(self):
        gw = _fresh()
        with pytest.raises(KeyError):
            gw.reject_action("nonexistent-id")

    def test_reject_already_rejected_raises_value_error(self):
        gw = _fresh()
        action = gw.create_pending_action("reminder_send", "Memo")
        gw.reject_action(action.id)
        with pytest.raises(ValueError, match="not in pending state"):
            gw.reject_action(action.id)

    def test_reject_already_confirmed_raises_value_error(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        gw.confirm_action(action.id)
        with pytest.raises(ValueError, match="not in pending state"):
            gw.reject_action(action.id)


class TestListPending:
    def test_list_pending_returns_only_pending_actions(self):
        gw = _fresh()
        a1 = gw.create_pending_action("fund_transfer", "One")
        a2 = gw.create_pending_action("fund_transfer", "Two")
        a3 = gw.create_pending_action("fund_transfer", "Three")
        gw.confirm_action(a2.id)
        gw.reject_action(a3.id)

        pending = gw.list_pending()
        assert len(pending) == 1
        assert pending[0].id == a1.id

    def test_list_pending_empty_when_all_resolved(self):
        gw = _fresh()
        a1 = gw.create_pending_action("fund_transfer", "One")
        gw.confirm_action(a1.id)
        assert gw.list_pending() == []

    def test_list_pending_empty_on_fresh_gateway(self):
        gw = _fresh()
        assert gw.list_pending() == []

    def test_list_pending_returns_all_pending_when_none_resolved(self):
        gw = _fresh()
        gw.create_pending_action("reminder_send", "R1")
        gw.create_pending_action("reminder_send", "R2")
        gw.create_pending_action("reminder_send", "R3")
        assert len(gw.list_pending()) == 3


class TestGetAction:
    def test_get_action_returns_correct_action(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Specific memo")
        fetched = gw.get_action(action.id)
        assert fetched is not None
        assert fetched.id == action.id
        assert fetched.memo == "Specific memo"

    def test_get_action_returns_none_for_missing_id(self):
        gw = _fresh()
        assert gw.get_action("does-not-exist") is None

    def test_get_action_reflects_status_after_confirm(self):
        gw = _fresh()
        action = gw.create_pending_action("fund_transfer", "Memo")
        gw.confirm_action(action.id)
        fetched = gw.get_action(action.id)
        assert fetched.status == "confirmed"
