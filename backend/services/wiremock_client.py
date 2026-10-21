"""
WireMock client — all external data access for the PoC goes through here.
WireMock is the single source of truth at runtime; this client is the outbound adapter.
"""
import httpx
from config import settings


class WireMockClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.wiremock_base_url

    async def get_accounts(self, sme_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(f"/api/v1/accounts/{sme_id}")
            response.raise_for_status()
            return response.json()

    async def get_transactions(self, sme_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(f"/api/v1/transactions", params={"sme_id": sme_id})
            response.raise_for_status()
            return response.json()

    async def get_invoices_payable(self, sme_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(f"/api/v1/invoices/payable", params={"sme_id": sme_id})
            response.raise_for_status()
            return response.json()

    async def get_invoices_receivable(self, sme_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(f"/api/v1/invoices/receivable", params={"sme_id": sme_id})
            response.raise_for_status()
            return response.json()


wiremock_client = WireMockClient()
