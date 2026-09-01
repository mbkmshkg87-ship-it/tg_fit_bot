import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]
DB_PATH = os.getenv("DB_PATH", "fitbot.db")
TZ = ZoneInfo(os.getenv("TZ", "Europe/Moscow"))
WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
