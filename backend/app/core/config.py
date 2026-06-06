import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _parse_csv_env(value, default):
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    project_root: Path
    groq_api_key: str
    cors_origins: list[str]
    privacy_index_dir: Path
    fda_guidance_index_dir: Path


@lru_cache(maxsize=1)
def get_settings():
    return Settings(
        project_root=PROJECT_ROOT,
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip().strip("()\"'").strip(),
        cors_origins=_parse_csv_env(
            os.getenv("CORS_ORIGINS"),
            [
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:3000",
                "http://localhost:3000",
            ],
        ),
        privacy_index_dir=PROJECT_ROOT / "data" / "privacy" / "faiss_index",
        fda_guidance_index_dir=PROJECT_ROOT
        / "data"
        / "fda_ai"
        / "guidance"
        / "faiss_index",
    )


def require_groq_api_key():
    api_key = get_settings().groq_api_key
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env or the server environment.")
    return api_key
