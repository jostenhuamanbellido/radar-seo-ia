"""Punto de entrada para Vercel (Python serverless). Reutiliza la misma app Flask."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401
