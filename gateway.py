"""
gateway.py - Payment & UPI Helpers
Handles wallet recharge verification via VC Gateway and dynamic UPI generation.

CRITICAL SEPARATION OF CONCERNS:
1. Wallet Recharge: User deposits funds to your personal UPI (GW_UPI_ID).
   Verified using the VC Gateway API.
2. Wallet Service Fee: Commission (ORDER_FEE = ₹5) deducted from internal wallet balance per order.
3. Meesho Order Payment: The customer pays Meesho directly (COD or Juspay UPI).
   User wallet balance is NEVER used to pay the Meesho order amount.
"""
import time
import urllib.parse
import json

try:
    import requests
except ImportError:
    requests = None

from config import GW_API_KEY, GW_UPI_ID, GW_UPI_NAME, GW_VERIFY_URL


def generate_txn_id(user_id):
    """Generates unique transaction ID for wallet recharge."""
    return f"FOD{user_id}{int(time.time())}"


def create_upi_link(txn_id, amount, vpa=None, name=None, note="Wallet Recharge"):
    """
    Creates dynamic UPI payment intent link.
    Defaults to your personal UPI ID (GW_UPI_ID) for wallet recharges.
    """
    pa = vpa or GW_UPI_ID
    pn = name or GW_UPI_NAME
    params = {
        "pa": pa,
        "pn": pn,
        "tid": txn_id,
        "tr": txn_id,
        "tn": note,
        "am": f"{float(amount):.2f}",
        "cu": "INR",
    }
    return "upi://pay?" + urllib.parse.urlencode(params)


def get_qr_url(upi_link, size=400):
    """Generates QR code image URL for a given UPI link."""
    if not upi_link:
        return ""
    encoded = urllib.parse.quote(upi_link, safe="")
    return (
        f"https://api.qrserver.com/v1/create-qr-code/"
        f"?size={size}x{size}"
        f"&margin=8"
        f"&data={encoded}"
    )


def get_qr_base64(upi_link, size=240):
    """Generates a base64 encoded data URI for the QR code if possible."""
    if not upi_link:
        return ""
    try:
        import urllib.request
        import base64
        url = get_qr_url(upi_link, size=size)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = resp.read()
            return f"data:image/png;base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return ""


def verify_payment(txn_id, amount=1):
    """
    Verifies wallet recharge payment via VC Gateway API.
    Endpoint: https://vcgatewaypro.com/payment_api.php?api_key={API_KEY}&order_id={ORDER_ID}&amount={AMOUNT}

    Returns:
        dict: {"success": bool, "status": str, "amount": float, "txn_id": str}
    """
    try:
        amt = int(float(amount)) if amount else 1
        url = f"{GW_VERIFY_URL}?api_key={GW_API_KEY}&order_id={txn_id}&amount={amt}"
        if requests is not None:
            resp = requests.get(url, timeout=10)
            data = resp.json()
        else:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "FOD-Pilot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

        status_str = str(data.get("status", "")).lower()
        if status_str in ("success", "completed", "paid", "true"):
            verified_amount = float(data.get("amount") or amt)
            return {
                "success": True,
                "status": "completed",
                "amount": verified_amount,
                "txn_id": txn_id,
                "raw": data,
            }
        return {
            "success": False,
            "status": data.get("status", "pending"),
            "error": data.get("message") or data.get("msg") or data.get("error") or "Payment pending or not confirmed",
            "amount": float(data.get("amount") or amt),
            "txn_id": txn_id,
            "raw": data,
        }
    except Exception as e:
        return {
            "success": False,
            "status": "pending",
            "error": str(e),
            "txn_id": txn_id,
        }

