import os
from pathlib import Path

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8812724251:AAFPMF3BcrF1drjCrzOL0OshDRfVWG1akU0")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "1364476174,8455570642").split(",")]
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"

ORDER_FEE = 0  # COMPLETELY FREE - no extra charge (was 5, removed per requirement)
WALLET_MIN = 1
WALLET_MAX = 500

# VC Payment Gateway - kept for wallet topup only, checkout uses seller UPI directly
GW_API_KEY = "PAY3C0023FD16FC822035173195"
GW_UPI_ID = "paytm.s1dw5n0@pty"  # NOT used for checkout anymore - sellerUPI from product is used
GW_UPI_NAME = "Payment Gateway"
GW_VERIFY_URL = "https://api.vcpayment.in/api/verify"
GW_MERCHANT_ID = os.environ.get("GW_MERCHANT_ID", "")
