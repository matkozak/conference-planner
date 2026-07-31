"""Repository-local paths for the CTAD 2026 ingestion workspace."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = REPOSITORY_ROOT / "data" / "ctad_2026"
SOURCE_DIR = DATA_DIR / "source"
WORK_DIR = DATA_DIR / "work"
PROGRAM_CANDIDATE = REPOSITORY_ROOT / "app" / ".programs" / "ctad-2026.json"
OVERRIDES_FILE = PACKAGE_DIR / "overrides.json"
