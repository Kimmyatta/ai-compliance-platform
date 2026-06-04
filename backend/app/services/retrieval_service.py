from pathlib import Path

from backend.app.core.config import get_settings


def path_exists(path: Path):
    return path.exists()


def privacy_index_available():
    index_dir = get_settings().privacy_index_dir
    return path_exists(index_dir / "index.faiss") and path_exists(index_dir / "metadata.json")


def fda_guidance_index_available():
    index_dir = get_settings().fda_guidance_index_dir
    return path_exists(index_dir / "index.faiss") and path_exists(index_dir / "metadata.json")
