import hashlib
import json
import time
import urllib.parse
import requests
from config import GW_API_KEY, GW_UPI_ID, GW_UPI_NAME, GW_VERIFY_URL


def generate_txn_id(user_id):
    return f"ORD{user_id}{int(time.time())}"


def create_upi_link(txn_id, amount):
    params = {
        "pa": GW_UPI_ID,
        "pn": GW_UPI_NAME,
        "tid": txn_id,
        "tr": txn_id,
        "tn": "Payment",
        "am": str(amount),
        "cu": "INR",
    }
    return "upi://pay?" + urllib.parse.urlencode(params)


def get_qr_url(upi_link, size=400):
    encoded = urllib.parse.quote(upi_link, safe="")
    return (
        f"https://quickchart.io/qr"
        f"?text={encoded}"
        f"&size={size}"
        f"&margin=2"
        f"&ecLevel=H"
        f"&format=png"
    )


def verify_payment(txn_id):
    """Verify payment via VC Gateway API. Returns dict with status."""
    try:
        # Try standard verify endpoint
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GW_API_KEY}",
        }
        payload = {"txn_id": txn_id, "api_key": GW_API_KEY}
        resp = requests.post(GW_VERIFY_URL, json=payload, headers=headers, timeout=10)
        data = resp.json()
        return {
            "success": True,
            "status": data.get("status", ""),
            "amount": data.get("amount", 0),
            "txn_id": txn_id,
            "raw": data,
        }
    except Exception as e1:
        try:
            # Fallback: try query param style
            url = f"{GW_VERIFY_URL}?api_key={GW_API_KEY}&txn_id={txn_id}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return {
                "success": True,
                "status": data.get("status", ""),
                "amount": data.get("amount", 0),
                "txn_id": txn_id,
                "raw": data,
            }
        except Exception as e2:
            return {
                "success": False,
                "status": "error",
                "error": str(e2),
                "txn_id": txn_id,
            }


def auto_verify_loop(txn_id, callback, max_wait=120, interval=5):
    """Poll for payment confirmation. Calls callback(success, amount) when done."""
    start = time.time()
    while time.time() - start < max_wait:
        result = verify_payment(txn_id)
        status = str(result.get("status", "")).lower()
        if result["success"] and status in ("success", "completed", "captured", "paid", "1"):
            callback(True, result.get("amount", 0))
            return result
        time.sleep(interval)
    callback(False, 0)
    return {"success": False, "status": "timeout"}
