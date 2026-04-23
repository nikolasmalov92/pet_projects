import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

base_url = "https://api.ati.su"
loads_url = "https://loads.ati.su"

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))
access_token = os.getenv("ATI_TOKEN")
telegram_token = os.getenv("TELEGRAM_TOKEN")

geo_types = {"Страна": 0, "Регион": 1, "Город": 2}
headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

BASE_DIR = Path(__file__).resolve().parent

DB_NAME = BASE_DIR / "database.db"
processed_file = BASE_DIR / "processed.json"
api_car_types = BASE_DIR / "api_car_types.json"
api_loading_types = BASE_DIR / "api_loading_types.json"
