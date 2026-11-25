import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEMO = ROOT / "demo"
CATALOGUE_CSV = DATA / "catalogue.csv"
ALIASES_JSON = DATA / "aliases.json"


def secret(name, default=None):
    """Read a setting from env vars, then from Streamlit secrets (Streamlit Cloud)."""
    v = os.getenv(name)
    if v:
        return v
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except Exception:
        return default


def api_key():
    return secret("OPENROUTER_API_KEY")


def model():
    return secret("ORDO_MODEL", "anthropic/claude-haiku-5.5")


# Fallback prices (USD per token) used only if OpenRouter does not return the cost.
PRICE_IN = float(secret("ORDO_PRICE_IN", "0.0000001"))
PRICE_OUT = float(secret("ORDO_PRICE_OUT", "0.0000005"))
