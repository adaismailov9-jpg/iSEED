"""Vercel entry point: serves the FastAPI app at /api/*."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from iseed.main import app  # noqa: E402,F401
