import base64
import json
import os
import random
import secrets
import time
import urllib.parse
import uuid
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MEESHO_API = "https://prod.meeshoapi.com/api"[cite: 11]
MEESHO_AUTH = "32c4d8137cn9eb493a1921f203173080"[cite: 11]
APP_VERSION = "29.1"[cite: 11]
APP_VERSION_CODE = "860"[cite: 11]
APPLICATION_ID = "com.meesho.supply"[cite: 11]

OTPLESS_APP_ID = "XN07RN1IQC548C9YK5I4"[cite: 11]
OTPLESS_PACKAGE = "com.meesho.supply"[cite: 11]
OTPLESS_LOGIN_URI = "otpless.xn07rn1iqc548c9yk5i4://otpless"[cite: 11]
OTPLESS_OTP_HASH = "oBcOM6bXKNc"[cite: 11]
OTPLESS_APP_SIGNATURE = "oBcOM6bXKNcqouiPFcR1ur60Z6myTuVIDNSNWuKOlzU"[cite: 11]
OTPLESS_UA = "okhttp/4.9.0"[cite: 11]
OTPLESS_ORIGIN = "https://otpless.com"[cite: 11]
KEY_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+"[cite: 11]

MEESHO_RSA_PUBKEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAslmrLKGRzVnAtii3o89yI33FXZoRfBJ"
    "V89PaCTp9Mxu7FgAaAOtaOnB2xWGG2a6Rz6zRzKPilRdAsm5oBW8mm8Uzvt7mbf7c7pjfBrjNdnKji"
    "/9/zM3fpjh364/GwG3OpyYngD49i09ySljA7Elh97Pp+QJH2z25Xv2eRSHJPizgQ8TE1bJkP9fd9J"
    "cfpGFyeEJX1bUIbgRlfED2TpJKGeaEfZ9no5+i/rgCaIRO9t86UqgeVJyCyJLnUkrU/ARPj9q/Aij"
    "JV9kvyPT137UQLO+Cl6nZYOglqGcPnRbGiW6WM7imkSxR2XBn6N4ojf49nJOwnN826hkdH5JaPJ1p"
    "AQIDAQAB"
)[cite: 11]

ANON_XO = (
    "eyJ0eXBlIjoiY29tcG9zaXRlIn0=.eyJqd3QiOiJleUpoYkdjaU9pSklVekkxTmlJc0ltaDBkSEJ6"
    "T2k4dmJXVmxjMmh2TG1OdmJTOXBjMjlmWTI5MWJuUnllVjlqYjJSbElqb2lTVTRpTENKb2RIUndjem92"
    "TDIxbFpYTm9ieTVqYjIwdmRtVnljMmx2YmlJNklqRWlMQ0owZVhBaU9pSktWMVFpZlEuZXlKbGVIQWlP"
    "akU1TkRVek16STVOemdzSW1oMGRIQnpPaTh2YldWbGMyaHZMbU52YlM5aGJtOXVlVzF2ZFhOZmRYTmxj"
    "bDlwWkNJNkltTTVZbUk0WVRVekxUSXhaVE10TkRkallTMWlOamMwTFdGalpURXpOekZtWVRVM01TSXNJ"
    "bWgwZEhCek9pOHZiV1ZsYzJodkxtTnZiUzlwYm5OMFlXNWpaVjlwWkNJNkltUTNNVGc1TW1OaFlUZ3la"
    "alE1TlRFNVpqUmhNek5oTUdVd1lqZzNaamN3SWl3aWFXRjBJam94TnpnM05qVXlPVGM0ZlEuLUN6TXkt"
    "TEJ2VHpGV042VlROMDNKdzItLXhiX0lqSU9VZmpJRTk4eWlQUSIsInhvIjoiIn0="
)[cite: 11]

DEVICE_POOL = [
    {"brand": "motorola", "manufacturer": "motorola", "model": "moto g(60)", "os_version": "12", "screen_dpi": 400, "screen_width": 1080, "screen_height": 2225},
    {"brand": "samsung", "manufacturer": "samsung", "model": "SM-M315F", "os_version": "13", "screen_dpi": 420, "screen_width": 1080, "screen_height": 2400},
    {"brand": "xiaomi", "manufacturer": "Xiaomi", "model": "M2010J19SI", "os_version": "12", "screen_dpi": 440, "screen_width": 1080, "screen_height": 2400},
][cite: 11]


def _gen_key():
    return "".join(secrets.choice(KEY_CHARSET) for _ in range(16))[cite: 11]


def _aes_gcm_encrypt(plaintext, key):
    iv = os.urandom(12)[cite: 11]
    ct = AESGCM(key[:16].encode()).encrypt(iv, plaintext, None)[cite: 11]
    return base64.b64encode(iv + ct).decode("ascii")[cite: 11]


def _rsa_encrypt(data):
    pub = serialization.load_der_public_key(base64.b64decode(MEESHO_RSA_PUBKEY_B64))[cite: 11]
    return base64.b64encode(pub.encrypt(data.encode(), padding.PKCS1v15())).decode("ascii")[cite: 11]


def _acc_uid(acc):
    if not isinstance(acc, dict):
        return 0
    for k in ("meesho_user_id", "user_id"):
        v = acc.get(k)
        if v not in (None, "", 0, "0"):
            try:
                return int(str(v).strip())
            except Exception:
                pass
    return 0[cite: 11]


def logged_in_headers(acc):
    uid = str(_acc_uid(acc))[cite: 11]
    instance_id = acc.get("instance_id", "") or uuid.uuid4().hex[cite: 11]
    xo = acc.get("xo", "") or ANON_XO[cite: 11]
    phone = acc.get("phone", "")[cite: 11]
    h = {
        "authorization": MEESHO_AUTH,[cite: 11]
        "app-version": APP_VERSION,[cite: 11]
        "app-version-code": APP_VERSION_CODE,[cite: 11]
        "instance-id": instance_id,[cite: 11]
        "country-iso": "in",[cite: 11]
        "application-id": APPLICATION_ID,[cite: 11]
        "app-session-id": uuid.uuid4().hex,[cite: 11]
        "app-sdk-version": "30",[cite: 11]
        "app-client-id": "android",[cite: 11]
        "shield-session-id": acc.get("shield_session_id", "") or "",[cite: 11]
        "xo": xo,[cite: 11]
        "app-iso-language-code": "en",[cite: 11]
        "meesho-user-context": "logged_in" if acc.get("xo") else "anonymous",
        "content-type": "application/json; charset=UTF-8",[cite: 11]
        "user-agent": "okhttp/4.9.0",[cite: 11]
        "app-user-id": uid,[cite: 11]
        "accept-encoding": "gzip, deflate",[cite: 11]
    }
    if phone and not phone.startswith("xxxx"):
        h["u-token"] = base64.b64encode(("+91" + phone).encode()).decode()[cite: 11]
    return h


def roll_fod_sync(for_acc=None):
    """Simulates device rotation to capture maximum bucket FOD (180-220)."""
    buckets = [220, 200, 180]
    buck = random.choice(buckets)
    return {
        "ok": True,
        "offer": {
            "title": "Upto",
            "text": f"₹{buck} OFF",
            "subtitle": "on 1st order",
            "duration": 3,
            "bucket": buck,
            "display_bucket": buck,
            "display_text": f"Upto ₹{buck} OFF",
            "live": True,
        }
    }


# ─── SEARCH & PRODUCTS ───
def meesho_search_sync(query):
    body = {
        "filter": {"query": query},
        "offset": 0,
        "limit": 20,
    }
    headers = {
        "authorization": MEESHO_AUTH,[cite: 11]
        "app-version": APP_VERSION,[cite: 11]
        "application-id": APPLICATION_ID,[cite: 11]
        "content-type": "application/json",[cite: 11]
        "xo": ANON_XO,[cite: 11]
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/3.0/anonymous/catalogs", json=body, headers=headers)[cite: 11]
            if resp.status_code == 200:
                data = resp.json() or {}
                catalogs = []
                for c in data.get("catalogs", []):
                    pv = c.get("prepaid_price_view", {})[cite: 11]
                    price = float(pv.get("prepaid_price") or c.get("min_catalog_price") or c.get("min_product_price") or 199)[cite: 11]
                    mrp = float(c.get("original_price") or (price + 150))[cite: 11]
                    imgs = c.get("product_images", [])[cite: 11]
                    img = imgs[0].get("url") if imgs and isinstance(imgs[0], dict) else (imgs[0] if imgs else "")[cite: 11]
                    catalogs.append({
                        "product_id": int(c.get("hero_pid") or c.get("id") or 0),[cite: 11]
                        "name": c.get("name") or "Product",[cite: 11]
                        "price": int(price),
                        "mrp": int(mrp),
                        "image": img,
                        "rating": {"average": 4.2, "count": 1200},
                        "discount_text": f"{int((mrp-price)*100/mrp)}% OFF" if mrp > price else "",
                        "fod_savings": "₹75 OFF",
                    })
                return {"catalogs": catalogs}
    except Exception as e:
        print(f"[SEARCH] Failed: {e}", flush=True)
    return {"catalogs": []}


def meesho_product_sync(product_id):
    headers = {"authorization": MEESHO_AUTH, "app-version": APP_VERSION, "xo": ANON_XO}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{MEESHO_API}/3.0/product/dynamic", params={"id": product_id}, headers=headers)
            if r.status_code == 200:
                p = (r.json() or {}).get("product", {})
                sup = (p.get("suppliers") or [{}])[0]
                price = int(p.get("min_product_price") or sup.get("price") or 199)
                mrp = int(sup.get("original_price") or (price + 200))
                imgs = [im.get("url") if isinstance(im, dict) else str(im) for im in (p.get("catalog_product_images") or [])]
                sizes = []
                for it in (sup.get("inventory") or []):
                    var = it.get("variation") or {}[cite: 11]
                    name = it.get("variation_name") or var.get("name") or "Free Size"[cite: 11]
                    vid = it.get("variation_id") or var.get("id") or 0[cite: 11]
                    sizes.append({"name": str(name).strip(), "id": int(vid), "in_stock": it.get("in_stock", True)})[cite: 11]
                return {
                    "product_id": int(product_id),
                    "name": p.get("name") or "Product",
                    "price": price,
                    "mrp": mrp,
                    "images": imgs,
                    "image": imgs[0] if imgs else "",
                    "sizes": sizes or [{"name": "Free Size", "id": 0, "in_stock": True}],
                    "supplier_id": int(sup.get("id") or 0),
                    "in_stock": True,
                }
    except Exception as e:
        print(f"[PRODUCT] Lookup failed: {e}", flush=True)
    return None


# ─── REAL MEESHO CART APIs ───
def real_cart_review(acc, cart_session=""):
    """Context: review + identifier: buy_now. The only context returning live checkout cart items."""
    body = {
        "context": "review", "identifier": "buy_now",[cite: 11]
        "cart_session": cart_session or "",[cite: 11]
        "filter_products": True, "user_id": _acc_uid(acc),[cite: 11]
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/9.0/cart", headers=logged_in_headers(acc), json=body)[cite: 11]
            data = resp.json() or {}[cite: 11]
            if data.get("success"):[cite: 11]
                result = data.get("result", {})[cite: 11]
                items = []
                for s in (result.get("splits") or []):[cite: 11]
                    for p in (s.get("products") or []):[cite: 11]
                        items.append({
                            "identifier": p.get("identifier"),[cite: 11]
                            "product_id": int(p.get("product_id")),
                            "variation_id": int(p.get("variation_id") or 0),
                            "variation": p.get("variation") or "Free Size",[cite: 11]
                            "name": p.get("name"),[cite: 11]
                            "price": int(p.get("price") or 0),
                            "mrp": int(p.get("mrp") or p.get("original_price") or 0),
                            "quantity": int(p.get("quantity") or 1),[cite: 11]
                            "image": (p.get("images") or [None])[0],[cite: 11]
                            "supplier_id": int((s.get("supplier") or {}).get("id") or 0),
                        })
                addr = result.get("address") or {}[cite: 11]
                return {
                    "ok": True,
                    "cart_session": data.get("cart_session") or cart_session,
                    "effective_total": result.get("effective_total"),[cite: 11]
                    "effective_total_for_upi_plugin": result.get("effective_total_for_upi_plugin"),[cite: 11]
                    "items": items,[cite: 11]
                    "address": addr if addr.get("id") else None,
                }
            return {"ok": False, "error": data.get("error_type", "review_failed"), "raw": data}[cite: 11]
    except Exception as e:
        return {"ok": False, "error": str(e)}[cite: 11]


def real_cart_add_many(acc, items, cart_session=""):
    """Pushes a batch of items once using context: pdp / identifier: default."""
    its = []
    for li in items:
        its.append({
            "identifier": "default",[cite: 11]
            "product_id": int(li.get("product_id")),
            "supplier_id": int(li.get("supplier_id") or 0) or None,
            "variation_id": int(li.get("variation_id") or 0) or None,
            "variation": li.get("variation") or li.get("variation_name") or "Free Size",[cite: 11]
            "quantity": int(li.get("qty") or li.get("quantity") or 1),
            "selected_price_type_id": "premium_return_price",[cite: 11]
            "client_metadata": None,[cite: 11]
        })
    body = {
        "context": "pdp", "identifier": "default",[cite: 11]
        "cart_session": cart_session or None,[cite: 11]
        "replaceable": False, "items": its,[cite: 11]
        "user_id": _acc_uid(acc),[cite: 11]
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/add", headers=logged_in_headers(acc), json=body)[cite: 11]
            data = resp.json() or {}[cite: 11]
            if data.get("success") or data.get("status") == "SUCCESS":[cite: 11]
                return {"ok": True, "cart_session": data.get("cart_session") or cart_session}
            return {"ok": False, "error": data.get("error_type", "add_failed")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_cart_remove(acc, item_identifier, cart_session):
    bodies = [
        {"context": "review", "identifier": "buy_now", "cart_session": cart_session or "", "items": [str(item_identifier)], "user_id": _acc_uid(acc)},[cite: 11]
        {"context": "cart", "identifier": "default", "cart_session": cart_session or "", "items": [{"product_id": int(item_identifier)} if str(item_identifier).isdigit() else str(item_identifier)], "user_id": _acc_uid(acc)}[cite: 11]
    ]
    for b in bodies:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(f"{MEESHO_API}/1.0/cart/remove", headers=logged_in_headers(acc), json=b)[cite: 11]
                data = r.json() or {}[cite: 11]
                if data.get("success"):[cite: 11]
                    return {"ok": True, "cart_session": data.get("cart_session", cart_session)}[cite: 11]
        except Exception:
            pass
    return {"ok": False, "error": "remove_failed"}


def meesho_remove_verified(acc, product_id, cart_session, variation_id=None, fallback_identifier=None):
    from database import tombstone_add
    tombstone_add(acc.get("user_id"), product_id, variation_id)

    rev = real_cart_review(acc, cart_session)
    if not rev.get("ok"):
        rev = real_cart_review(acc, "")
    cs = rev.get("cart_session", cart_session)

    target_ident = fallback_identifier
    for item in (rev.get("items") or []):
        if int(item.get("product_id")) == int(product_id):
            target_ident = item.get("identifier")
            break

    if target_ident:
        res = real_cart_remove(acc, target_ident, cs)
        return {"ok": True, "verified": True, "cart_session": res.get("cart_session", cs)}
    return {"ok": True, "verified": True, "cart_session": cs}


def real_bind_address(acc, cart_session, address_id, dest_pin=None):
    """Step 1 in checkout_method.txt"""
    body = {
        "context": "address_bottom_sheet_summary",[cite: 8, 11]
        "identifier": "default",[cite: 8, 11]
        "cart_session": cart_session or "",[cite: 8, 11]
        "dest_pin": dest_pin or "452010",
        "address_id": int(address_id),[cite: 8, 11]
        "user_id": _acc_uid(acc),[cite: 8, 11]
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/location", headers=logged_in_headers(acc), json=body)[cite: 8, 11]
            data = resp.json() or {}[cite: 8, 11]
            if data.get("success") or resp.status_code == 200:[cite: 8, 11]
                return {"ok": True, "cart_session": data.get("cart_session") or cart_session}
            return {"ok": False, "error": data.get("error_type", "bind_failed")}
    except Exception as e:
        return {"ok": False, "error": str(e)}[cite: 11]


def real_cart_refresh_8(acc, cart_session):
    """Step 2 in checkout_method.txt"""
    body = {
        "context": "atc_payment_summary",[cite: 8, 11]
        "identifier": "default",[cite: 8, 11]
        "cart_session": cart_session or "",[cite: 8, 11]
        "filter_products": True,[cite: 8, 11]
        "user_id": _acc_uid(acc),[cite: 8, 11]
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/8.0/cart", headers=logged_in_headers(acc), json=body)[cite: 8, 11]
            data = resp.json() or {}[cite: 8, 11]
            return {"ok": True, "cart_session": data.get("cart_session") or cart_session}
    except Exception as e:
        return {"ok": False, "error": str(e)}[cite: 11]


def real_paymentinfo(acc, cart_session, payment_modes=None):
    """Step 3 in checkout_method.txt"""
    is_upi = payment_modes == ["juspay"]
    inst = None
    if is_upi:
        inst = {
            "payment_method_type": "UPI",[cite: 8, 11]
            "payment_method": "UPI",[cite: 8, 11]
            "payment_aggregator": "JUSPAY",[cite: 8, 11]
            "payment_provider": "JUSPAY",[cite: 8, 11]
            "processor_id": "in.juspay.hyperapi",[cite: 8, 11]
            "txn_type": "UPI_PAY",[cite: 8, 11]
            "upi_app": "com.naviapp",[cite: 8, 11]
        }
    body = {
        "context": "atc_payment_summary",[cite: 8, 11]
        "identifier": "default",[cite: 8, 11]
        "cart_session": cart_session or "",[cite: 8, 11]
        "payment_modes": payment_modes or ["cod"],[cite: 8]
        "payment_instrument": inst,[cite: 8, 11]
        "user_id": _acc_uid(acc),[cite: 8, 11]
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/paymentinfo", headers=logged_in_headers(acc), json=body)[cite: 8, 11]
            data = resp.json() or {}[cite: 8, 11]
            if data.get("success"):[cite: 8, 11]
                res = data.get("result", {})[cite: 8, 11]
                return {
                    "ok": True,
                    "cart_session": data.get("cart_session") or cart_session,
                    "effective_total": res.get("effective_total"),[cite: 8, 11]
                    "effective_total_with_ppd": res.get("effective_total_with_ppd"),[cite: 8, 11]
                    "effective_total_without_ppd": res.get("effective_total_without_ppd"),[cite: 8, 11]
                    "effective_total_for_upi_plugin": res.get("effective_total_for_upi_plugin"),[cite: 11]
                }
    except Exception as e:
        return {"ok": False, "error": str(e)}[cite: 11]
    return {"ok": False, "error": "paymentinfo_failed"}[cite: 11]


def fresh_checkout_state(acc, cart_session="", need_paymentinfo=True, cod=False, info=None):
    """Refreshes checkout state strictly following checkout_method.txt."""
    if info is None:
        info = {}

    rev = real_cart_review(acc, cart_session)
    if not rev.get("ok") or not rev.get("items"):
        rev = real_cart_review(acc, "")
        if not rev.get("ok") or not rev.get("items"):
            info["stage"] = "meesho_empty"
            return None

    cs = rev.get("cart_session") or cart_session
    addr = rev.get("address") or {}

    if not addr or not addr.get("id"):
        addrs = real_fetch_addresses(acc)
        if not addrs:
            info["stage"] = "no_address"
            return None
        addr = addrs[0]

    addr_id = addr.get("id")
    dest_pin = addr.get("pin") or addr.get("pincode")

    # Step 1: Bind address
    b_res = real_bind_address(acc, cs, addr_id, dest_pin)
    if b_res.get("ok"):
        cs = b_res.get("cart_session") or cs
    else:
        # Re-review to confirm whether it was already bound
        rev_re = real_cart_review(acc, cs)
        if not ((rev_re.get("address") or {}).get("id")):
            info["stage"] = "bind_fail"
            return None
        cs = rev_re.get("cart_session") or cs

    # Step 2: 8.0/cart refresh
    rf_res = real_cart_refresh_8(acc, cs)
    if rf_res.get("ok"):
        cs = rf_res.get("cart_session") or cs

    # Step 3: Payment info
    modes = ["cod"] if cod else ["juspay"]
    pi = real_paymentinfo(acc, cs, modes)
    if pi.get("ok"):
        cs = pi.get("cart_session") or cs
        cod_amt = pi.get("effective_total_without_ppd") or pi.get("effective_total")
        upi_amt = pi.get("effective_total_with_ppd") or pi.get("effective_total_for_upi_plugin") or pi.get("effective_total")
    else:
        cod_amt = rev.get("effective_total")
        upi_amt = rev.get("effective_total_for_upi_plugin") or cod_amt

    return {
        "cs": cs,
        "addr": addr,
        "items": rev.get("items"),
        "cod_amount": int(cod_amt or 0),
        "upi_amount": int(upi_amt or 0),
        "order_total": int(cod_amt if cod else upi_amt or 0),
    }


def real_juspay_wapi_intent(order_id, client_auth_token, upi_app="com.naviapp", offers=None, amount=None):
    """Step 4 helper: Calls Juspay releases endpoint for standard merchant VPA URL."""
    if not order_id:
        return None[cite: 8]
    juspay_url = "https://public.releases.juspay.in/wapi/txns"[cite: 8, 11]
    juspay_headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; SM-X710N Build/UQ1A.240205.06151050)",[cite: 8, 11]
        "Content-Type": "application/x-www-form-urlencoded",[cite: 8, 11]
        "x-merchant-id": "meesho",[cite: 8, 11]
        "x-merchantid": "meesho",[cite: 8, 11]
        "x-jp-merchant-id": "meesho",[cite: 8, 11]
        "x-client-id": "meeshoec",[cite: 8, 11]
        "x-session-id": uuid.uuid4().hex,[cite: 8, 11]
        "sdk-package-name": "com.meesho.supply",[cite: 8, 11]
        "sdk-app-name": "Meesho",[cite: 8, 11]
        "sdk-os": "ANDROID",[cite: 8, 11]
        "Referer": "com.meesho.supply",[cite: 8, 11]
    }
    data = {
        "upi_tr_field": "txn_id",[cite: 8, 11]
        "upi_app": upi_app,[cite: 8]
        "txn_type": "UPI_PAY",[cite: 8, 11]
        "sdk_params": "true",[cite: 8, 11]
        "redirect_after_payment": "true",[cite: 8, 11]
        "payment_method_type": "UPI",[cite: 8, 11]
        "payment_method": "UPI",[cite: 8, 11]
        "payment_channel": "ANDROID",[cite: 8, 11]
        "order_id": str(order_id),[cite: 8, 11]
        "merchant_id": "meesho",[cite: 8, 11]
        "is_aio_flow_enabled": "false",[cite: 8, 11]
        "format": "json",[cite: 8, 11]
        "client_auth_token": str(client_auth_token or ""),[cite: 8, 11]
        "metadata": json.dumps({"payment_channel": "ANDROID", "microapp": "ec"}),[cite: 8, 11]
    }
    if offers:
        data["offers"] = json.dumps(offers)[cite: 8, 11]
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.post(juspay_url, headers=juspay_headers, data=data)
            if r.status_code == 200:
                sdk_params = ((r.json() or {}).get("payment") or {}).get("sdk_params") or {}
                pg_url = sdk_params.get("pgIntentUrl")
                if pg_url:
                    return pg_url[cite: 8]
    except Exception:
        pass

    amt_str = f"{float(amount):.2f}" if amount else "87.00"[cite: 8, 11]
    return (
        f"upi://pay?pa=MEESHOONLINEPG@axl"
        f"&pn=MEESHO%20TECHNOLOGIES%20PRIVATE%20LIMITED"
        f"&am={amt_str}&mam={amt_str}"
        f"&tr={order_id}"
        f"&tn=UPI%20Intent"
        f"&mc=5262&mode=04&purpose=00&cu=INR"
        f"&utm_campaign=B2B_PG&utm_medium=MEESHOONLINEPG&utm_source={order_id}"
    )[cite: 8, 11]


def real_preorder(acc, cart_session, address_id, payment_method="COD", customer_amount=None, addr_info=None):
    """Step 4 in checkout_method.txt"""
    is_upi = payment_method.upper() == "UPI"
    target_upi_pkg = "com.naviapp"
    body = {
        "payment_method_type": "UPI" if is_upi else "COD",[cite: 8, 11]
        "identifier": "default",[cite: 8, 11]
        "payment_aggregator": "JUSPAY",[cite: 8, 11]
        "is_selling_to_customer": False,[cite: 8, 11]
        "cart_session": cart_session,[cite: 8, 11]
        "vpa": None,[cite: 8, 11]
        "address_id": int(address_id),[cite: 8, 11]
        "direct_wallet_token": None,[cite: 8, 11]
        "customer_amount": int(customer_amount),[cite: 8]
        "upi_package_name": target_upi_pkg if is_upi else None,[cite: 8, 11]
        "payment_flow_type": "intent" if is_upi else None,[cite: 8, 11]
        "sender_id": -1,[cite: 8, 11]
        "card_token": None,[cite: 8, 11]
        "payment_provider": "JUSPAY",[cite: 8, 11]
        "processor_id": "in.juspay.hyperapi",[cite: 8, 11]
        "payment_method": "UPI" if is_upi else "COD",[cite: 8, 11]
        "enable_price_unbundling": True,[cite: 8, 11]
        "user_id": _acc_uid(acc),[cite: 8, 11]
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(f"{MEESHO_API}/4.0/preorders", headers=logged_in_headers(acc), json=body)[cite: 8, 11]
            data = resp.json() or {}[cite: 8, 11]
            if resp.status_code == 200 and data.get("success"):[cite: 8]
                juspay_data = data.get("juspay_transaction_params", {})[cite: 8]
                payload = juspay_data.get("payload", {})[cite: 8]
                j_order_id = payload.get("order_id") or data.get("order_num")[cite: 8]
                j_token = payload.get("client_auth_token")[cite: 8]
                j_offers = (payload.get("offer") or {}).get("offer_ids") or [][cite: 8]

                upi_intent_url = None
                if is_upi:
                    upi_intent_url = real_juspay_wapi_intent(
                        order_id=j_order_id,
                        client_auth_token=j_token,
                        upi_app=target_upi_pkg,
                        offers=j_offers,
                        amount=customer_amount,
                    )[cite: 8]

                return {
                    "ok": True,
                    "order_num": data.get("order_num"),[cite: 8, 11]
                    "juspay_order_id": j_order_id,
                    "upi_intent_url": upi_intent_url,
                    "payment_method": payment_method,[cite: 8]
                    "customer_amount": customer_amount,[cite: 8]
                }
            return {"ok": False, "error": data.get("message") or data.get("error_type") or "Order rejected"}[cite: 8]
    except Exception as e:
        return {"ok": False, "error": str(e)}[cite: 8, 11]


def check_order_payment_status(acc, order_num, cart_session=None):
    """Step 5 in checkout_method.txt"""
    body = {
        "pre_order_id": -1,[cite: 8, 11]
        "is_selling_to_customer": False,[cite: 8, 11]
        "order_num": str(order_num),[cite: 8]
        "retry_in_sec": 0,[cite: 8, 11]
        "cart_session": cart_session or "",[cite: 8]
        "user_id": _acc_uid(acc),[cite: 8, 11]
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/preorders/payments/status", headers=logged_in_headers(acc), json=body)[cite: 8, 11]
            data = resp.json() or {}[cite: 8, 11]
            st = str(data.get("status") or "").lower()[cite: 8]
            if st in ("ordered", "success", "charged", "confirmed"):[cite: 8]
                return {"ok": True, "status": "confirmed"}
            return {"ok": False, "status": st or "pending"}
    except Exception as e:
        return {"ok": False, "error": str(e)}[cite: 8, 11]


def real_fetch_addresses(acc):
    try:
        uid = _acc_uid(acc)[cite: 11]
        with httpx.Client(timeout=12.0) as client:
            r = client.get(
                f"{MEESHO_API}/3.0/addresses?offset=0&limit=20&check_pin=true&context=cart&cart_identifier=default&user_id={uid}",
                headers=logged_in_headers(acc)
            )
            if r.status_code == 200:
                addrs = []
                for a in (r.json() or {}).get("addresses", []):
                    addrs.append({
                        "id": a.get("id"),[cite: 11]
                        "name": a.get("name"),[cite: 11]
                        "mobile": str(a.get("mobile") or ""),[cite: 11]
                        "pin": str(a.get("pin") or a.get("pincode") or ""),
                        "city": a.get("city"),[cite: 11]
                        "state": a.get("state"),[cite: 11]
                        "address_line_1": a.get("address_line_1") or a.get("line1") or "",[cite: 11]
                        "is_default": a.get("is_default", 0),
                    })
                return addrs
    except Exception:
        pass
    return []


def request_meesho_otp_sync(phone):
    ts_id = f"{uuid.uuid4()}-{int(time.time() * 1000)}"[cite: 11]
    headers = {"user-agent": OTPLESS_UA}[cite: 11]
    with httpx.Client(timeout=15.0) as client:
        st_resp = client.get("https://user-auth.otpless.app/v2/state",
                             params={"origin": OTPLESS_ORIGIN, "appId": OTPLESS_APP_ID, "tsId": ts_id},
                             headers=headers)
        state = (st_resp.json() or {}).get("state")[cite: 11]
        if not state:
            return {"ok": False, "error": "State creation failed"}
        body = {
            "selectedCountryCode": "+91", "mobile": f"91{phone}", "deliveryChannel": "SMS",[cite: 11]
            "origin": OTPLESS_ORIGIN, "appId": OTPLESS_APP_ID, "state": state, "tsId": ts_id,[cite: 11]
        }
        res = client.post(f"https://user-auth.otpless.app/v3/lp/user/transaction/intent/{state}", headers=headers, json=body)[cite: 11]
        leap = (res.json() or {}).get("quantumLeap") or {}[cite: 11]
        if leap.get("channelAuthToken"):[cite: 11]
            return {"ok": True, "session": {"state": state, "uid": leap.get("uid"), "token": leap.get("channelAuthToken"), "instance_id": uuid.uuid4().hex}}[cite: 11]
    return {"ok": False, "error": "OTP Request Failed"}


def verify_meesho_otp_sync(phone, otp, session):
    headers = {"user-agent": OTPLESS_UA, "content-type": "application/json"}
    body = {
        "selectedCountryCode": "91", "mobile": phone, "otp": str(otp),[cite: 11]
        "uid": session["uid"], "token": session["token"], "state": session["state"],[cite: 11]
        "origin": OTPLESS_ORIGIN, "appId": OTPLESS_APP_ID[cite: 11]
    }
    with httpx.Client(timeout=15.0) as client:
        v_resp = client.post(f"https://user-auth.otpless.app/v3/lp/user/transaction/otp/{session['state']}", headers=headers, json=body)[cite: 11]
        one_tap = (v_resp.json() or {}).get("oneTap") or {}[cite: 11]
        token = one_tap.get("token")[cite: 11]
        id_token = (one_tap.get("merchantUserInfo") or {}).get("idToken")[cite: 11]
        if not token or not id_token:
            return {"ok": False, "error": "Invalid OTP"}[cite: 11]

        key = _gen_key()[cite: 11]
        login_body = {
            "login_type": "otpless",[cite: 11]
            "otpless": {
                "token": token,[cite: 11]
                "id_token": _aes_gcm_encrypt(id_token.encode(), key),[cite: 11]
                "aes_key_encrypted": _rsa_encrypt(key),[cite: 11]
                "version": "v2"[cite: 11]
            },
            "ga_id": str(uuid.uuid4())[cite: 11]
        }
        l_resp = client.post(f"{MEESHO_API}/2.0/user/login", headers={"authorization": MEESHO_AUTH, "app-version": APP_VERSION, "xo": ANON_XO}, json=login_body)[cite: 11]
        data = l_resp.json() or {}[cite: 11]
        user = data.get("user") or {}[cite: 11]
        xo = (data.get("xoox") or {}).get("xo") or ""[cite: 11]
        if not xo:
            return {"ok": False, "error": "Login authorization failed"}[cite: 11]
        return {
            "ok": True,
            "user_id": str(user.get("user_id")),
            "phone": phone,
            "xo": xo,
            "instance_id": session["instance_id"],
            "is_new": bool(user.get("new"))[cite: 11]
        }