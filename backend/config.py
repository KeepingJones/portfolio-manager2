import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

T212_MODE = os.getenv("T212_MODE", "demo")

if T212_MODE == "live":
    T212_API_KEY = os.getenv("T212_LIVE_API_KEY", "")
    T212_API_SECRET = os.getenv("T212_LIVE_API_SECRET", "")
    T212_BASE_URL = "https://live.trading212.com/api/v0"
else:
    T212_API_KEY = os.getenv("T212_DEMO_API_KEY", "")
    T212_API_SECRET = os.getenv("T212_DEMO_API_SECRET", "")
    T212_BASE_URL = "https://demo.trading212.com/api/v0"

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio.db")
