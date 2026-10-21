"""
Shared pytest fixtures for the SME Virtual CFO Agent backend tests.

Module-level stubs are injected into sys.modules BEFORE any other import
so that `from main import app` (used by test_routers.py) does not fail when
google-adk's LiteLlm extra is absent.  The stubs cover only what the agent
modules import at the top level — runtime calls are still mocked per-test.
"""
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports from backend root (services/, models/)
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Stub heavy agent dependencies so test collection doesn't fail when the
# optional google-adk[extensions] (LiteLlm) is not installed.
# ---------------------------------------------------------------------------

def _make_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# Only stub if the real LiteLlm import would fail
try:
    from google.adk.models.lite_llm import LiteLlm  # noqa: F401
except (ImportError, AttributeError):
    # Stub out the parts that agents import at module level
    _make_module("google.adk.models.lite_llm", LiteLlm=MagicMock)
    _make_module("litellm", completion=AsyncMock())

MOCK_DATA_DIR = BACKEND_ROOT / "mock_data"


@pytest.fixture(scope="session")
def tax_rules():
    with open(MOCK_DATA_DIR / "tax_rules_2025.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_accounts():
    with open(MOCK_DATA_DIR / "accounts.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_transactions():
    with open(MOCK_DATA_DIR / "transactions.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_payables():
    with open(MOCK_DATA_DIR / "invoices_payable.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_receivables():
    with open(MOCK_DATA_DIR / "invoices_receivable.json") as f:
        return json.load(f)
