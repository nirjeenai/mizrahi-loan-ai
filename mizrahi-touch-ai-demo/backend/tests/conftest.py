"""Every test runs against a throw-away data directory, set before any app module reads its settings,
so no test can touch backend/data. Gemini is disabled; tests that need a review insert it themselves."""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="mcs-tests-")
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_MAX_CALLS_PER_HOUR"] = "0"
