"""Environment-based configuration. Works with zero credentials (local dev mode)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STARTER_DIR = PROJECT_ROOT / "source_files" / "extracted" / "CrunchWeek_StarterPack"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    # --- official source files (never modified by the app)
    dataset_path: Path = STARTER_DIR / "data" / "cit_public.json"
    validator_path: Path = STARTER_DIR / "validator.py"
    sample_disruption_path: Path = STARTER_DIR / "examples" / "sample_disruption.json"
    validator_sha256: str = ""  # optional pin; empty = do not check

    # --- app state / outputs
    state_dir: Path = PROJECT_ROOT / "backend" / "var"
    exports_dir: Path = PROJECT_ROOT / "exports"
    team_name: str = "Campus X"

    # --- solver
    solver_seed: int = 42
    solver_time_limit_s: int = 120
    solver_workers: int = 1

    # --- database (SQLite locally; Supabase PostgreSQL when DATABASE_URL is set)
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'backend' / 'var' / 'campusx.db'}"

    # --- auth. LOCAL mode is a labelled development stub, NOT production authentication.
    auth_mode: str = "local"  # local | supabase
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # Never expose a service-role key to the frontend; backend-only and optional.
    supabase_service_role_key: str = ""

    # LOCAL dev auth only. These demo accounts are NOT production authentication.
    demo_password: str = "campusx-demo"
    local_auth_secret: str = "dev-only-secret-change-me"

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
