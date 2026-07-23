"""Repository-local paths for the AAIC 2026 ingestion workspace."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPOSITORY_ROOT / "data" / "aaic_2026"
REFRESH_DIR = DATA_DIR / "refreshes"
