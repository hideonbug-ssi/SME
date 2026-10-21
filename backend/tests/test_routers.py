"""
FastAPI router integration tests — all agents and LLM calls are mocked.
Uses FastAPI TestClient (synchronous) so no asyncio fixtures needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from services.mcp_client import PRODUCT_CATALOGUE

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthz:
    def test_returns_200(self):
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_returns_ok_body(self):
        response = client.get("/healthz")
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Forecast router
# ---------------------------------------------------------------------------

class TestForecastRouter:
    def _mock_forecast_response(self):
        """Build a minimal ForecastResponse-compatible mock."""
        from models.forecast import ForecastResponse, ForecastDataPoint, ForecastSummary
        from datetime import date
        return ForecastResponse(
            sme_id="TH-SME-001",
            data_points=[
                ForecastDataPoint(date=date(2026, 7, 14), projected_balance=280000.0, confidence="high")
            ],
            summary=ForecastSummary(
                min_point=71313.0,
                min_date=date(2026, 7, 26),
                max_point=283180.0,
                max_date=date(2026, 7, 19),
                key_drivers=["Payment due: Large supplier invoice (฿180,000) on 2026-07-26"],
            ),
            rolling_avg_monthly_outflow=270550.0,
            confidence_overall="high",
            updated_at="2026-07-14T00:00:00Z",
            alert_message="⚠️ Cash shortfall projected on 2026-07-26.",
            alert_message_th="⚠️ คาดว่าจะมีเงินสดไม่เพียงพอ",
            surplus_detected=False,
            shortfall_detected=True,
            handoff_payload={
                "trigger_context": "shortfall_yellow",
                "amount_thb": 63962.0,
            },
        )

    def test_returns_200(self):
        with patch("routers.forecast.run_forecast_agent", new=AsyncMock(return_value=self._mock_forecast_response())):
            response = client.get("/api/v1/forecast/cashflow")
        assert response.status_code == 200

    def test_response_has_data_points(self):
        with patch("routers.forecast.run_forecast_agent", new=AsyncMock(return_value=self._mock_forecast_response())):
            response = client.get("/api/v1/forecast/cashflow")
        data = response.json()
        assert "data_points" in data
        assert len(data["data_points"]) >= 1

    def test_response_has_confidence_field(self):
        with patch("routers.forecast.run_forecast_agent", new=AsyncMock(return_value=self._mock_forecast_response())):
            response = client.get("/api/v1/forecast/cashflow")
        assert response.json()["confidence_overall"] in ("high", "low")

    def test_horizon_days_param_accepted(self):
        with patch("routers.forecast.run_forecast_agent", new=AsyncMock(return_value=self._mock_forecast_response())):
            response = client.get("/api/v1/forecast/cashflow?horizon_days=30")
        assert response.status_code == 200

    def test_agent_error_returns_503(self):
        with patch("routers.forecast.run_forecast_agent", new=AsyncMock(side_effect=RuntimeError("WireMock down"))):
            response = client.get("/api/v1/forecast/cashflow")
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Shortfall / Pending-action router
# ---------------------------------------------------------------------------

class TestShortfallRouter:
    def _mock_shortfall_response(self, tier="yellow"):
        from models.forecast import ShortfallStatusResponse
        return ShortfallStatusResponse(
            tier=tier,
            shortfall_amount_thb=63962.0 if tier != "green" else None,
            shortfall_date="2026-07-26" if tier != "green" else None,
            recovery_plan="Consider arranging a revolving credit line." if tier != "green" else None,
            product_trigger={"trigger_context": f"shortfall_{tier}"} if tier != "green" else None,
            repayability_passed=True if tier != "green" else None,
        )

    def test_shortfall_status_returns_200(self):
        with patch("routers.shortfall.run_shortfall_agent", new=AsyncMock(return_value=self._mock_shortfall_response())):
            response = client.get("/api/v1/shortfall/status")
        assert response.status_code == 200

    def test_shortfall_status_tier_field_present(self):
        with patch("routers.shortfall.run_shortfall_agent", new=AsyncMock(return_value=self._mock_shortfall_response("red"))):
            response = client.get("/api/v1/shortfall/status")
        assert response.json()["tier"] in ("green", "yellow", "red")

    def test_shortfall_agent_error_returns_503(self):
        with patch("routers.shortfall.run_shortfall_agent", new=AsyncMock(side_effect=RuntimeError("agent down"))):
            response = client.get("/api/v1/shortfall/status")
        assert response.status_code == 503

    def test_list_pending_actions_returns_200(self):
        response = client.get("/api/v1/pending-actions")
        assert response.status_code == 200
        assert "pending_actions" in response.json()

    def test_confirm_nonexistent_pending_action_returns_404(self):
        response = client.post("/api/v1/pending-actions/nonexistent-uuid/confirm")
        assert response.status_code == 404

    def test_reject_nonexistent_pending_action_returns_404(self):
        response = client.delete("/api/v1/pending-actions/nonexistent-uuid")
        assert response.status_code == 404

    def test_confirm_and_reject_lifecycle(self):
        from services.approval_gateway import approval_gateway
        # Create a real pending action and confirm it via the API
        action = approval_gateway.create_pending_action("fund_transfer", "Test lifecycle")
        response = client.post(f"/api/v1/pending-actions/{action.id}/confirm")
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"

    def test_reject_action_via_api(self):
        from services.approval_gateway import approval_gateway
        action = approval_gateway.create_pending_action("reminder_send", "Test reject")
        response = client.delete(f"/api/v1/pending-actions/{action.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# Recommendations router
# ---------------------------------------------------------------------------

class TestRecommendationsRouter:
    def test_empty_trigger_context_returns_403(self):
        response = client.post("/api/v1/recommendations/products", json={
            "sme_id": "TH-SME-001",
            "trigger_context": "",
            "signals": {},
        })
        assert response.status_code == 403

    def test_valid_opportunity_trigger_returns_200(self):
        with patch("routers.recommendations.mcp_client.get_product_recommendation",
                   new=AsyncMock(return_value=PRODUCT_CATALOGUE)), \
             patch("routers.recommendations._generate_rationale",
                   new=AsyncMock(return_value="High-yield deposit is ideal for your idle surplus.")):
            response = client.post("/api/v1/recommendations/products", json={
                "sme_id": "TH-SME-001",
                "trigger_context": "opportunity",
                "signals": {},
            })
        assert response.status_code == 200

    def test_opportunity_response_has_recommendation_field(self):
        with patch("routers.recommendations.mcp_client.get_product_recommendation",
                   new=AsyncMock(return_value=PRODUCT_CATALOGUE)), \
             patch("routers.recommendations._generate_rationale",
                   new=AsyncMock(return_value="Test rationale.")):
            response = client.post("/api/v1/recommendations/products", json={
                "sme_id": "TH-SME-001",
                "trigger_context": "opportunity",
                "signals": {},
            })
        data = response.json()
        assert "recommendation" in data
        # May be null (no match) or a product — just check the field exists
        if data["recommendation"] is not None:
            assert "product_id" in data["recommendation"]
            assert "relevance_score" in data["recommendation"]

    def test_shortfall_yellow_triggers_credit_line(self):
        with patch("routers.recommendations.mcp_client.get_product_recommendation",
                   new=AsyncMock(return_value=PRODUCT_CATALOGUE)), \
             patch("routers.recommendations._generate_rationale",
                   new=AsyncMock(return_value="Revolving credit line bridges your gap.")):
            response = client.post("/api/v1/recommendations/products", json={
                "sme_id": "TH-SME-001",
                "trigger_context": "shortfall_yellow",
                "signals": {"repayability_passed": True},
            })
        assert response.status_code == 200
        data = response.json()
        if data["recommendation"]:
            assert data["recommendation"]["relevance_score"] >= 0.70

    def test_npl_guard_suppresses_lending_products_when_repayability_fails(self):
        # To trigger the NPL guard the router must compute repayability as failed.
        # The router re-runs assess_repayability when repayability_passed is falsy AND
        # projected_monthly_cashflows is provided. Supply cashflows that fail the 1.2x check.
        with patch("routers.recommendations.mcp_client.get_product_recommendation",
                   new=AsyncMock(return_value=PRODUCT_CATALOGUE)), \
             patch("routers.recommendations._generate_rationale",
                   new=AsyncMock(return_value="N/A")):
            response = client.post("/api/v1/recommendations/products", json={
                "sme_id": "TH-SME-001",
                "trigger_context": "shortfall_red",
                "signals": {
                    "repayability_passed": False,
                    # cashflows that fail 1.2× the default 15,000 repayment (need >=18,000)
                    "projected_monthly_cashflows": [5000.0, 5000.0, 5000.0],
                },
            })
        assert response.status_code == 200
        data = response.json()
        # All products for shortfall_red are lending products → NPL guard → null
        assert data["recommendation"] is None

    def test_mcp_failure_returns_null_not_error(self):
        with patch("routers.recommendations.mcp_client.get_product_recommendation",
                   new=AsyncMock(side_effect=Exception("MCP down"))):
            response = client.post("/api/v1/recommendations/products", json={
                "sme_id": "TH-SME-001",
                "trigger_context": "opportunity",
                "signals": {},
            })
        assert response.status_code == 200
        assert response.json()["recommendation"] is None


# ---------------------------------------------------------------------------
# Tax router
# ---------------------------------------------------------------------------

class TestTaxRouter:
    def test_create_session_returns_200(self):
        response = client.post("/api/v1/tax/session", params={"taxpayer_type": "individual"})
        assert response.status_code == 200

    def test_create_session_returns_session_id(self):
        response = client.post("/api/v1/tax/session", params={"taxpayer_type": "individual"})
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_create_session_has_disclaimer(self):
        response = client.post("/api/v1/tax/session", params={"taxpayer_type": "individual"})
        data = response.json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 10

    def test_calculate_with_invalid_session_returns_404(self):
        response = client.post(
            "/api/v1/tax/session/calculate",
            params={"session_id": "nonexistent-session-id"},
            json={"taxpayer_type": "individual", "tax_year": 2025},
        )
        assert response.status_code == 404

    def test_calculate_pit_returns_result(self):
        # Create session first
        session_resp = client.post("/api/v1/tax/session", params={"taxpayer_type": "individual"})
        session_id = session_resp.json()["session_id"]

        calc_resp = client.post(
            "/api/v1/tax/session/calculate",
            params={"session_id": session_id},
            json={"taxpayer_type": "individual", "tax_year": 2025},
        )
        assert calc_resp.status_code == 200
        data = calc_resp.json()
        assert "pit_result" in data
        assert data["pit_result"] is not None
        assert data["pit_result"]["net_tax_payable"] >= 0

    def test_calculate_pit_worked_example(self):
        # Full path: create session → calculate with exact worked example inputs
        session_resp = client.post("/api/v1/tax/session", params={"taxpayer_type": "individual"})
        session_id = session_resp.json()["session_id"]

        calc_resp = client.post(
            "/api/v1/tax/session/calculate",
            params={"session_id": session_id},
            json={
                "taxpayer_type": "individual",
                "tax_year": 2025,
                "income_by_category": {"40_1_employment": 615000.0},
                "allowances": {"personal": 60000},
                "wht_suffered": 0.0,
            },
        )
        assert calc_resp.status_code == 200
        pit = calc_resp.json()["pit_result"]
        assert pit["net_tax_payable"] == 23000.0

    def test_calculate_includes_disclaimer(self):
        session_resp = client.post("/api/v1/tax/session", params={"taxpayer_type": "individual"})
        session_id = session_resp.json()["session_id"]

        calc_resp = client.post(
            "/api/v1/tax/session/calculate",
            params={"session_id": session_id},
            json={"taxpayer_type": "individual"},
        )
        data = calc_resp.json()
        assert "disclaimer" in data
        assert "guidance only" in data["disclaimer"].lower() or "not a tax filing" in data["disclaimer"].lower()


# ---------------------------------------------------------------------------
# Invoice router (OCR + overdue — agent mocked)
# ---------------------------------------------------------------------------

class TestInvoiceRouter:
    def test_overdue_invoices_returns_200(self):
        from models.invoice import OverdueInvoicesResponse
        mock_resp = OverdueInvoicesResponse(
            as_of_date="2026-07-14",
            overdue_invoices=[],
            total_outstanding_thb=0.0,
        )
        with patch("routers.invoices.run_overdue_agent", new=AsyncMock(return_value=mock_resp)):
            response = client.get("/api/v1/invoices/overdue")
        assert response.status_code == 200

    def test_overdue_invoices_response_has_expected_fields(self):
        from models.invoice import OverdueInvoicesResponse
        mock_resp = OverdueInvoicesResponse(
            as_of_date="2026-07-14",
            overdue_invoices=[],
            total_outstanding_thb=0.0,
        )
        with patch("routers.invoices.run_overdue_agent", new=AsyncMock(return_value=mock_resp)):
            response = client.get("/api/v1/invoices/overdue")
        data = response.json()
        assert "overdue_invoices" in data
        assert "as_of_date" in data
        assert "total_outstanding_thb" in data

    def test_extract_unsupported_type_returns_415(self):
        response = client.post(
            "/api/v1/invoices/extract",
            files={"document": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415

    def test_confirm_reminder_with_unknown_action_returns_404(self):
        response = client.post(
            "/api/v1/invoices/INV-001/remind/confirm",
            params={"action_id": "nonexistent"},
        )
        assert response.status_code == 404

    def test_reject_reminder_with_unknown_action_returns_404(self):
        response = client.post(
            "/api/v1/invoices/INV-001/remind/reject",
            params={"action_id": "nonexistent"},
        )
        assert response.status_code == 404
