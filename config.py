"""
config.py - Configuration constants for FOD Pilot
Brand Name: VIEDDETX SINGH
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"

# Brand and project
PROJECT_NAME = "FOD Pilot – Meesho First-Order Engine"
BRAND_NAME = "MEESHO ORDER BOT"

# Telegram Bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8812724251:AAFPMF3BcrF1drjCrzOL0OshDRfVWG1akU0")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "1364476174,8455570642").split(",") if x.strip()]
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

# ---------------------------------------------------------------------------
# WALLET SERVICE FEE & COMMISSION
# Note: This is your personal platform fee (₹5 per order) deducted from the
# user's bot wallet. It accumulates in the backend ledger and is NOT added
# to or deducted from the Meesho order total.
# ---------------------------------------------------------------------------
ORDER_FEE = int(os.environ.get("ORDER_FEE", 5))
WALLET_MIN = int(os.environ.get("WALLET_MIN", 1))
WALLET_MAX = int(os.environ.get("WALLET_MAX", 500))

# ---------------------------------------------------------------------------
# PAYMENT GATEWAY FOR WALLET RECHARGE (VC Gateway)
# Note: Wallet recharge goes to YOUR personal UPI ID, NOT Meesho's UPI.
# Meesho order checkout payments are handled separately via Juspay or COD.
# ---------------------------------------------------------------------------
GW_API_KEY = os.environ.get("GW_API_KEY", "PAY3C0023FD16FC822035173195")
# Replace with your actual personal UPI ID for receiving user wallet recharges:
GW_UPI_ID = os.environ.get("GW_UPI_ID", "your-upi@bank")
GW_UPI_NAME = os.environ.get("GW_UPI_NAME", "Order Bot Wallet")
GW_VERIFY_URL = os.environ.get("GW_VERIFY_URL", "https://vcgatewaypro.com/payment_api.php")

