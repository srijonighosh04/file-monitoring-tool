import os
from pathlib import Path

# Base workspace directory
BASE_DIR = Path(__file__).resolve().parent

# Directory paths
DATABASE_DIR = BASE_DIR / "database"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"
ASSETS_DIR = BASE_DIR / "assets"

# File paths
DATABASE_PATH = DATABASE_DIR / "fim.db"
LOG_PATH = LOGS_DIR / "application.log"

# Scan settings
HASH_CHUNK_SIZE = 4096  # read 4096-byte chunks

# Ignore lists (system files, and our own DB/logs/reports folders to avoid circular scanning)
IGNORE_FILENAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "$RECYCLE.BIN",
    "fim.db",
    "application.log",
}

IGNORE_DIRNAMES = {
    ".git",
    ".github",
    "__pycache__",
    "database",
    "logs",
    "reports",
    "assets",
}

# GUI configuration
DEFAULT_THEME = "darkly"  # bootstrap theme (e.g. darkly, cosmo, flatly, superhero)
APP_TITLE = "File Integrity Monitoring (FIM) Tool"
APP_VERSION = "1.0.0"
