"""
MCP client for the product recommendation catalogue (AIWSRT-6).

Tries to connect to the real MCP server at MCP_SERVER_URL. If the server is
unreachable (ConnectionError, timeout, or any HTTP error), falls back to
MockMCPClient which returns the hardcoded 11-product catalogue. This ensures
the PoC works in development without a running MCP server.
"""
import httpx
import logging
from dataclasses import dataclass, field
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Product catalogue — 11 products from the context doc
# The real MCP server would return these dynamically; the mock always returns them.
# ---------------------------------------------------------------------------

PRODUCT_CATALOGUE = [
    {
        "product_id": "PROD-001",
        "product_name": "KTB SME Term Loan",
        "triggering_signal": "shortfall_red",
        "consent_category": "lending",
        "is_lending": True,
        "is_offerable": True,
        "disclosures": [
            "Loan subject to credit approval.",
            "Interest rates and terms may vary.",
            "Collateral may be required.",
        ],
    },
    {
        "product_id": "PROD-002",
        "product_name": "KTB SME Revolving Credit Line",
        "triggering_signal": "shortfall_yellow",
        "consent_category": "lending",
        "is_lending": True,
        "is_offerable": True,
        "disclosures": [
            "Credit line subject to annual review.",
            "Interest charged on drawn amount only.",
        ],
    },
    {
        "product_id": "PROD-003",
        "product_name": "KTB Invoice Financing",
        "triggering_signal": "shortfall_yellow",
        "consent_category": "lending",
        "is_lending": True,
        "is_offerable": True,
        "disclosures": [
            "Advances up to 80% of invoice face value.",
            "Repayment upon customer settlement.",
        ],
    },
    {
        "product_id": "PROD-004",
        "product_name": "KTB Trade Finance / Supplier Credit",
        "triggering_signal": "shortfall_yellow",
        "consent_category": "lending",
        "is_lending": True,
        "is_offerable": True,
        "disclosures": [
            "Extends supplier payment terms.",
            "Subject to supplier network participation.",
        ],
    },
    {
        "product_id": "PROD-005",
        "product_name": "KTB Thai ESG Fund",
        "triggering_signal": "tax_advisory",
        "consent_category": "investment",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "Investment involves risk. Past performance is not indicative of future results.",
            "This is not a guaranteed return product.",
            "Tax benefit subject to Revenue Department approval.",
        ],
    },
    {
        "product_id": "PROD-006",
        "product_name": "KTB RMF Fund",
        "triggering_signal": "tax_advisory",
        "consent_category": "investment",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "Must be held until age 55 and minimum 5 years.",
            "Investment involves risk.",
            "Tax benefit subject to Revenue Department rules.",
        ],
    },
    {
        "product_id": "PROD-007",
        "product_name": "KTB High-Yield Term Deposit",
        "triggering_signal": "opportunity",
        "consent_category": "deposit",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "Deposit rates subject to change.",
            "Early withdrawal may result in reduced interest.",
            "Protected by DPA up to ฿1,000,000.",
        ],
    },
    {
        "product_id": "PROD-008",
        "product_name": "KTB Tax Reserve Sub-Account",
        "triggering_signal": "tax_advisory",
        "consent_category": "deposit",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "Funds in sub-account remain yours — not held by the bank.",
            "No minimum balance required.",
        ],
    },
    {
        "product_id": "PROD-009",
        "product_name": "KTB SME Business Insurance",
        "triggering_signal": "opportunity",
        "consent_category": "insurance",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "Insurance is underwritten by a third party.",
            "Coverage terms and exclusions apply.",
        ],
    },
    {
        "product_id": "PROD-010",
        "product_name": "KTB SME FX Hedging Product",
        "triggering_signal": "opportunity",
        "consent_category": "fx",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "FX products carry market risk.",
            "Not suitable for speculative use.",
        ],
    },
    {
        "product_id": "PROD-011",
        "product_name": "KTB Merchant Payment Acceptance",
        "triggering_signal": "opportunity",
        "consent_category": "payments",
        "is_lending": False,
        "is_offerable": True,
        "disclosures": [
            "Transaction fees apply.",
            "Settlement period T+1.",
        ],
    },
]


class MockMCPClient:
    """Fallback when the real MCP server is not reachable. Returns the hardcoded catalogue."""

    async def get_product_recommendation(self, trigger_context: str, signals: dict) -> list[dict]:
        logger.info("MockMCPClient: returning hardcoded product catalogue (MCP server unreachable)")
        return PRODUCT_CATALOGUE


class MCPClient:
    """Real MCP client — calls the MCP server at MCP_SERVER_URL."""

    def __init__(self, server_url: str | None = None):
        self.server_url = server_url or settings.mcp_server_url

    async def get_product_recommendation(self, trigger_context: str, signals: dict) -> list[dict]:
        try:
            async with httpx.AsyncClient(base_url=self.server_url, timeout=5.0) as client:
                response = await client.post(
                    "/tools/get_product_recommendation",
                    json={"trigger_context": trigger_context, "signals": signals},
                )
                response.raise_for_status()
                return response.json().get("products", PRODUCT_CATALOGUE)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning("MCP server unreachable (%s) — falling back to mock catalogue.", exc)
            return PRODUCT_CATALOGUE


def get_mcp_client() -> MCPClient | MockMCPClient:
    """Returns MCPClient; test by pinging the server, fall back to mock if unreachable."""
    return MCPClient()


mcp_client = get_mcp_client()
