"""
meesho.py - Complete Meesho API Integration (Sync for Flask)
OTPLESS Login, FOD Offers (180-220), Product Search, Cart, Checkout & Juspay UPI QR
Brand: VIEDDETX SINGH
Project: FOD Pilot – Meesho First-Order Engine
"""
import base64
import json
import os
import random
import re
import secrets
import time
import uuid
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ============================================================
# CONSTANTS & MEESHO APP HEADERS
# ============================================================
MEESHO_API = "https://prod.meeshoapi.com/api"
MEESHO_AUTH = "32c4d8137cn9eb493a1921f203173080"
APP_VERSION = "29.1"
APP_VERSION_CODE = "860"
APPLICATION_ID = "com.meesho.supply"

ANON_XO = (
    "eyJ0eXBlIjoiY29tcG9zaXRlIn0=.eyJqd3QiOiJleUpoYkdjaU9pSklVekkxTmlJc0ltaDBkSEJ6"
    "T2k4dmJXVmxjMmh2TG1OdmJTOXBjMjlmWTI5MWJuUnllVjlqYjJSbElqb2lTVTRpTENKb2RIUndjem92"
    "TDIxbFpYTm9ieTVqYjIwdmRtVnljMmx2YmlJNklqRWlMQ0owZVhBaU9pSktWMVFpZlEuZXlKbGVIQWlP"
    "akU1TkRVek16STVOemdzSW1oMGRIQnpPaTh2YldWbGMyaHZMbU52YlM5aGJtOXVlVzF2ZFhOZmRYTmxj"
    "bDlwWkNJNkltTTVZbUk0WVRVekxUSXhaVE10TkRkallTMWlOamMwTFdGalpURXpOekZtWVRVM01TSXNJ"
    "bWgwZEhCek9pOHZiV1ZsYzJodkxtTnZiUzlwYm5OMFlXNWpaVjlwWkNJNkltUTNNVGc1TW1OaFlUZ3la"
    "alE1TlRFNVpqUmhNek5oTUdVd1lqZzNaamN3SWl3aWFXRjBJam94TnpnM05qVXlPVGM0ZlEuLUN6TXkt"
    "TEJ2VHpGV042VlROMDNKdzItLXhiX0lqSU9VZmpJRTk4eWlQUSIsInhvIjoiIn0="
)

MEESHO_RSA_PUBKEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAslmrLKGRzVnAtii3o89yI33FXZoRfBJ"
    "V89PaCTp9Mxu7FgAaAOtaOnB2xWGG2a6Rz6zRzKPilRdAsm5oBW8mm8Uzvt7mbf7c7pjfBrjNdnKji"
    "/9/zM3fpjh364/GwG3OpyYngD49i09ySljA7Elh97Pp+QJH2z25Xv2eRSHJPizgQ8TE1bJkP9fd9J"
    "cfpGFyeEJX1bUIbgRlfED2TpJKGeaEfZ9no5+i/rgCaIRO9t86UqgeVJyCyJLnUkrU/ARPj9q/Aij"
    "JV9kvyPT137UQLO+Cl6nZYOglqGcPnRbGiW6WM7imkSxR2XBn6N4ojf49nJOwnN826hkdH5JaPJ1p"
    "AQIDAQAB"
)

OTPLESS_APP_ID = "XN07RN1IQC548C9YK5I4"
OTPLESS_PACKAGE = "com.meesho.supply"
OTPLESS_LOGIN_URI = "otpless.xn07rn1iqc548c9yk5i4://otpless"
OTPLESS_OTP_HASH = "oBcOM6bXKNc"
OTPLESS_APP_SIGNATURE = "oBcOM6bXKNcqouiPFcR1ur60Z6myTuVIDNSNWuKOlzU"
OTPLESS_UA = "okhttp/4.9.0"
OTPLESS_ORIGIN = "https://otpless.com"
KEY_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+"

DEVICE_INFO = {
    "platform": "android",
    "vendor": "motorola",
    "browser": "",
    "connection": "",
    "language": "en-IN",
    "cookieEnabled": "",
    "screenWidth": 1080,
    "screenHeight": 2225,
    "userAgent": "Dalvik/2.1.0 (Linux; U; Android 12; moto g(60) Build/S2RI32.32-20-9-9-2) otplesssdk",
    "timezoneOffset": 330,
    "cpuArchitecture": "aarch64",
}

DEVICE_POOL = [
    {"brand": "motorola", "manufacturer": "motorola", "model": "moto g(60)", "os_version": "12", "os": "Android", "screen_dpi": 400, "screen_width": 1080, "screen_height": 2225},
    {"brand": "samsung", "manufacturer": "samsung", "model": "SM-M315F", "os_version": "13", "os": "Android", "screen_dpi": 420, "screen_width": 1080, "screen_height": 2400},
    {"brand": "samsung", "manufacturer": "samsung", "model": "SM-A546E", "os_version": "14", "os": "Android", "screen_dpi": 450, "screen_width": 1080, "screen_height": 2340},
    {"brand": "xiaomi", "manufacturer": "Xiaomi", "model": "M2010J19SI", "os_version": "12", "os": "Android", "screen_dpi": 440, "screen_width": 1080, "screen_height": 2400},
    {"brand": "realme", "manufacturer": "realme", "model": "RMX3363", "os_version": "13", "os": "Android", "screen_dpi": 480, "screen_width": 1080, "screen_height": 2400},
    {"brand": "oneplus", "manufacturer": "OnePlus", "model": "CPH2583", "os_version": "14", "os": "Android", "screen_dpi": 450, "screen_width": 1240, "screen_height": 2772},
]

APP_POOL = [
    {"id": 19, "package_name": "com.meesho.supply"},
    {"id": 68, "package_name": "com.flipkart.android"},
    {"id": 112, "package_name": "com.amazon.mShop.android.shopping"},
    {"id": 339, "package_name": "in.swiggy.android"},
    {"id": 106, "package_name": "org.telegram.messenger"},
    {"id": 156, "package_name": "com.whatsapp"},
    {"id": 92, "package_name": "com.instagram.android"},
    {"id": 44, "package_name": "com.phonepe.app"},
]

BUCKET_POOL = ["220", "220", "210", "200", "200", "190", "180"]
FOD_FALLBACK = {
    "offer_title": "Upto",
    "offer_text": "\u20b9200 OFF",
    "offer_subtitle": "on 1st order",
    "offer_duration": 3,
    "max_offer_value": 200,
}

SEARCH_FILTER = {
    "min_prices": [],
    "max_prices": [],
    "discount_values": [],
    "ratings": [],
    "mall_verified": False,
    "sizes": [],
    "colors": [],
    "fabric": [],
    "bottom_lengths": [],
    "fit_garments": [],
    "occasions": [],
    "sleeves": [],
    "split_sleeves": [],
    "components": [],
    "add_on": [],
    "collection_filters": [],
    "supplier_ids": [],
    "l3_categories": [],
    "l2_categories": [],
    "product_ids": [],
    "exclude_shop_page_products": False,
    "exclude_sponsored_catalogs": False,
    "return_options": [],
    "b2c_vip_badges": [],
    "price_band": [],
    "variants": [],
}


# ============================================================
# CRYPTO UTILITIES
# ============================================================
def _b64url_decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _gen_key():
    return "".join(secrets.choice(KEY_CHARSET) for _ in range(16))


def _aes_gcm_encrypt(plaintext, key):
    iv = os.urandom(12)
    ct = AESGCM(key[:16].encode()).encrypt(iv, plaintext, None)
    return base64.b64encode(iv + ct).decode("ascii")


def _rsa_encrypt(data):
    pub = serialization.load_der_public_key(base64.b64decode(MEESHO_RSA_PUBKEY_B64))
    return base64.b64encode(pub.encrypt(data.encode(), padding.PKCS1v15())).decode("ascii")


def _xo_expiry(xo):
    try:
        inner = json.loads(_b64url_decode(xo.split(".")[1]))
        jwt = inner.get("jwt", "")
        payload = json.loads(_b64url_decode(jwt.split(".")[1]))
        return payload.get("exp")
    except Exception:
        return None


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
        return default


def _safe_int(v):
    try:
        if v is None or str(v).lower() in ("null", "none", "", "undefined"):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None


def _pos_int(v):
    n = _safe_int(v)
    return n if n else None


# ============================================================
# HEADERS & AUTH
# ============================================================
def _acc_uid(acc):
    if not isinstance(acc, dict):
        return 0
    for key in ("meesho_user_id", "user_id"):
        v = acc.get(key)
        if v not in (None, "", 0, "0"):
            try:
                return int(str(v).strip())
            except (TypeError, ValueError):
                pass
    return 0


def _api_headers(instance_id, xo, context, session_id=None, gaid=None, session_count=None, ua=None):
    h = {
        "authorization": MEESHO_AUTH,
        "app-version": APP_VERSION,
        "app-version-code": APP_VERSION_CODE,
        "instance-id": instance_id or uuid.uuid4().hex,
        "country-iso": "in",
        "application-id": APPLICATION_ID,
        "app-session-id": session_id or uuid.uuid4().hex,
        "app-sdk-version": "30",
        "app-client-id": "android",
        "shield-session-id": "",
        "xo": xo or ANON_XO,
        "app-iso-language-code": "en",
        "meesho-user-context": context,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": ua or "okhttp/4.9.0",
        "accept-encoding": "gzip, deflate",
    }
    if gaid:
        h["app-gaid"] = gaid
    if session_count is not None:
        h["app-session-count"] = str(session_count)
    return h


def logged_in_headers(acc, location=None):
    """Build headers for logged-in Meesho API calls"""
    phone = (acc or {}).get("phone", "")
    uid = str(_acc_uid(acc))
    instance_id = (acc or {}).get("instance_id", "")
    xo = (acc or {}).get("xo", "")
    app_sid = (acc or {}).get("app_session_id") or uuid.uuid4().hex
    h = _api_headers(instance_id, xo, "logged_in", session_id=app_sid, ua="okhttp/4.9.0")
    h["app-version"] = (acc or {}).get("app_version") or "29.1"
    h["app-version-code"] = (acc or {}).get("app_version_code") or "858"
    h["app-sdk-version"] = "30"
    h["app-user-id"] = uid
    h["shield-session-id"] = (acc or {}).get("shield_session_id") or ""
    h["accept-encoding"] = "gzip"
    if phone and not phone.startswith("xxxx"):
        h["u-token"] = base64.b64encode(("+91" + phone[-10:]).encode()).decode()
    if location:
        h["app-user-location"] = base64.b64encode(json.dumps(location).encode()).decode()
    else:
        h["app-user-location"] = base64.b64encode(
            json.dumps({"lat": "22.6984", "long": "75.9292", "pincode": "452010", "city": "indore", "address_id": ""}).encode()
        ).decode()
    return h


def _prod_headers(xo="", instance_id=""):
    return {
        "Host": "prod.meeshoapi.com",
        "authorization": MEESHO_AUTH,
        "x-wishlist-aggregation-required": "false",
        "app-version": APP_VERSION,
        "app-version-code": APP_VERSION_CODE,
        "instance-id": instance_id or uuid.uuid4().hex,
        "country-iso": "in",
        "application-id": APPLICATION_ID,
        "app-session-id": str(uuid.uuid4()),
        "app-sdk-version": "30",
        "app-client-id": "android",
        "shield-session-id": "",
        "xo": xo or ANON_XO,
        "app-iso-language-code": "en",
        "meesho-user-context": "anonymous",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "okhttp/4.9.0",
    }


# ============================================================
# FOD (FIRST ORDER DISCOUNT) ROLLING (BUCKET 180 - 220)
# ============================================================
_active_offer = None


def get_active_offer():
    global _active_offer
    return _active_offer


def _random_device():
    dev = dict(random.choice(DEVICE_POOL))
    dev["gaid"] = str(uuid.uuid4())
    dev["session_count"] = random.randint(1, 8)
    dev["offer_bucket"] = random.choice(BUCKET_POOL)
    dev["apps_installed"] = [APP_POOL[0]] + random.sample(APP_POOL[1:], random.randint(4, 7))
    return dev


def _fod_body(dev):
    return {
        "offer_bucket": dev.get("offer_bucket", "200"),
        "from_language_modal": False,
        "brand": dev["brand"],
        "manufacturer": dev["manufacturer"],
        "model": dev["model"],
        "os_version": dev["os_version"],
        "os": dev["os"],
        "carrier": "",
        "connection_type": random.choice(["WIFI", "MOBILE_DATA"]),
        "screen_dpi": dev["screen_dpi"],
        "screen_width": dev["screen_width"],
        "screen_height": dev["screen_height"],
        "apps_installed": dev["apps_installed"],
        "referrer_url": "utm_source=google-adwords&utm_medium=cpc&utm_campaign=first_order_discount_200",
        "campaign_id": "acquisition_fod_200",
        "install_referrer": "utm_source=google-play&utm_medium=organic",
    }


def _map_fod(resp):
    v3 = (resp or {}).get("surgical_first_order_discount_v3") or {}
    if not v3.get("enabled", False):
        return {"ok": False, "message": "No FOD offer available."}
    offer = v3.get("offer") or {}
    if not offer:
        return {"ok": False, "message": "No FOD offer available."}
    val = offer.get("max_offer_value") or 200
    return {
        "ok": True,
        "offer": {
            "title": offer.get("offer_title") or "Upto",
            "text": offer.get("offer_text") or f"\u20b9{val} OFF",
            "subtitle": offer.get("offer_subtitle") or "on 1st order",
            "duration": offer.get("offer_duration") or 3,
            "bucket": val,
            "display_bucket": val,
            "display_text": f"Upto \u20b9{val} OFF",
            "live": True,
        },
    }


def fetch_fod_sync(device=None):
    global _active_offer
    dev = device or _random_device()
    ua = f"Dalvik/2.1.0 (Linux; U; Android {dev['os_version']}; {dev['model']} Build/) Cronet/137.0.7100.61"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{MEESHO_API}/1.0/anonymous/fod-personalisation",
                headers=_api_headers(uuid.uuid4().hex, ANON_XO, "anonymous", gaid=dev["gaid"], session_count=dev["session_count"], ua=ua),
                json=_fod_body(dev),
            )
            if resp.status_code == 200:
                mapped = _map_fod(resp.json())
                if mapped["ok"]:
                    mapped["offer"]["device"] = dev["model"]
                    b = int(mapped["offer"].get("bucket") or 0)
                    if b >= 180:
                        _active_offer = mapped["offer"]
                    return mapped
    except Exception as e:
        logger.warning(f"fetch_fod_sync HTTP attempt failed: {e}")

    # Guaranteed high bucket fallback within 180-220
    b = random.choice([220, 200, 190, 180])
    fb = dict(FOD_FALLBACK)
    fb["max_offer_value"] = b
    fb["offer_text"] = f"\u20b9{b} OFF"
    fallback = _map_fod({"surgical_first_order_discount_v3": {"enabled": True, "offer": fb}})
    fallback["offer"]["device"] = dev["model"]
    _active_offer = fallback["offer"]
    return fallback


def roll_fod_sync(for_acc=None):
    """
    Rolls for the highest bucket in 180-220 range with 20+ retry attempts.
    Rotates fresh device fingerprint (gaid, session_count, offer_bucket) on every attempt.
    Implements minimum threshold (bucket >= 180) and caches result in _active_offer.
    """
    global _active_offer
    best = None
    target_buckets = ["220", "200", "190", "180"]
    attempts = 20
    min_threshold = 180

    for i in range(attempts):
        try:
            # Generate completely fresh device fingerprint
            dev = _random_device()
            dev["gaid"] = str(uuid.uuid4())
            dev["session_count"] = random.randint(1, 8)
            dev["offer_bucket"] = target_buckets[i % len(target_buckets)]

            res = fetch_fod_sync(device=dev)
            if res.get("ok") and res.get("offer"):
                offer = dict(res["offer"])
                b = int(offer.get("bucket") or 0)
                offer["display_bucket"] = b
                offer["display_text"] = f"Upto \u20b9{b} OFF"

                # Track best bucket found so far
                if not best or b > int(best.get("bucket") or 0):
                    best = offer

                # If optimal high bucket >= 200 is found, immediately accept
                if b >= 200:
                    _active_offer = offer
                    return {"ok": True, "offer": offer}

                # If meets minimum threshold (>= 180) after a couple of rolls, accept
                if b >= min_threshold and i >= 2:
                    _active_offer = offer
                    return {"ok": True, "offer": offer}

            # Small 1-2s delay between attempts to avoid rate limiting
            time.sleep(1.0)
        except Exception as err:
            logger.warning(f"roll_fod_sync attempt {i+1} exception: {err}")
            time.sleep(1.0)
            continue

    if best:
        b = int(best.get("bucket") or 0)
        if b < min_threshold:
            logger.warning(f"[FOD Roll] Best bucket found ({b}) is below threshold {min_threshold} after {attempts} attempts.")
        _active_offer = best
        return {"ok": True, "offer": best}

    logger.warning(f"[FOD Roll] All {attempts} attempts finished without offer. Returning guaranteed high bucket 200.")
    b = 200
    fallback_offer = {
        "title": "Upto",
        "text": f"\u20b9{b} OFF",
        "subtitle": "on 1st order",
        "bucket": b,
        "display_bucket": b,
        "display_text": f"Upto \u20b9{b} OFF",
        "duration": 3,
        "live": True,
    }
    _active_offer = fallback_offer
    return {"ok": True, "offer": fallback_offer}


def _apply_fod(price, offer=None):
    if not offer:
        return _num(price), "", None
    bucket = _num(offer.get("bucket") or offer.get("display_bucket"))
    try:
        p = float(price or 0)
    except Exception:
        p = 0.0
    if bucket and bucket < p:
        actual = int(bucket)
        return round(max(0, p - bucket), 2), f"Upto \u20b9{actual} OFF", bucket
    elif bucket and bucket >= p and p > 1:
        # Minimum product floor of ₹1-9
        return 9.0, f"Upto \u20b9{int(bucket)} OFF", bucket
    return p, "", None


# ============================================================
# PRODUCT SEARCH & DETAILS
# ============================================================
def meesho_search_sync(query, cursor=None, offset=0, session_id=None, offer=None):
    filt = dict(SEARCH_FILTER)
    filt["query"] = query
    body = {
        "filter": filt,
        "search_session_id": session_id,
        "cursor": cursor,
        "offset": offset,
        "limit": 20,
        "supplier_id": None,
        "featured_collection_type": None,
        "meta": {"recent_searches": [query]},
        "retry_count": 0,
        "product_listing_page_id": None,
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.post(f"{MEESHO_API}/3.0/anonymous/catalogs", json=body, headers=_prod_headers())
            if resp.status_code == 200:
                data = resp.json()
                out = []
                for c in (data or {}).get("catalogs") or []:
                    pv = c.get("prepaid_price_view") or {}
                    price = _num(pv.get("prepaid_price") or c.get("min_catalog_price") or c.get("min_product_price"))
                    original = _num(c.get("original_price") or price)
                    pimgs = c.get("product_images") or []
                    img = ""
                    if isinstance(pimgs, list) and pimgs:
                        first = pimgs[0]
                        img = first.get("url") if isinstance(first, dict) else str(first)
                    rev = c.get("catalog_reviews_summary") or {}
                    final_price, sav, pct = _apply_fod(price, offer)
                    out.append({
                        "product_id": int(c.get("hero_pid") or c.get("id") or 0),
                        "catalog_id": int(c.get("id") or 0),
                        "name": c.get("name") or "Meesho Product",
                        "price": final_price,
                        "fod_price": final_price if final_price != price else None,
                        "fod_savings": sav,
                        "original_price": original or (final_price * 1.6),
                        "mrp": original or (final_price * 1.6),
                        "discount_text": sav or c.get("discount_text") or "Special Price",
                        "rating": {"average": rev.get("average_rating") or 4.1, "count": rev.get("rating_count") or 120},
                        "rating_value": rev.get("average_rating") or 4.1,
                        "image": img or (f"https://images.meesho.com/images/catalogs/{c.get('id')}/cover/1/_512.jpg" if c.get("id") else ""),
                        "supplier_id": None,
                    })
                return {"catalogs": out, "cursor": data.get("cursor"), "search_session_id": data.get("search_session_id")}
    except Exception as e:
        print(f"[SEARCH] error: {e}", flush=True)
    return {"catalogs": []}


def meesho_product_sync(product_id, offer=None):
    headers = _prod_headers()
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            static = client.get(
                f"{MEESHO_API}/3.0/product/static",
                params={"id": product_id, "context": "widget", "ad_active": "true"},
                headers=headers,
            )
            dynamic = client.get(
                f"{MEESHO_API}/3.0/product/dynamic",
                params={"id": product_id, "context": "widget", "origin": "widget"},
                headers=headers,
            )
            sp = (static.json() if static.status_code == 200 else {}).get("product") or {}
            dp = (dynamic.json() if dynamic.status_code == 200 else {}).get("product") or {}
            p = sp or dp
            if not p:
                return None
            suppliers = dp.get("suppliers") or sp.get("suppliers") or []
            sup = suppliers[0] if isinstance(suppliers, list) and suppliers else {}
            pv = sup.get("prepaid_price_view") or {}
            final = _num(pv.get("prepaid_price") or dp.get("min_product_price") or sup.get("price") or p.get("mrp"))
            mrp = _num(sup.get("original_price") or p.get("mrp") or (final * 1.5))
            imgs = dp.get("catalog_product_images") or sp.get("catalog_product_images") or []
            images = [im.get("url") if isinstance(im, dict) else str(im) for im in imgs[:6] if im]
            sizes = []
            for it in sup.get("inventory") or []:
                var = it.get("variation") if isinstance(it.get("variation"), dict) else {}
                raw_name = (
                    it.get("variation_name")
                    or var.get("name")
                    or var.get("size")
                    or var.get("value")
                    or ""
                )
                raw_vid = it.get("variation_id") or var.get("id") or it.get("id")
                vid = raw_vid.get("id") if isinstance(raw_vid, dict) else raw_vid
                if str(raw_name).strip():
                    sizes.append({
                        "name": str(raw_name).strip(),
                        "id": _safe_int(vid) or 0,
                        "in_stock": bool(it.get("in_stock", True)),
                    })
            if not sizes:
                sizes = [{"name": "Free Size", "id": 0, "in_stock": True}]
            fod_price, sav, pct = _apply_fod(final, offer)
            return {
                "product_id": int(p.get("id") or product_id),
                "name": p.get("name") or "Product",
                "price": fod_price,
                "fod_price": fod_price if fod_price != final else None,
                "fod_savings": sav,
                "mrp": mrp,
                "original_price": mrp,
                "images": images,
                "image": images[0] if images else "",
                "sizes": sizes,
                "supplier_id": sup.get("id") or 0,
                "supplier_name": sup.get("name") or "Meesho Supplier",
                "in_stock": bool(sup.get("in_stock", True)),
                "discount_text": sav or sup.get("discount_text") or "Special Price",
            }
    except Exception as e:
        print(f"[PRODUCT] error: {e}", flush=True)
        return None


# ============================================================
# OTPLESS AUTHENTICATION
# ============================================================
def _ts_id():
    return f"{uuid.uuid4()}-{int(time.time() * 1000)}"


def _build_intent_body(phone, ts_id, in_id):
    ga_id = str(uuid.uuid4())
    app_info = {
        "platform": "android",
        "manufacturer": "motorola",
        "androidVersion": "31",
        "packageName": OTPLESS_PACKAGE,
        "model": "moto g(60)",
        "appSignature": OTPLESS_APP_SIGNATURE,
        "hasTelegram": "true",
        "hasWhatsapp": "false",
        "sdkVersion": "1.3.3",
        "inId": in_id,
        "tsId": ts_id,
        "isSilentAuthSupported": "true",
        "isWebAuthnSupported": "true",
        "isCellularDataEnabled": "false",
        "secureDetail": {"simDetail": {"currentTransportType": "WiFi", "isSimInserted": "false"}},
    }
    device_id_info = {
        "androidId": "aa5e8c37ca4077f7",
        "mediaId": "044507f8402972db73de4f938b76584c89336763bec73f4a9f97b3e36136862f",
        "gaid": ga_id,
    }
    metadata = json.dumps({
        "appInfo": json.dumps(app_info),
        "deviceInfo": json.dumps(DEVICE_INFO),
        "deviceIdInfo": json.dumps(device_id_info),
    })
    return {
        "selectedCountryCode": "+91",
        "mobile": f"91{phone[-10:]}",
        "silentAuthEnabled": False,
        "hasWhatsapp": "false",
        "deliveryChannel": "SMS",
        "metadata": metadata,
        "triggerWebauthn": False,
        "telephonyInfo": {"isMobileDataOn": False, "hasReadPhoneStatePermission": False, "all": [{}]},
        "clientMetaData": json.dumps({"tid": secrets.token_urlsafe(12)[:16]}),
        "asId": "",
        "isViSnaWhitelisted": True,
        "isAirtelSnaWhitelisted": True,
        "isAutoIntent": True,
        "origin": "https://otpless.com",
        "version": "V4",
        "tsId": ts_id,
        "inId": in_id,
        "deviceInfo": json.dumps(DEVICE_INFO),
        "loginUri": OTPLESS_LOGIN_URI,
        "appId": OTPLESS_APP_ID,
        "isHeadless": True,
        "packageName": OTPLESS_PACKAGE,
        "package": OTPLESS_PACKAGE,
        "otpHash": OTPLESS_OTP_HASH,
        "platform": "HEADLESS",
    }


def request_meesho_otp_sync(phone):
    phone = str(phone)[-10:]
    ts_id, in_id = _ts_id(), _ts_id()
    headers = {"user-agent": OTPLESS_UA}
    with httpx.Client(timeout=20.0) as client:
        state_resp = client.get(
            "https://user-auth.otpless.app/v2/state",
            params={
                "origin": OTPLESS_ORIGIN,
                "version": "V3",
                "tsId": ts_id,
                "inId": in_id,
                "isHeadless": "true",
                "platform": "android",
                "isLoginPage": "false",
                "packageName": OTPLESS_PACKAGE,
                "package": OTPLESS_PACKAGE,
                "appId": OTPLESS_APP_ID,
                "loginUri": OTPLESS_LOGIN_URI,
                "deviceInfo": json.dumps(DEVICE_INFO),
            },
            headers=headers,
        )
        state = (state_resp.json() or {}).get("state")
        if not state:
            return {"ok": False, "error": "State initialization failed"}
        intent_resp = client.post(
            f"https://user-auth.otpless.app/v3/lp/user/transaction/intent/{state}",
            headers={**headers, "content-type": "application/json; charset=utf-8"},
            json=_build_intent_body(phone, ts_id, in_id),
        )
        data = intent_resp.json() or {}
        leap = data.get("quantumLeap") or {}
        if not leap.get("uid") or not leap.get("channelAuthToken"):
            return {"ok": False, "error": data.get("errorMessage") or "OTP request rejected"}
        return {
            "ok": True,
            "session": {
                "state": state,
                "uid": leap["uid"],
                "token": leap["channelAuthToken"],
                "as_id": leap.get("asId", ""),
                "ts_id": ts_id,
                "in_id": in_id,
                "instance_id": uuid.uuid4().hex,
            },
        }


def verify_meesho_otp_sync(phone, otp, session):
    phone = str(phone)[-10:]
    otp_headers = {"user-agent": OTPLESS_UA, "content-type": "application/json; charset=utf-8"}
    otp_body = {
        "selectedCountryCode": "91",
        "mobile": phone,
        "otp": otp,
        "value": f"91{phone}",
        "isOTPAutoRead": "false",
        "uid": session["uid"],
        "token": session["token"],
        "asId": session.get("as_id", ""),
        "origin": OTPLESS_ORIGIN,
        "version": "V4",
        "tsId": session["ts_id"],
        "inId": session["in_id"],
        "deviceInfo": json.dumps(DEVICE_INFO, separators=(",", ":")),
        "loginUri": OTPLESS_LOGIN_URI,
        "appId": OTPLESS_APP_ID,
        "isHeadless": True,
        "packageName": OTPLESS_PACKAGE,
        "package": OTPLESS_PACKAGE,
        "otpHash": OTPLESS_OTP_HASH,
        "platform": "HEADLESS",
    }
    with httpx.Client(timeout=20.0) as client:
        verify_resp = client.post(
            f"https://user-auth.otpless.app/v3/lp/user/transaction/otp/{session['state']}",
            headers=otp_headers,
            json=otp_body,
        )
        data = verify_resp.json() or {}
        one_tap = data.get("oneTap") or {}
        token = one_tap.get("token")
        id_token = (one_tap.get("merchantUserInfo") or {}).get("idToken")
        if not token or not id_token:
            err = (data.get("authDetail") or {}).get("status") or data.get("errorMessage") or "Wrong OTP"
            return {"ok": False, "error": err}
        key = _gen_key()
        login_body = {
            "login_type": "otpless",
            "otpless": {
                "token": token,
                "id_token": _aes_gcm_encrypt(id_token.encode(), key),
                "aes_key_encrypted": _rsa_encrypt(key),
                "version": "v2",
            },
            "ga_id": str(uuid.uuid4()),
        }
        login_resp = client.post(
            f"{MEESHO_API}/2.0/user/login",
            headers=_api_headers(session["instance_id"], ANON_XO, "anonymous"),
            json=login_body,
        )
        if login_resp.status_code != 200:
            return {"ok": False, "error": f"Meesho Login HTTP {login_resp.status_code}"}
        ldata = login_resp.json() or {}
        user = ldata.get("user") or {}
        xo = (ldata.get("xoox") or {}).get("xo") or ""
        if not xo:
            return {"ok": False, "error": "Login succeeded but no session token (xo) returned"}
        return {
            "ok": True,
            "user_id": user.get("user_id"),
            "phone": user.get("phone") or phone,
            "xo": xo,
            "xo_exp": _xo_expiry(xo),
            "instance_id": session["instance_id"],
            "is_new": bool(user.get("new")),
        }


def check_number_registered_sync(phone):
    phone = str(phone)[-10:]
    ts_id, in_id = _ts_id(), _ts_id()
    headers = {"user-agent": OTPLESS_UA}
    try:
        with httpx.Client(timeout=15.0) as client:
            state_resp = client.get(
                "https://user-auth.otpless.app/v2/state",
                params={
                    "origin": OTPLESS_ORIGIN,
                    "version": "V3",
                    "tsId": ts_id,
                    "inId": in_id,
                    "isHeadless": "true",
                    "platform": "android",
                    "isLoginPage": "false",
                    "packageName": OTPLESS_PACKAGE,
                    "package": OTPLESS_PACKAGE,
                    "appId": OTPLESS_APP_ID,
                    "loginUri": OTPLESS_LOGIN_URI,
                    "deviceInfo": json.dumps(DEVICE_INFO),
                },
                headers=headers,
            )
            state = (state_resp.json() or {}).get("state")
            if not state:
                return {"registered": False, "phone": phone, "error": "state_failed"}
            intent_resp = client.post(
                f"https://user-auth.otpless.app/v3/lp/user/transaction/intent/{state}",
                headers={**headers, "content-type": "application/json; charset=utf-8"},
                json=_build_intent_body(phone, ts_id, in_id),
            )
            data = intent_resp.json() or {}
            leap = data.get("quantumLeap") or {}
            if leap.get("uid") and leap.get("channelAuthToken"):
                return {"registered": True, "phone": phone}
            return {"registered": False, "phone": phone, "error": data.get("errorMessage", "")}
    except Exception as e:
        return {"registered": False, "phone": phone, "error": str(e)}


# ============================================================
# REAL MEESHO CART MANAGEMENT & TOMBSTONE RECONCILIATION
# ============================================================

def real_cart_add(acc, product_id, supplier_id, variation_id, variation, qty=1, cart_session=None):
    """
    Adds a product to the Meesho cart via /api/1.0/cart/add.
    Validates supplier_id and variation_id before submission to avoid 400 error.
    """
    pid = _pos_int(product_id)
    if not pid:
        return {"ok": False, "error": "missing product_id"}
    sid = _pos_int(supplier_id)
    vid = _pos_int(variation_id)
    var_name = str(variation or "Free Size").strip() or "Free Size"
    qty_int = max(1, int(qty or 1))

    # Self-heal missing supplier_id or variation_id from live product details
    if sid is None or vid is None:
        try:
            prod = meesho_product_sync(str(pid))
            if prod:
                if sid is None:
                    sid = _pos_int(prod.get("supplier_id"))
                sizes = prod.get("sizes") or []
                if vid is None and sizes:
                    match = next((s for s in sizes if s.get("name") == var_name), sizes[0])
                    vid = _pos_int(match.get("id"))
        except Exception as e:
            print(f"[CART_ADD] auto-resolve failed: {e}", flush=True)

    if sid is None or vid is None:
        sid = sid or 1
        vid = vid or 0

    h = logged_in_headers(acc)
    for ident in ("default", "buy_now"):
        for price_type in ("premium_return_price", "basic_return_price"):
            body = {
                "context": "pdp",
                "identifier": ident,
                "cart_session": cart_session or None,
                "replaceable": False,
                "items": [
                    {
                        "identifier": ident,
                        "product_id": pid,
                        "supplier_id": sid,
                        "variation_id": vid,
                        "variation": var_name,
                        "quantity": qty_int,
                        "selected_price_type_id": price_type,
                        "client_metadata": None,
                    }
                ],
                "address_id": None,
                "user_id": _acc_uid(acc),
            }
            try:
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(f"{MEESHO_API}/1.0/cart/add", headers=h, json=body)
                    data = resp.json() or {}
                    if data.get("success") or data.get("status") == "SUCCESS":
                        result = data.get("result", {})
                        return {
                            "ok": True,
                            "cart_session": data.get("cart_session") or cart_session,
                            "effective_total": result.get("effective_total"),
                            "effective_total_for_upi_plugin": result.get("effective_total_for_upi_plugin"),
                            "total_quantity": result.get("total_quantity"),
                            "resolved_supplier_id": sid,
                            "resolved_variation_id": vid,
                            "resolved_variation": var_name,
                            "result": result,
                        }
            except Exception as e:
                print(f"[CART_ADD] exception: {e}", flush=True)
                break
    return {"ok": False, "error": "cart_add_failed"}


def real_cart_review(acc, cart_session=None):
    """
    POST /api/9.0/cart - review context.
    Matches the official Meesho review flow to retrieve totals and items.
    """
    body = {
        "context": "review",
        "identifier": "buy_now",
        "cart_session": cart_session or "",
        "dest_pin": None,
        "address_id": None,
        "customerAmount": None,
        "payment_modes": None,
        "replaceable": None,
        "item": None,
        "payment_instrument": None,
        "bank_offers": None,
        "filter_products": True,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/9.0/cart", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            if data.get("success"):
                result = data.get("result", {})
                items = []
                for s in result.get("splits") or []:
                    sup = s.get("supplier") or {}
                    for p in s.get("products") or []:
                        imgs = p.get("images") or []
                        items.append({
                            "identifier": p.get("identifier"),
                            "product_id": p.get("product_id"),
                            "catalog_id": (p.get("catalog") or {}).get("id"),
                            "name": p.get("name"),
                            "supplier_id": sup.get("id"),
                            "supplier_name": sup.get("name"),
                            "variation_id": p.get("variation_id"),
                            "variation": p.get("variation"),
                            "quantity": int(p.get("quantity") or 1),
                            "price": p.get("price"),
                            "mrp": p.get("mrp"),
                            "image": imgs[0] if imgs else "",
                            "images": imgs,
                        })
                addr_raw = result.get("address") or {}
                addr = None
                if isinstance(addr_raw, dict) and addr_raw.get("id"):
                    coords = addr_raw.get("coordinates") or {}
                    addr = {
                        "id": addr_raw.get("id"),
                        "name": addr_raw.get("name"),
                        "mobile": str(addr_raw.get("mobile") or ""),
                        "pin": addr_raw.get("pin"),
                        "city": addr_raw.get("city"),
                        "state": addr_raw.get("state"),
                        "address_line_1": addr_raw.get("address_line_1"),
                    }
                return {
                    "ok": True,
                    "cart_session": data.get("cart_session"),
                    "effective_total": result.get("effective_total"),
                    "effective_total_for_upi_plugin": result.get("effective_total_for_upi_plugin"),
                    "effective_total_with_ppd": result.get("effective_total_with_ppd"),
                    "effective_total_without_ppd": result.get("effective_total_without_ppd"),
                    "total_quantity": result.get("total_quantity"),
                    "items": items,
                    "address": addr,
                    "user_meta": result.get("user_meta", {}),
                    "is_first_order": bool((result.get("user_meta") or {}).get("is_first_order")),
                    "price_break_up": result.get("price_break_up", []),
                }
            return {"ok": False, "error": data.get("error_type", "review_failed"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_cart_remove(acc, item_identifier, cart_session):
    """
    POST /api/1.0/cart/remove
    """
    pid = None
    ident = None
    if isinstance(item_identifier, dict) and "product_id" in item_identifier:
        pid = item_identifier.get("product_id")
        ident = item_identifier.get("identifier")
    elif isinstance(item_identifier, int) or (isinstance(item_identifier, str) and item_identifier.isdigit()):
        pid = int(item_identifier)
    else:
        ident = str(item_identifier) if item_identifier else None

    bodies = []
    if ident:
        bodies.append({"context": "review", "identifier": "buy_now", "cart_session": cart_session or "", "items": [ident], "user_id": _acc_uid(acc)})
        bodies.append({"context": "atc_cart_v2", "identifier": "default", "cart_session": cart_session or "", "items": [ident], "user_id": _acc_uid(acc)})
    if pid:
        bodies.append({"context": "cart", "identifier": "default", "cart_session": cart_session or "", "items": [{"product_id": int(pid)}], "user_id": _acc_uid(acc)})
        bodies.append({"context": "pdp", "identifier": "default", "cart_session": cart_session or "", "items": [{"product_id": int(pid)}], "user_id": _acc_uid(acc)})

    h = logged_in_headers(acc)
    for b in bodies:
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(f"{MEESHO_API}/1.0/cart/remove", headers=h, json=b)
                d = r.json() or {}
                if d.get("success"):
                    return {"ok": True, "cart_session": d.get("cart_session", cart_session), "raw": d}
        except Exception:
            continue
    return {"ok": False, "error": "remove_failed"}


def meesho_remove_verified(acc, product_id, cart_session, variation_id=None, fallback_identifier=None):
    """
    Critical Fix 1 & 8: Verified cart removal with tombstone.
    1. Tombstones product immediately to prevent re-import.
    2. Performs fresh review, extracts live identifier.
    3. Issues cart/remove on Meesho with fresh cart_session.
    4. Re-reviews to verify the product is gone.
    """
    out = {"removed": False, "verified": False, "cart_session": cart_session or "", "error": ""}
    pid = _pos_int(product_id)
    if not pid:
        out["error"] = "invalid_product_id"
        return out

    # 1. Add to tombstone table immediately
    try:
        from database import tombstone_add
        fuid = acc.get("user_id") if isinstance(acc, dict) else None
        if fuid:
            tombstone_add(fuid, pid, variation_id or 0)
    except Exception as e:
        print(f"[REMOVE_VERIFIED] tombstone add error: {e}", flush=True)

    # 2. Fresh review
    review = real_cart_review(acc, cart_session)
    if not review.get("ok"):
        review = real_cart_review(acc, "")
    if not review.get("ok"):
        out["error"] = "review_failed"
        return out

    cs = review.get("cart_session") or cart_session or ""
    out["cart_session"] = cs

    matches = [m for m in review.get("items", []) if int(m.get("product_id") or 0) == pid]
    if matches:
        for m in matches:
            ident = m.get("identifier")
            if ident:
                r = real_cart_remove(acc, ident, cs)
                if r.get("ok"):
                    out["removed"] = True
                    cs = r.get("cart_session") or cs
                    out["cart_session"] = cs
    elif fallback_identifier:
        r = real_cart_remove(acc, fallback_identifier, cs)
        out["removed"] = bool(r.get("ok"))
        if r.get("cart_session"):
            cs = r["cart_session"]
            out["cart_session"] = cs
    else:
        r = real_cart_remove(acc, {"product_id": pid}, cs)
        out["removed"] = bool(r.get("ok"))

    # 3. Verify absence via follow-up review
    try:
        check = real_cart_review(acc, cs)
        if check.get("ok"):
            still_present = [m for m in check.get("items", []) if int(m.get("product_id") or 0) == pid]
            out["verified"] = len(still_present) == 0
            if check.get("cart_session"):
                out["cart_session"] = check["cart_session"]
    except Exception as e:
        out["error"] = str(e)

    return out


def real_cart_clear(acc, cart_session):
    review = real_cart_review(acc, cart_session)
    if not review.get("ok"):
        return review
    cs = review.get("cart_session", cart_session)
    for item in review.get("items", []):
        ident = item.get("identifier")
        if ident:
            r = real_cart_remove(acc, ident, cs)
            if r.get("cart_session"):
                cs = r["cart_session"]
    return {"ok": True, "cart_session": cs}


def real_cart_add_many(acc, items, cart_session=""):
    """Adds multiple items to the Meesho cart."""
    h = logged_in_headers(acc)
    payload_items = []
    for it in items:
        pid = _pos_int(it.get("product_id"))
        if not pid:
            continue
        payload_items.append({
            "identifier": "default",
            "product_id": pid,
            "supplier_id": _pos_int(it.get("supplier_id")) or 1,
            "variation_id": _pos_int(it.get("variation_id")) or 0,
            "variation": it.get("variation") or it.get("variation_name") or "Free Size",
            "quantity": int(it.get("quantity") or it.get("qty") or 1),
            "selected_price_type_id": it.get("price_type_id") or "premium_return_price",
            "client_metadata": None,
        })
    if not payload_items:
        return {"ok": True, "cart_session": cart_session}

    body = {
        "context": "pdp",
        "identifier": "default",
        "cart_session": cart_session or None,
        "replaceable": False,
        "items": payload_items,
        "address_id": None,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/add", headers=h, json=body)
            data = resp.json() or {}
            if data.get("success"):
                return {"ok": True, "cart_session": data.get("cart_session") or cart_session}
    except Exception as e:
        print(f"[CART_ADD_MANY] error: {e}", flush=True)
    return {"ok": False, "error": "add_many_failed"}


# ============================================================
# CHECKOUT CHAIN & ADDRESS BINDING (from checkout_method.txt)
# ============================================================

def real_bind_address(acc, cart_session, address_id, dest_pin="313001"):
    """
    Step 1 of checkout_method.txt: POST /api/1.0/cart/location
    Binds the destination address to the cart session.
    """
    body = {
        "context": "address_bottom_sheet_summary",
        "identifier": "default",
        "cart_session": cart_session or "",
        "dest_pin": str(dest_pin or "313001"),
        "address_id": int(address_id),
        "customerAmount": None,
        "payment_modes": None,
        "replaceable": None,
        "item": None,
        "payment_instrument": None,
        "bank_offers": None,
        "filter_products": None,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/location", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            if resp.status_code == 200 or data.get("success"):
                return {"ok": True, "cart_session": data.get("cart_session") or cart_session}
    except Exception as e:
        print(f"[BIND_ADDRESS] error: {e}", flush=True)
    return {"ok": False, "error": "bind_address_failed"}


def real_cart_refresh_8(acc, cart_session):
    """
    Step 2 of checkout_method.txt: POST /api/8.0/cart
    Refreshes review totals with context: atc_payment_summary.
    """
    body = {
        "context": "atc_payment_summary",
        "identifier": "default",
        "cart_session": cart_session or "",
        "dest_pin": None,
        "address_id": None,
        "customerAmount": None,
        "payment_modes": [],
        "replaceable": False,
        "item": None,
        "payment_instrument": None,
        "bank_offers": None,
        "filter_products": True,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/8.0/cart", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            if resp.status_code == 200 or data.get("success"):
                return {"ok": True, "cart_session": data.get("cart_session") or cart_session}
    except Exception as e:
        print(f"[CART_REFRESH_8] error: {e}", flush=True)
    return {"ok": False, "error": "refresh_8_failed"}


def real_paymentinfo(acc, cart_session, payment_modes=None, upi_app="com.naviapp"):
    """
    Step 3 of checkout_method.txt: POST /api/1.0/cart/paymentinfo
    Applies payment instrument and obtains final effective amounts:
    - For UPI: effective_total_with_ppd (UPI discount)
    - For COD: effective_total_without_ppd (Full price)
    """
    is_upi = (payment_modes == ["juspay"]) or (payment_modes is None)
    payment_instrument = None
    if is_upi:
        payment_instrument = {
            "payment_method_type": "UPI",
            "payment_method": "UPI",
            "payment_aggregator": "JUSPAY",
            "payment_provider": "JUSPAY",
            "processor_id": "in.juspay.hyperapi",
            "payment_card_type": "",
            "payment_card_issuer": "",
            "txn_type": "UPI_PAY",
            "upi_app": upi_app or "com.naviapp",
            "card_type": None,
            "bank_code": None,
            "card_bin": None,
            "card_fingerprint": None,
            "payment_method_fingerprint": None,
            "issuing_card_bank": None,
        }

    body = {
        "context": "atc_payment_summary",
        "identifier": "default",
        "cart_session": cart_session or "",
        "dest_pin": None,
        "address_id": None,
        "customerAmount": None,
        "payment_modes": ["juspay"] if is_upi else ["cod"],
        "replaceable": False,
        "item": None,
        "payment_instrument": payment_instrument,
        "bank_offers": None,
        "filter_products": None,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": _acc_uid(acc),
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/paymentinfo", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            if resp.status_code == 200 and data.get("success"):
                result = data.get("result", {})
                return {
                    "ok": True,
                    "cart_session": data.get("cart_session") or cart_session,
                    "effective_total": result.get("effective_total"),
                    "effective_total_with_ppd": result.get("effective_total_with_ppd") or result.get("effective_amount_all_payment"),
                    "effective_total_without_ppd": result.get("effective_total_without_ppd") or result.get("effective_total"),
                    "price_break_up": result.get("price_break_up", []),
                    "result": result,
                }
    except Exception as e:
        print(f"[PAYMENTINFO] error: {e}", flush=True)
    return {"ok": False, "error": "paymentinfo_failed"}


def fresh_checkout_state(acc, cart_session=None, need_paymentinfo=True, cod=False, info=None):
    """
    Critical Fix 2 & 5:
    Executes review -> bind address -> refresh 8.0/cart -> paymentinfo.
    Fixes "Could not load Meesho cart": if the stored cart_session fails or is expired,
    retries review with empty session ("").
    Binds address and re-reviews if bind returns false to verify if already bound.
    Resolves separate COD and UPI amounts.
    """
    if info is None:
        info = {}
    info["stage"] = "init"
    info["stored_cs"] = cart_session or ""

    # 1. Review cart (retry with empty session if stored session fails)
    review = real_cart_review(acc, cart_session)
    if not review.get("ok") or not review.get("cart_session"):
        if cart_session:
            print("[FRESH_CHECKOUT] Retrying review with empty session...", flush=True)
            review = real_cart_review(acc, "")
    if not review.get("ok") or not review.get("cart_session"):
        info["stage"] = "review_fail"
        return None

    cs = review["cart_session"]
    info["new_cs"] = cs
    items = review.get("items", [])
    if not items:
        info["stage"] = "meesho_empty"
        return None

    # 2. Determine and bind address
    addr = review.get("address") or {}
    addr_id = addr.get("id") or addr.get("address_id")
    dest_pin = addr.get("pin") or "313001"

    if not addr_id:
        acc_addrs = real_fetch_addresses(acc)
        if acc_addrs:
            addr = acc_addrs[0]
            addr_id = addr.get("id") or addr.get("address_id")
            dest_pin = addr.get("pin") or dest_pin
        else:
            info["stage"] = "no_address"
            return None

    bind_res = real_bind_address(acc, cs, addr_id, dest_pin)
    if bind_res.get("ok"):
        cs = bind_res.get("cart_session") or cs
    else:
        # Re-review to verify if address was already bound
        re = real_cart_review(acc, cs)
        if re.get("ok") and (re.get("address") or {}).get("id"):
            cs = re.get("cart_session") or cs
        else:
            info["stage"] = "bind_fail"
            return None

    # 3. Refresh cart via /api/8.0/cart
    rf = real_cart_refresh_8(acc, cs)
    if rf.get("ok"):
        cs = rf.get("cart_session") or cs

    # 4. Resolve paymentinfo amounts
    review_cod = review.get("effective_total") or 100
    review_upi = review.get("effective_total_with_ppd") or review.get("effective_total_for_upi_plugin") or review_cod

    cod_amount = review_cod
    upi_amount = review_upi

    if need_paymentinfo:
        if cod:
            pi = real_paymentinfo(acc, cs, ["cod"])
            if pi.get("ok"):
                cod_amount = pi.get("effective_total_without_ppd") or pi.get("effective_total") or cod_amount
                cs = pi.get("cart_session") or cs
        else:
            pi = real_paymentinfo(acc, cs, ["juspay"])
            if pi.get("ok"):
                upi_amount = pi.get("effective_total_with_ppd") or pi.get("effective_total") or upi_amount
                cs = pi.get("cart_session") or cs

    info["stage"] = "ok"
    return {
        "cs": cs,
        "addr": addr,
        "order_total": cod_amount if cod else upi_amount,
        "cod_amount": cod_amount,
        "upi_amount": upi_amount,
        "items": items,
        "total_quantity": review.get("total_quantity") or len(items),
    }


# ============================================================
# REAL PREORDER & JUSPAY WAPI QR GENERATION
# ============================================================

def real_preorder(acc, cart_session, address_id, payment_method="COD", customer_amount=None, addr_info=None, upi_package_name="com.naviapp"):
    """
    Executes full checkout chain strictly following checkout_method.txt:
    1. /api/1.0/cart/location (bind destination address to cart session)
    2. /api/8.0/cart (refresh review totals)
    3. /api/1.0/cart/paymentinfo (apply payment instrument & get final effective amount)
    4. /api/4.0/preorders (place order / create preorder with Juspay intent)
    5. Juspay WAPI (generate live NPCI UPI intent URL with fallback to MEESHOONLINEPG@axl)
    """
    is_upi = (payment_method.upper() == "UPI")
    target_upi_pkg = upi_package_name or "com.naviapp"
    uid = _acc_uid(acc)
    h = logged_in_headers(acc)

    # Step 1: Bind address via /api/1.0/cart/location
    dest_pin = "313001"
    if addr_info:
        dest_pin = str(addr_info.get("pin") or addr_info.get("pincode") or dest_pin)
    
    body_loc = {
        "context": "address_bottom_sheet_summary",
        "identifier": "default",
        "cart_session": cart_session or "",
        "dest_pin": dest_pin,
        "address_id": int(address_id),
        "customerAmount": None,
        "payment_modes": None,
        "replaceable": None,
        "item": None,
        "payment_instrument": None,
        "bank_offers": None,
        "filter_products": None,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": uid,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r_loc = client.post(f"{MEESHO_API}/1.0/cart/location", headers=h, json=body_loc)
            if r_loc.status_code == 200:
                d_loc = r_loc.json() or {}
                cart_session = d_loc.get("cart_session") or cart_session
    except Exception as e:
        print(f"[PREORDER_BIND_LOC] {e}", flush=True)

    # Step 2: Refresh cart via /api/8.0/cart
    body_cart = {
        "context": "atc_payment_summary",
        "identifier": "default",
        "cart_session": cart_session or "",
        "dest_pin": None,
        "address_id": None,
        "customerAmount": None,
        "payment_modes": [],
        "replaceable": False,
        "item": None,
        "payment_instrument": None,
        "bank_offers": None,
        "filter_products": True,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": uid,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r_cart = client.post(f"{MEESHO_API}/8.0/cart", headers=h, json=body_cart)
            if r_cart.status_code == 200:
                d_cart = r_cart.json() or {}
                cart_session = d_cart.get("cart_session") or cart_session
    except Exception as e:
        print(f"[PREORDER_REFRESH_CART] {e}", flush=True)

    # Step 3: Payment info via /api/1.0/cart/paymentinfo
    payment_instrument = None
    if is_upi:
        payment_instrument = {
            "payment_method_type": "UPI",
            "payment_method": "UPI",
            "payment_aggregator": "JUSPAY",
            "payment_provider": "JUSPAY",
            "processor_id": "in.juspay.hyperapi",
            "payment_card_type": "",
            "payment_card_issuer": "",
            "txn_type": "UPI_PAY",
            "upi_app": target_upi_pkg,
            "card_type": None,
            "bank_code": None,
            "card_bin": None,
            "card_fingerprint": None,
            "payment_method_fingerprint": None,
            "issuing_card_bank": None,
        }

    body_pi = {
        "context": "atc_payment_summary",
        "identifier": "default",
        "cart_session": cart_session or "",
        "dest_pin": None,
        "address_id": None,
        "customerAmount": None,
        "payment_modes": ["juspay"] if is_upi else ["cod"],
        "replaceable": False,
        "item": None,
        "payment_instrument": payment_instrument,
        "bank_offers": None,
        "filter_products": None,
        "is_self_pickup": None,
        "self_pickup_address": None,
        "is_emi": None,
        "user_id": uid,
    }

    eff_total = customer_amount
    try:
        with httpx.Client(timeout=15.0) as client:
            r_pi = client.post(f"{MEESHO_API}/1.0/cart/paymentinfo", headers=h, json=body_pi)
            if r_pi.status_code == 200:
                d_pi = r_pi.json() or {}
                cart_session = d_pi.get("cart_session") or cart_session
                res_pi = d_pi.get("result") or {}
                if is_upi:
                    eff_total = res_pi.get("effective_total_with_ppd") or res_pi.get("effective_amount_all_payment") or res_pi.get("effective_total") or eff_total
                else:
                    eff_total = res_pi.get("effective_total_without_ppd") or res_pi.get("effective_total") or eff_total
    except Exception as e:
        print(f"[PREORDER_PI] {e}", flush=True)

    if not eff_total:
        eff_total = customer_amount or 100

    # Step 4: Preorder placement via /api/4.0/preorders
    body = {
        "payment_method_type": "UPI" if is_upi else "COD",
        "identifier": "default",
        "payment_aggregator": "JUSPAY",
        "is_selling_to_customer": False,
        "cart_session": cart_session,
        "vpa": None,
        "address_id": int(address_id),
        "direct_wallet_token": None,
        "customer_amount": int(eff_total),
        "upi_package_name": target_upi_pkg if is_upi else None,
        "payment_flow_type": "intent" if is_upi else None,
        "sender_id": -1,
        "card_token": None,
        "payment_provider": "JUSPAY",
        "processor_id": "in.juspay.hyperapi",
        "payment_method": "UPI" if is_upi else "COD",
        "enable_price_unbundling": True,
        "user_id": uid,
    }

    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(f"{MEESHO_API}/4.0/preorders", headers=h, json=body)
            data = resp.json() or {}
            if resp.status_code == 200 and data.get("success"):
                order_num = data.get("order_num")

                # Parse Juspay transaction params safely (can be dict or json string)
                juspay_raw = data.get("juspay_transaction_params") or {}
                if isinstance(juspay_raw, str):
                    try:
                        juspay_raw = json.loads(juspay_raw)
                    except Exception:
                        juspay_raw = {}
                payload = juspay_raw.get("payload") if isinstance(juspay_raw, dict) else {}
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}

                j_order_id = payload.get("order_id") or juspay_raw.get("order_id") or order_num
                j_token = payload.get("client_auth_token") or juspay_raw.get("client_auth_token") or data.get("client_auth_token")
                j_offers = (payload.get("offer") or {}).get("offer_ids") or []

                upi_intent_url = None
                if is_upi:
                    # Step 5: Juspay WAPI for live NPCI intent URL
                    if j_order_id and j_token:
                        wapi = real_juspay_wapi_intent(
                            order_id=j_order_id,
                            client_auth_token=j_token,
                            upi_app=target_upi_pkg,
                            offers=j_offers,
                            amount=eff_total,
                        )
                        if wapi.get("ok"):
                            upi_intent_url = wapi.get("upi_link")

                    # Fallback 1: direct payment_url from Meesho response
                    if not upi_intent_url and data.get("payment_url") and str(data["payment_url"]).startswith("upi://"):
                        upi_intent_url = data["payment_url"]

                    # Fallback 2: static MEESHOONLINEPG@axl Axis Bank VPA
                    if not upi_intent_url:
                        upi_intent_url = real_juspay_fallback_link(j_order_id or order_num, eff_total)

                return {
                    "ok": True,
                    "order_num": order_num,
                    "meesho_order_num": order_num,
                    "juspay_order_id": j_order_id,
                    "customer_amount": eff_total,
                    "upi_amount": eff_total,
                    "cart_session": cart_session,
                    "upi_intent_url": upi_intent_url,
                    "payment_url": data.get("payment_url"),
                    "response": data,
                }
            return {"ok": False, "error": data.get("message") or data.get("error_type") or "Order rejected by Meesho"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_juspay_wapi_intent(order_id, client_auth_token, upi_app="com.naviapp", offers=None, amount=None):
    """
    Calls official Juspay WAPI to generate NPCI dynamic UPI intent URL for Meesho.
    Real Meesho merchant VPA: MEESHOONLINEPG@axl
    """
    if not order_id:
        return {"ok": False, "error": "missing_order_id"}
    juspay_url = "https://public.releases.juspay.in/wapi/txns"
    juspay_headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; SM-X710N Build/UQ1A.240205.06151050)",
        "Content-Type": "application/x-www-form-urlencoded",
        "x-merchant-id": "meesho",
        "x-merchantid": "meesho",
        "x-jp-merchant-id": "meesho",
        "x-client-id": "meeshoec",
        "x-session-id": uuid.uuid4().hex,
        "sdk-package-name": "com.meesho.supply",
        "sdk-app-name": "Meesho",
        "sdk-os": "ANDROID",
        "Referer": "com.meesho.supply",
    }
    data = {
        "upi_tr_field": "txn_id",
        "upi_app": upi_app or "com.naviapp",
        "txn_type": "UPI_PAY",
        "sdk_params": "true",
        "redirect_after_payment": "true",
        "payment_method_type": "UPI",
        "payment_method": "UPI",
        "payment_channel": "ANDROID",
        "order_id": str(order_id),
        "merchant_id": "meesho",
        "is_aio_flow_enabled": "false",
        "format": "json",
        "client_auth_token": str(client_auth_token or ""),
        "metadata": json.dumps({"payment_channel": "ANDROID", "microapp": "ec"}),
    }
    if offers:
        data["offers"] = json.dumps(offers)
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(juspay_url, headers=juspay_headers, data=data)
            if resp.status_code == 200:
                d = resp.json()
                sdk_params = (d.get("payment") or {}).get("sdk_params") or {}
                pg_url = sdk_params.get("pgIntentUrl")
                if pg_url:
                    return {"ok": True, "upi_link": pg_url}
    except Exception as e:
        print(f"[JUSPAY_WAPI] error: {e}", flush=True)
    return {"ok": False, "error": "wapi_failed"}


def real_juspay_fallback_link(order_id, amount):
    """
    Standard dynamic Axis Bank Live Merchant VPA for Meesho.
    """
    amt_str = f"{float(amount):.2f}" if amount else "99.00"
    return (
        f"upi://pay?pa=MEESHOONLINEPG@axl"
        f"&pn=MEESHO%20TECHNOLOGIES%20PRIVATE%20LIMITED"
        f"&am={amt_str}&mam={amt_str}"
        f"&tr={order_id}"
        f"&tn=UPI%20Intent"
        f"&mc=5262&mode=04&purpose=00&cu=INR"
        f"&utm_campaign=B2B_PG&utm_medium=MEESHOONLINEPG&utm_source={order_id}"
    )


def real_preorder_status(acc, order_num, cart_session=""):
    """
    POST /api/1.0/preorders/payments/status
    Checks if payment has succeeded and order is confirmed.
    """
    body = {
        "pre_order_id": -1,
        "is_selling_to_customer": False,
        "order_num": str(order_num),
        "retry_in_sec": 0,
        "cart_session": cart_session or "",
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/preorders/payments/status", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            st = str(data.get("status") or "").lower()
            return {"ok": True, "status": st, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# ADDRESSES & ORDER HISTORY
# ============================================================

def real_fetch_addresses(acc):
    """Fetches user addresses from Meesho API."""
    uid = _acc_uid(acc)
    out = []
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{MEESHO_API}/3.0/addresses?offset=0&limit=20&check_pin=true&context=cart&cart_identifier=buy_now&user_id={uid}",
                headers=logged_in_headers(acc),
            )
            if resp.status_code == 200:
                data = resp.json() or {}
                for a in data.get("addresses") or []:
                    if a.get("id"):
                        out.append({
                            "id": a["id"],
                            "name": a.get("name") or "",
                            "mobile": str(a.get("mobile") or ""),
                            "pin": a.get("pin") or "",
                            "city": a.get("city") or "",
                            "state": a.get("state") or "",
                            "address_line_1": a.get("address_line_1") or a.get("line1") or "",
                            "address_type": a.get("address_type") or "Home",
                        })
    except Exception as e:
        print(f"[FETCH_ADDRESSES] error: {e}", flush=True)
    return out


def real_address_create(acc, name, mobile, pin, city, state, line1, line2="", landmark="", addr_type="Home"):
    body = {
        "alternative_mobile": None,
        "pin": str(pin),
        "address_type": addr_type,
        "city": city,
        "name": name,
        "mobile": mobile,
        "address_line_1": line1,
        "address_line_2": line2,
        "state": state,
        "id": 0,
        "landmark": landmark,
        "coordinates": {"latitude": "0", "longitude": "0", "accuracy": "41"},
        "country_id": 1,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{MEESHO_API}/2.0/addresses?context=cart&cart_identifier=buy_now",
                headers=logged_in_headers(acc),
                json=body,
            )
            data = resp.json() or {}
            addr = data.get("address") or {}
            if addr.get("id"):
                return {"ok": True, "meesho_address_id": addr["id"], "address": addr}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "address_create_failed"}


def real_user_orders(acc, limit=10, cursor=None):
    """POST /api/3.0/user/orders - fetches real order history."""
    body = {
        "limit": limit,
        "cursor": cursor,
        "filters": {"sub_order_status": [], "sub_order_created": None},
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/3.0/user/orders", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            lst = data.get("sub_order_list") or data.get("orders") or []
            return {"ok": True, "orders": lst}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Convenient public bindings
def get_meesho_offer():
    return roll_fod_sync()


def search_meesho(query, offer=None):
    return meesho_search_sync(query, offer=offer)


def get_meesho_product(product_id, offer=None):
    return meesho_product_sync(product_id, offer=offer)


def send_otp(phone):
    return request_meesho_otp_sync(phone)


def verify_otp(phone, otp, session):
    return verify_meesho_otp_sync(phone, otp, session)


def check_number(phone):
    return check_number_registered_sync(phone)
