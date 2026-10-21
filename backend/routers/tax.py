"""
Tax router — AIWSRT-4 tax calculation assistant.
"""
from fastapi import APIRouter, HTTPException
from models.tax import TaxSessionResponse, TaxCalculateResponse, TaxCalculateRequest
from agents.tax_agent import create_tax_session, calculate_tax

router = APIRouter(prefix="/tax", tags=["tax"])


@router.post("/session", response_model=TaxSessionResponse)
async def start_tax_session(taxpayer_type: str | None = None):
    """
    Start a tax calculation session. Derives taxpayer type (individual/juristic).
    Pre-fills figures from the mock ledger.
    """
    try:
        return await create_tax_session(taxpayer_type=taxpayer_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/session/calculate", response_model=TaxCalculateResponse)
async def calculate_tax_session(session_id: str, request: TaxCalculateRequest):
    """
    Run the tax calculation. Returns PIT or CIT + VAT or SBT (never both VAT and SBT).
    Output is guidance only — not a tax filing.
    """
    try:
        return await calculate_tax(session_id=session_id, request_data=request.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
