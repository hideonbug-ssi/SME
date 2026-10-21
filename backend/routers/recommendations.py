"""
Product recommendation router — AIWSRT-6 upsell endpoint.
"""
import logging
import httpx
from fastapi import APIRouter, HTTPException
from models.recommendation import RecommendationRequest, RecommendationResponse, ProductRecommendation
from services.mcp_client import mcp_client
from services.recommendation_engine import score_products
from services.repayability import assess_repayability
from config import settings
from agent_tracer import tracer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Default product monthly repayment for repayability check (conservative)
_DEFAULT_PRODUCT_MONTHLY_REPAYMENT = 15000.0


async def _generate_rationale(
    product_name: str, trigger_context: str, signals: dict
) -> tuple[str, str, str]:
    """
    Call LiteLLM to generate a grounded product rationale from the owner's actual figures.
    Returns (prompt_str, rationale, source) where source is "llm" or "fallback".
    """
    signal_summary = "; ".join(f"{k}={v}" for k, v in signals.items() if v is not None)
    prompt = (
        f"Generate a concise, factual rationale (2–3 sentences) for recommending '{product_name}' "
        f"to an SME owner based on the following signal data:\n"
        f"Trigger: {trigger_context}\n"
        f"Signal data: {signal_summary}\n\n"
        f"Rules: (1) Only reference the owner's actual figures — no invented facts. "
        f"(2) No guaranteed returns or guaranteed tax savings. "
        f"(3) One product, one rationale. "
        f"(4) Keep it under 60 words."
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{settings.litellm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                json={
                    "model": settings.litellm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                },
            )
            response.raise_for_status()
            data = response.json()
            rationale = data["choices"][0]["message"]["content"].strip()
            return prompt, rationale, "llm"
    except Exception as exc:
        logger.warning("LiteLLM rationale generation failed: %s — using template", exc)
        rationale = _template_rationale(product_name, trigger_context, signals)
        return prompt, rationale, "fallback"


def _template_rationale(product_name: str, trigger_context: str, signals: dict) -> str:
    """Fallback rationale when LLM is unreachable."""
    amount = signals.get("amount_thb", signals.get("shortfall_amount_thb", 0))
    if trigger_context in ("shortfall_yellow", "shortfall_red"):
        return (
            f"Based on your projected cash shortfall of ฿{amount:,.0f}, "
            f"{product_name} could help bridge the gap and maintain business continuity."
        )
    elif trigger_context == "opportunity":
        return (
            f"Your sustained cash surplus of ฿{amount:,.0f} presents an opportunity to earn "
            f"higher returns with {product_name}."
        )
    elif trigger_context == "tax_advisory":
        return (
            f"{product_name} may help reduce your tax liability based on your current income position. "
            f"Please consult a tax professional before investing."
        )
    return f"{product_name} is recommended based on your current financial position."


@router.post("/products", response_model=RecommendationResponse)
async def get_product_recommendation(request: RecommendationRequest):
    """
    Signal-to-product matching with LLM-generated rationale (AIWSRT-6).

    Business rules enforced:
    - At most ONE product returned (highest-scoring)
    - Relevance score < 0.70 → null recommendation
    - Lending products require repayability: passed (NPL guard)
    - Consent assumed for PoC unless trigger_context is missing

    This endpoint closes the unified agent trace run (started by forecast router) so the
    Console shows all three agents' steps in one cohesive timeline.
    """
    if not request.trigger_context:
        tracer.finish_run()
        raise HTTPException(status_code=403, detail="consent_required: trigger_context missing")

    # Fetch product catalogue from MCP (falls back to mock automatically)
    try:
        products = await mcp_client.get_product_recommendation(
            trigger_context=request.trigger_context,
            signals=request.signals,
        )
    except Exception as exc:
        logger.error("MCP client failed: %s", exc)
        tracer.finish_run()
        return RecommendationResponse(recommendation=None)

    tracer.emit_step(
        agent="RecommendationEngine",
        action="fetch_product_catalogue",
        input_data={"trigger_context": request.trigger_context, "source": "MCP (mock)"},
        output={"products_available": len(products)},
        duration_ms=0,
    )

    # Determine repayability from signals (PoC: use passed flag if provided, else assess)
    repayability_passed = request.signals.get("repayability_passed", True)
    projected_cashflows = request.signals.get("projected_monthly_cashflows", [50000.0] * 6)
    if isinstance(projected_cashflows, list) and not request.signals.get("repayability_passed"):
        rep_result = assess_repayability(projected_cashflows, _DEFAULT_PRODUCT_MONTHLY_REPAYMENT)
        repayability_passed = rep_result.passes

    # Score products — returns None if nothing clears threshold
    opted_out = request.signals.get("opted_out_categories", [])
    best_product = score_products(
        products=products,
        trigger_context=request.trigger_context,
        repayability_passed=repayability_passed,
        opted_out_categories=opted_out,
    )

    tracer.emit_step(
        agent="RecommendationEngine",
        action="score_and_select",
        input_data={
            "products_evaluated": len(products),
            "threshold": 0.70,
            "repayability_passed": repayability_passed,
            "opted_out": opted_out,
        },
        output={
            "winner": best_product.product_name if best_product else None,
            "score": best_product.score if best_product else None,
            "recommendation": best_product is not None,
        },
    )

    if best_product is None:
        tracer.finish_run()
        return RecommendationResponse(recommendation=None)

    # Generate LLM rationale grounded in the owner's actual figures
    prompt_str, rationale, rationale_source = await _generate_rationale(
        product_name=best_product.product_name,
        trigger_context=request.trigger_context,
        signals=request.signals,
    )

    tracer.emit_step(
        agent="RecommendationEngine",
        action="generate_rationale",
        input_data={
            "product": best_product.product_name,
            "trigger_context": request.trigger_context,
            "rationale_source": rationale_source,
        },
        prompt=prompt_str,
        reasoning=rationale,
        output={
            "rationale": rationale,
            "source": rationale_source,  # "llm" or "fallback"
        },
    )

    repayability_label = "passed" if not best_product.is_lending else ("passed" if repayability_passed else "failed")

    tracer.finish_run()  # close the unified ForecastAgent → ShortfallAgent → RecommendationEngine trace
    return RecommendationResponse(
        recommendation=ProductRecommendation(
            product_id=best_product.product_id,
            product_name=best_product.product_name,
            rationale=rationale,
            relevance_score=best_product.score,
            signal_basis=best_product.signal_basis,
            repayability=repayability_label,
            disclosures=best_product.disclosures,
        )
    )
