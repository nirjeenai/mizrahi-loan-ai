"""Runtime configuration — read once from backend/.env and the environment."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    model_extract: str
    model_judge: str
    model_agent: str
    max_llm_calls_per_hour: int
    review_provider: str
    mcp_keys: dict[str, str]
    visiontrace_mcp_url: str
    visiontrace_mcp_key: str
    data_dir: Path
    frontend_dist: Path
    simulation_date: str
    rubrics_dir: Path
    session_ttl_minutes: int
    demo_identity: bool
    demo_reset: bool
    onboarding_llm: bool
    onboarding_llm_model: str
    onboarding_llm_timeout: float

    @property
    def db_path(self) -> Path:
        return self.data_dir / "mortgage_case_service.sqlite3"

    @property
    def main_data(self) -> bool:
        """The default DATA_DIR (backend/data): the user's own instance. Isolated stacks and tests set DATA_DIR."""
        return self.data_dir.resolve() == (BACKEND_DIR / "data").resolve()

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def renders_dir(self) -> Path:
        return self.data_dir / "renders"

    @property
    def session_secret(self) -> bytes:
        """SESSION_SECRET, or a random secret kept in DATA_DIR (created once, 0600) so sessions survive restarts."""
        if os.environ.get("SESSION_SECRET"):
            return os.environ["SESSION_SECRET"].encode()
        path = self.data_dir / "session_secret"
        if not path.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(secrets.token_hex(32), encoding="utf8")
            path.chmod(0o600)
        return path.read_text(encoding="utf8").strip().encode()


def _mcp_keys() -> dict[str, str]:
    keys = {}
    if os.environ.get("MCP_DEMO_KEY"):
        keys[os.environ["MCP_DEMO_KEY"]] = "DEMO-MTZ-2026-001"
    if os.environ.get("MCP_DEMO_KEY_2"):
        keys[os.environ["MCP_DEMO_KEY_2"]] = "DEMO-MTZ-2026-002"
    return keys


settings = Settings(
    gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
    model_extract=os.environ.get("GEMINI_MODEL_EXTRACT", "gemini-3.8-flash"),
    model_judge=os.environ.get("GEMINI_MODEL_JUDGE", "gemini-3.8-flash"),
    model_agent=os.environ.get("GEMINI_MODEL_AGENT", "gemini-3.8-flash"),
    max_llm_calls_per_hour=int(os.environ.get("GEMINI_MAX_CALLS_PER_HOUR", "400")),
    review_provider=os.environ.get("REVIEW_PROVIDER", "gemini"),
    mcp_keys=_mcp_keys(),
    visiontrace_mcp_url=os.environ.get("VISIONTRACE_MCP_URL", ""),
    visiontrace_mcp_key=os.environ.get("VISIONTRACE_MCP_KEY", ""),
    data_dir=Path(os.environ.get("DATA_DIR", str(BACKEND_DIR / "data"))),
    frontend_dist=PROJECT_DIR / "frontend" / "dist",
    simulation_date=os.environ.get("SIMULATION_DATE", "2026-10-12"),
    rubrics_dir=BACKEND_DIR / "rubrics",
    session_ttl_minutes=int(os.environ.get("SESSION_TTL_MINUTES", "480")),
    # demo conveniences, on by default in this concept demo; set to 0 outside a demo (see app/auth.py)
    demo_identity=os.environ.get("DEMO_IDENTITY", "1") == "1",
    demo_reset=os.environ.get("DEMO_RESET", "1") == "1",
    # conversational questionnaire (V2): Gemini on by default (with a key), no call quota; ONBOARDING_LLM=0 turns it off
    onboarding_llm=os.environ.get("ONBOARDING_LLM", "1") == "1",
    onboarding_llm_model=os.environ.get("ONBOARDING_LLM_MODEL", os.environ.get("GEMINI_MODEL_AGENT", "gemini-3.8-flash")),
    onboarding_llm_timeout=float(os.environ.get("ONBOARDING_LLM_TIMEOUT", "8")),
)
