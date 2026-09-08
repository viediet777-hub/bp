import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8773133018:AAEJoWff77I7k-6w4CA12g-SlOzPDSRbHuI")
    ADMIN_IDS: list = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "1364476174").split(",") if x.strip()]
    VC_API_KEY: str = os.getenv("VC_API_KEY", "PAY3C0023FD16FC822035173195")
    UPI_ID: str = os.getenv("UPI_ID", "paytm.s1dw5n0@pty")
    UPI_NAME: str = os.getenv("UPI_NAME", "VC Payment Gateway")
    FORCE_JOIN_CHANNEL: str = os.getenv("FORCE_JOIN_CHANNEL", "")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "bot" / "database" / "selling_bot.db"))

settings = Settings()
