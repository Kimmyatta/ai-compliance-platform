import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    api_key: str
    model: str
    cors_origins: list[str]
    max_input_tokens: int = 4000
    max_completion_tokens: int = 3000


def load_settings(data_dir: Path | None = None) -> Settings:
    # Read only this application's env file; never load the parent's secrets implicitly.
    config = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    return Settings(
        data_dir=Path(data_dir or config.get("LEGAL_DATA_DIR") or PROJECT_ROOT / "data"),
        api_key=(config.get("GROQ_API_KEY") or "").strip(),
        model=config.get("LEGAL_MODEL") or "openai/gpt-oss-20b",
        cors_origins=(config.get("LEGAL_CORS_ORIGINS") or
                      "http://127.0.0.1:5175,http://localhost:5175").split(","),
        max_input_tokens=int(config.get("LEGAL_MAX_INPUT_TOKENS") or 4000),
        max_completion_tokens=int(config.get("LEGAL_MAX_COMPLETION_TOKENS") or 3000),
    )
