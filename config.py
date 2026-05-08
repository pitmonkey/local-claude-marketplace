import os

from dotenv import load_dotenv

load_dotenv()

# Required — will raise KeyError if missing and not DRY_RUN
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

if not DRY_RUN:
    WEBHOOK_URL = os.environ["WEBHOOK_URL"]
