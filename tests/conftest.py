"""Shared test setup — runs before any test module is imported.

brain.py constructs the Anthropic client at import time, and test_nudge.py's
import chain (nudge -> telegram_io -> brain) reaches it. Give the import
graph harmless dummy keys so the suite runs on machines with no .env (CI).
Because load_dotenv() never overrides existing env vars, these dummies also
win over the real .env during a test run — so if a test ever accidentally
made a live API call, it would fail loudly instead of spending real money.
"""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy-key")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-dummy-key")
