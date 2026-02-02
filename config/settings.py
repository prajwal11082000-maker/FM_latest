import os
from pathlib import Path

# Application settings
APP_NAME = "Warehouse Management System"
APP_VERSION = "1.0.0"

# API Configuration
API_BASE_URL = "http://127.0.0.1:8000/api"
API_TIMEOUT = 30
RETRY_ATTEMPTS = 3

# Data paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backup"
RESOURCES_DIR = BASE_DIR / "resources"

# CSV file paths
CSV_FILES = {
    'devices': DATA_DIR / "devices.csv",
    'tasks': DATA_DIR / "tasks.csv",
    'users': DATA_DIR / "users.csv",
    'maps': DATA_DIR / "maps.csv",
    'zones': DATA_DIR / "zones.csv",
    'stops': DATA_DIR / "stops.csv",
    'stop_groups': DATA_DIR / "stop_groups.csv",
    'racks': DATA_DIR / "racks.csv",
    'zone_alignment': DATA_DIR / "zone_alignment.csv",
    'products': DATA_DIR / "products.csv",
    'charging_zones': DATA_DIR / "charging_zones.csv",
}

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

WINDOW_SIZE = (1400, 900)
SIDEBAR_WIDTH = 60
EXPANDED_SIDEBAR_WIDTH = 200

# Refresh intervals (seconds)
DEVICE_STATUS_REFRESH = 5
TASK_STATUS_REFRESH = 3
AUTO_SYNC_INTERVAL = 30

# Theme settings
DEFAULT_THEME = "dark"
THEMES_DIR = RESOURCES_DIR / "styles"