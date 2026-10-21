from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings
from routers import forecast, shortfall, recommendations, invoices, tax
from routers.demo import router as demo_router
from routers.console import router as console_router

app = FastAPI(
    title="SME Virtual CFO Agent",
    description="AI-powered CFO assistant for SME retail banking — PoC",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast.router, prefix="/api/v1")
app.include_router(shortfall.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(tax.router, prefix="/api/v1")
app.include_router(demo_router, prefix="/api/v1")
app.include_router(console_router, prefix="/api/v1")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port, reload=True)
