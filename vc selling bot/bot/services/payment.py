import requests
import urllib.parse
import time
from config.settings import settings

class VCPaymentGateway:
    API_URL = "https://vcapi.vcstore.site/payment_api.php"

    @staticmethod
    def create_order_id(user_id):
        """Exact BotHelp format: VC + timestamp + user_id"""
        return f"VC{int(time.time() * 1000)}{user_id}"

    @staticmethod
    def generate_qr_url(amount, order_id):
        """UPI URL banao aur QR code ka URL return karo"""
        upi_url = (
            "upi://pay?"
            f"pa={urllib.parse.quote(settings.UPI_ID)}"
            f"&pn={urllib.parse.quote(settings.UPI_NAME)}"
            f"&tid={urllib.parse.quote(order_id)}"
            f"&tr={urllib.parse.quote(order_id)}"
            f"&tn={urllib.parse.quote('VC Payment')}"
            f"&am={urllib.parse.quote(str(int(amount)))}"
            f"&cu=INR"
        )
        qr_url = (
            "https://quickchart.io/qr"
            f"?text={urllib.parse.quote(upi_url)}"
            "&size=800&margin=3&ecLevel=H"
        )
        return qr_url

    @staticmethod
    def check_payment(order_id, amount):
        """VC API se payment check karo - exact BotHelp jaisa"""
        api_key = settings.VC_API_KEY
        if not api_key:
            return {"status": "error", "message": "API Key not set"}

        url = (
            f"{VCPaymentGateway.API_URL}"
            f"?api_key={urllib.parse.quote(api_key)}"
            f"&order_id={urllib.parse.quote(str(order_id))}"
            f"&amount={urllib.parse.quote(str(int(amount)))}"
        )

        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()
            return data
        except Exception as e:
            return {"status": "error", "message": str(e)}
