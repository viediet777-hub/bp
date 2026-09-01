"""
meesho.py - Meesho API Integration (Sync for Flask)
OTPLESS Login, FOD Offers, Product Search, Cart
"""
import base64, json, os, random, re, secrets, time, uuid

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ============================================================ CONSTANTS
MEESHO_API = "https://prod.meeshoapi.com/api"
MEESHO_AUTH = "32c4d8137cn9eb493a1921f203173080"
APP_VERSION = "29.1"
APP_VERSION_CODE = "860"
APPLICATION_ID = "com.meesho.supply"

ANON_XO = ("eyJ0eXBlIjoiY29tcG9zaXRlIn0=.eyJqd3QiOiJleUpoYkdjaU9pSklVekkxTmlJc0ltaDBkSEJ6"
           "T2k4dmJXVmxjMmh2TG1OdmJTOXBjMjlmWTI5MWJuUnllVjlqYjJSbElqb2lTVTRpTENKb2RIUndjem92"
           "TDIxbFpYTm9ieTVqYjIwdmRtVnljMmx2YmlJNklqRWlMQ0owZVhBaU9pSktWMVFpZlEuZXlKbGVIQWlP"
           "akU1TkRVek16STVOemdzSW1oMGRIQnpPaTh2YldWbGMyaHZMbU52YlM5aGJtOXVlVzF2ZFhOZmRYTmxj"
           "bDlwWkNJNkltTTVZbUk0WVRVekxUSXhaVE10TkRkallTMWlOamMwTFdGalpURXpOekZtWVRVM01TSXNJ"
           "bWgwZEhCek9pOHZiV1ZsYzJodkxtTnZiUzlwYm5OMFlXNWpaVjlwWkNJNkltUTNNVGc1TW1OaFlUZ3la"
           "alE1TlRFNVpqUmhNek5oTUdVd1lqZzNaamN3SWl3aWFXRjBJam94TnpnM05qVXlPVGM0ZlEuLUN6TXkt"
           "TEJ2VHpGV042VlROMDNKdzItLXhiX0lqSU9VZmpJRTk4eWlQUSIsInhvIjoiIn0=")

MEESHO_RSA_PUBKEY_B64 = ("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAslmrLKGRzVnAtii3o89yI33FXZoRfBJ"
                         "V89PaCTp9Mxu7FgAaAOtaOnB2xWGG2a6Rz6zRzKPilRdAsm5oBW8mm8Uzvt7mbf7c7pjfBrjNdnKji"
                         "/9/zM3fpjh364/GwG3OpyYngD49i09ySljA7Elh97Pp+QJH2z25Xv2eRSHJPizgQ8TE1bJkP9fd9J"
                         "cfpGFyeEJX1bUIbgRlfED2TpJKGeaEfZ9no5+i/rgCaIRO9t86UqgeVJyCyJLnUkrU/ARPj9q/Aij"
                         "JV9kvyPT137UQLO+Cl6nZYOglqGcPnRbGiW6WM7imkSxR2XBn6N4ojf49nJOwnN826hkdH5JaPJ1p"
                         "AQIDAQAB")

OTPLESS_APP_ID = "XN07RN1IQC548C9YK5I4"
OTPLESS_PACKAGE = "com.meesho.supply"
OTPLESS_LOGIN_URI = "otpless.xn07rn1iqc548c9yk5i4://otpless"
OTPLESS_OTP_HASH = "oBcOM6bXKNc"
OTPLESS_APP_SIGNATURE = "oBcOM6bXKNcqouiPFcR1ur60Z6myTuVIDNSNWuKOlzU"
OTPLESS_UA = "okhttp/4.9.0"
OTPLESS_ORIGIN = "https://otpless.com"
KEY_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+"

DEVICE_INFO = {"platform": "android", "vendor": "motorola", "browser": "", "connection": "",
    "language": "en-IN", "cookieEnabled": "", "screenWidth": 1080, "screenHeight": 2225,
    "userAgent": "Dalvik/2.1.0 (Linux; U; Android 12; moto g(60) Build/S2RI32.32-20-9-9-2) otplesssdk",
    "timezoneOffset": 330, "cpuArchitecture": "aarch64"}

DEVICE_POOL = [
    {"brand": "motorola", "manufacturer": "motorola", "model": "moto g(60)", "os_version": "12", "os": "Android", "screen_dpi": 400, "screen_width": 1080, "screen_height": 2225},
    {"brand": "samsung", "manufacturer": "samsung", "model": "SM-M315F", "os_version": "13", "os": "Android", "screen_dpi": 420, "screen_width": 1080, "screen_height": 2400},
    {"brand": "samsung", "manufacturer": "samsung", "model": "SM-A546E", "os_version": "14", "os": "Android", "screen_dpi": 450, "screen_width": 1080, "screen_height": 2340},
    {"brand": "xiaomi", "manufacturer": "Xiaomi", "model": "M2010J19SI", "os_version": "12", "os": "Android", "screen_dpi": 440, "screen_width": 1080, "screen_height": 2400},
    {"brand": "realme", "manufacturer": "realme", "model": "RMX3363", "os_version": "13", "os": "Android", "screen_dpi": 480, "screen_width": 1080, "screen_height": 2400},
    {"brand": "vivo", "manufacturer": "vivo", "model": "V2130", "os_version": "13", "os": "Android", "screen_dpi": 440, "screen_width": 1080, "screen_height": 2376},
    {"brand": "oneplus", "manufacturer": "OnePlus", "model": "CPH2583", "os_version": "14", "os": "Android", "screen_dpi": 450, "screen_width": 1240, "screen_height": 2772},
]

APP_POOL = [
    {"id": 19, "package_name": "com.meesho.supply"}, {"id": 68, "package_name": "com.flipkart.android"},
    {"id": 112, "package_name": "com.amazon.mShop.android.shopping"}, {"id": 339, "package_name": "in.swiggy.android"},
    {"id": 106, "package_name": "org.telegram.messenger"}, {"id": 156, "package_name": "com.whatsapp"},
    {"id": 92, "package_name": "com.instagram.android"}, {"id": 77, "package_name": "com.facebook.katana"},
    {"id": 88, "package_name": "com.truecaller"}, {"id": 44, "package_name": "com.phonepe.app"},
]

BUCKET_POOL = ["180", "180", "180", "175", "150", "135", "120", "100", "90", "75", "60", ""]
FOD_FALLBACK = {"offer_title": "Upto", "offer_text": "\u20b975 OFF", "offer_subtitle": "on 1st order", "offer_duration": 3, "max_offer_value": 75}

SEARCH_FILTER = {"min_prices": [], "max_prices": [], "discount_values": [], "ratings": [],
    "mall_verified": False, "sizes": [], "colors": [], "fabric": [], "bottom_lengths": [],
    "fit_garments": [], "occasions": [], "sleeves": [], "split_sleeves": [], "components": [],
    "add_on": [], "collection_filters": [], "supplier_ids": [], "l3_categories": [],
    "l2_categories": [], "product_ids": [], "exclude_shop_page_products": False,
    "exclude_sponsored_catalogs": False, "return_options": [], "b2c_vip_badges": [],
    "price_band": [], "variants": []}

# ============================================================ CRYPTO
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
    try: return float(v or default)
    except Exception: return default

def _safe_int(v):
    try:
        if v is None or str(v).lower() in ("null", "none", "", "undefined"):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None

# ============================================================ DEVICE / FOD
def _random_device():
    dev = dict(random.choice(DEVICE_POOL))
    dev["gaid"] = str(uuid.uuid4())
    dev["session_count"] = random.randint(1, 6)
    dev["offer_bucket"] = random.choice(BUCKET_POOL)
    dev["apps_installed"] = [APP_POOL[0]] + random.sample(APP_POOL[1:], random.randint(4, 7))
    return dev

def _fod_body(dev):
    return {
        "offer_bucket": dev["offer_bucket"], "from_language_modal": False,
        "brand": dev["brand"], "manufacturer": dev["manufacturer"], "model": dev["model"],
        "os_version": dev["os_version"], "os": dev["os"], "carrier": "",
        "connection_type": random.choice(["WIFI", "MOBILE_DATA"]),
        "screen_dpi": dev["screen_dpi"], "screen_width": dev["screen_width"], "screen_height": dev["screen_height"],
        "apps_installed": dev["apps_installed"],
        "referrer_url": "utm_source=google-adwords&utm_medium=cpc&utm_campaign=first_order_discount_150",
        "campaign_id": "acquisition_fod_150", "install_referrer": "utm_source=google-play&utm_medium=organic",
    }

def _api_headers(instance_id, xo, context, session_id=None, gaid=None, session_count=None, ua=None):
    h = {"authorization": MEESHO_AUTH, "app-version": APP_VERSION, "app-version-code": APP_VERSION_CODE,
         "instance-id": instance_id, "country-iso": "in", "application-id": APPLICATION_ID,
         "app-session-id": session_id or uuid.uuid4().hex, "app-sdk-version": "34",
         "app-client-id": "android", "shield-session-id": "", "xo": xo,
         "app-iso-language-code": "en", "meesho-user-context": context,
         "content-type": "application/json; charset=UTF-8", "user-agent": ua or "Cronet",
         "accept-encoding": "gzip, deflate"}
    if gaid: h["app-gaid"] = gaid
    if session_count is not None: h["app-session-count"] = str(session_count)
    return h

def _map_fod(resp):
    v3 = (resp or {}).get("surgical_first_order_discount_v3") or {}
    if not v3.get("enabled", False):
        return {"ok": False, "message": "No FOD offer available."}
    offer = v3.get("offer") or {}
    if not offer:
        return {"ok": False, "message": "No FOD offer available."}
    return {"ok": True, "offer": {
        "title": offer.get("offer_title") or "Upto", "text": offer.get("offer_text") or "",
        "subtitle": offer.get("offer_subtitle") or "on 1st order",
        "duration": offer.get("offer_duration"), "bucket": offer.get("max_offer_value")}}

_XO_IDX = 0

def _next_anon_xo():
    global _XO_IDX
    pool = [("", ANON_XO)]
    xo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xos")
    try:
        for name in sorted(os.listdir(xo_dir)):
            if name.endswith(".txt"):
                xo = open(os.path.join(xo_dir, name)).read().strip()
                if xo and len(xo) > 100:
                    pool.append(("", xo))
    except Exception:
        pass
    entry = pool[_XO_IDX % len(pool)]
    _XO_IDX += 1
    return entry[1]

# ============================================================ SYNC FOD
def fetch_fod_sync(device=None):
    dev = device or _random_device()
    ua = f"Dalvik/2.1.0 (Linux; U; Android {dev['os_version']}; {dev['model']} Build/) Cronet/137.0.7100.61"
    xo = _next_anon_xo()
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/anonymous/fod-personalisation",
                headers=_api_headers(uuid.uuid4().hex, xo, "anonymous", gaid=dev["gaid"], session_count=dev["session_count"], ua=ua),
                json=_fod_body(dev))
            if resp.status_code == 200:
                mapped = _map_fod(resp.json())
                if mapped["ok"]:
                    mapped["offer"]["device"] = dev["model"]
                    return mapped
    except Exception:
        pass
    fallback = _map_fod({"surgical_first_order_discount_v3": {"enabled": True, "offer": FOD_FALLBACK}})
    fallback["offer"]["device"] = dev["model"]
    return fallback

# ============================================================ SYNC SEARCH
def _prod_headers(xo="", instance_id=""):
    return {"Host": "prod.meeshoapi.com", "authorization": MEESHO_AUTH,
         "x-wishlist-aggregation-required": "false", "app-version": APP_VERSION,
         "app-version-code": APP_VERSION_CODE, "instance-id": instance_id or uuid.uuid4().hex,
         "country-iso": "in", "application-id": APPLICATION_ID, "app-session-id": str(uuid.uuid4()),
         "app-sdk-version": "33", "app-client-id": "android", "shield-session-id": "",
         "xo": xo or ANON_XO, "app-iso-language-code": "en", "meesho-user-context": "anonymous",
         "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
         "User-Agent": "okhttp/4.9.0"}

def meesho_search_sync(query, cursor=None, offset=0, session_id=None, offer=None):
    filt = dict(SEARCH_FILTER)
    filt["query"] = query
    body = {"filter": filt, "search_session_id": session_id, "cursor": cursor,
        "offset": offset, "limit": 20, "supplier_id": None, "featured_collection_type": None,
        "meta": {"recent_searches": [query]}, "retry_count": 0, "product_listing_page_id": None}
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
                    out.append({"product_id": int(c.get("hero_pid") or c.get("id") or 0),
                        "catalog_id": int(c.get("id") or 0), "name": c.get("name"),
                        "price": final_price, "fod_price": final_price if final_price != price else None,
                        "fod_savings": sav, "original_price": original or price,
                        "discount_text": (sav if pct else c.get("discount_text")) or "",
                        "rating": {"average": rev.get("average_rating"), "count": rev.get("rating_count")},
                        "image": img or (f"https://images.meesho.com/images/catalogs/{c.get('id')}/cover/1/_512.jpg" if c.get("id") else ""),
                        "supplier_id": None})
                return {"catalogs": out, "cursor": data.get("cursor"), "search_session_id": data.get("search_session_id")}
    except Exception:
        pass
    return None

# ============================================================ SYNC PRODUCT
def meesho_product_sync(product_id, offer=None):
    headers = _prod_headers()
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            static = client.get(f"{MEESHO_API}/3.0/product/static",
                params={"id": product_id, "context": "widget", "ad_active": "true"}, headers=headers)
            dynamic = client.get(f"{MEESHO_API}/3.0/product/dynamic",
                params={"id": product_id, "context": "widget", "origin": "widget"}, headers=headers)
            sp = (static.json() if static.status_code == 200 else {}).get("product") or {}
            dp = (dynamic.json() if dynamic.status_code == 200 else {}).get("product") or {}
            if not sp and not dp:
                return None
            p = sp or dp
            suppliers = dp.get("suppliers") or sp.get("suppliers") or []
            sup = suppliers[0] if isinstance(suppliers, list) and suppliers else {}
            pv = sup.get("prepaid_price_view") or {}
            final = _num(pv.get("prepaid_price") or dp.get("min_product_price") or sup.get("price") or p.get("mrp"))
            mrp = _num(sup.get("original_price") or p.get("mrp") or final)
            imgs = dp.get("catalog_product_images") or sp.get("catalog_product_images") or []
            images = [im.get("url") if isinstance(im, dict) else str(im) for im in imgs[:6] if im]
            sizes = []
            for it in (sup.get("inventory") or []):
                name = it.get("variation_name") or it.get("variation")
                if name:
                    sizes.append({"name": name, "id": it.get("variation_id")})
            fod_price, sav, pct = _apply_fod(final, offer)
            return {"product_id": int(p.get("id") or product_id), "name": p.get("name") or "Product",
                "price": fod_price, "fod_price": fod_price if fod_price != final else None, "fod_savings": sav,
                "mrp": mrp, "list_price": final, "original_price": mrp, "images": images,
                "image": images[0] if images else None, "sizes": sizes,
                "supplier_id": sup.get("id"), "supplier_name": sup.get("name"),
                "in_stock": bool(sup.get("in_stock", True)) if "in_stock" in sup else True,
                "discount_text": (sav if pct else sup.get("discount_text")) or ""}
    except Exception:
        return None

# ============================================================ FOD HELPERS
def _apply_fod(price, offer=None):
    if not offer:
        return _num(price), "", None
    pct = _num(offer.get("pct"))
    flat = _num(offer.get("flat"))
    cb = _num(offer.get("cashback"))
    bucket = _num(offer.get("bucket"))
    display_bucket = _num(offer.get("display_bucket"))  # Always 180 for user display
    try:
        price = float(price or 0)
    except Exception:
        price = 0.0
    if pct >= 100:
        return 0.0, "100% FREE", 100
    if pct and pct < 100:
        return round(max(0, price - price * pct / 100), 2), f"{int(pct)}% OFF", pct
    if flat:
        return round(max(0, price - flat), 2), f"\u20b9{int(flat)} OFF", flat
    if bucket and bucket < price:
        # Use display_bucket (180) for text, actual bucket for price calculation
        display_text = f"Upto \u20b9{int(display_bucket)} OFF" if display_bucket else f"Upto \u20b9{int(bucket)} OFF"
        return round(max(0, price - bucket), 2), display_text, bucket
    if cb:
        return round(max(0, price - cb), 2), f"\u20b9{int(cb)} CASHBACK", cb
    return price, "", None

def roll_fod_sync():
    best = None
    for i in range(5):
        try:
            dev = _random_device()
            if i < 3:
                dev["offer_bucket"] = "180"
            res = fetch_fod_sync(device=dev)
            if res.get("ok") and res.get("offer"):
                offer = dict(res["offer"])
                offer.setdefault("id", str(offer.get("bucket") or "live").lower().replace(" ", ""))
                offer.setdefault("title", "OFFER")
                offer.setdefault("text", "")
                offer.setdefault("subtitle", "on 1st order")
                offer["live"] = True
                buck = int(offer.get("bucket") or 0)
                # Always show 180 OFF to user, keep actual bucket for internal use
                offer["display_bucket"] = 180
                offer["display_text"] = "Upto \u20b9180 OFF"
                if buck >= 180:
                    return {"ok": True, "offer": offer}
                if not best or buck > int(best.get("bucket") or 0):
                    best = offer
        except Exception:
            continue
    if best:
        # Ensure display_bucket is set on best offer too
        best.setdefault("display_bucket", 180)
        best.setdefault("display_text", "Upto \u20b9180 OFF")
        return {"ok": True, "offer": best}
    return {"ok": False, "error": "Could not fetch offer."}

# ============================================================ OTPLESS SYNC
def _ts_id():
    return f"{uuid.uuid4()}-{int(time.time() * 1000)}"

def _build_intent_body(phone, ts_id, in_id):
    ga_id = str(uuid.uuid4())
    app_info = {"platform": "android", "manufacturer": "motorola", "androidVersion": "31",
        "packageName": OTPLESS_PACKAGE, "model": "moto g(60)", "appSignature": OTPLESS_APP_SIGNATURE,
        "hasTelegram": "true", "hasMiChat": "false", "hasLine": "false", "hasDiscord": "false",
        "hasSlack": "false", "hasViber": "false", "hasSignal": "false", "hasBotim": "false",
        "hasTrueCaller": "false", "hasWhatsapp": "false", "sdkVersion": "1.3.3",
        "inId": in_id, "tsId": ts_id, "isSilentAuthSupported": "true", "isWebAuthnSupported": "true",
        "isCellularDataEnabled": "false", "secureDetail": {"simDetail": {"currentTransportType": "WiFi", "isSimInserted": "false"}}}
    device_id_info = {"androidId": "aa5e8c37ca4077f7",
        "mediaId": "044507f8402972db73de4f938b76584c89336763bec73f4a9f97b3e36136862f", "gaid": ga_id}
    metadata = json.dumps({"appInfo": json.dumps(app_info), "deviceInfo": json.dumps(DEVICE_INFO), "deviceIdInfo": json.dumps(device_id_info)})
    return {"selectedCountryCode": "+91", "mobile": f"91{phone}", "silentAuthEnabled": False,
        "hasWhatsapp": "false", "deliveryChannel": "SMS", "metadata": metadata,
        "triggerWebauthn": False, "telephonyInfo": {"isMobileDataOn": False, "hasReadPhoneStatePermission": False, "all": [{}]},
        "clientMetaData": json.dumps({"tid": secrets.token_urlsafe(12)[:16]}),
        "asId": "", "isViSnaWhitelisted": True, "isAirtelSnaWhitelisted": True, "isAutoIntent": True,
        "origin": "https://otpless.com", "version": "V4", "tsId": ts_id, "inId": in_id,
        "deviceInfo": json.dumps(DEVICE_INFO), "loginUri": OTPLESS_LOGIN_URI,
        "appId": OTPLESS_APP_ID, "isHeadless": True, "packageName": OTPLESS_PACKAGE,
        "package": OTPLESS_PACKAGE, "otpHash": OTPLESS_OTP_HASH, "platform": "HEADLESS"}

def request_meesho_otp_sync(phone):
    ts_id, in_id = _ts_id(), _ts_id()
    headers = {"user-agent": OTPLESS_UA}
    with httpx.Client(timeout=20.0) as client:
        state_resp = client.get("https://user-auth.otpless.app/v2/state",
            params={"origin": OTPLESS_ORIGIN, "version": "V3", "tsId": ts_id, "inId": in_id,
                "isHeadless": "true", "platform": "android", "isLoginPage": "false",
                "packageName": OTPLESS_PACKAGE, "package": OTPLESS_PACKAGE,
                "appId": OTPLESS_APP_ID, "loginUri": OTPLESS_LOGIN_URI, "deviceInfo": json.dumps(DEVICE_INFO)},
            headers=headers)
        state = (state_resp.json() or {}).get("state")
        if not state:
            return {"ok": False, "error": "State failed."}
        intent_resp = client.post(f"https://user-auth.otpless.app/v3/lp/user/transaction/intent/{state}",
            headers={**headers, "content-type": "application/json; charset=utf-8"},
            json=_build_intent_body(phone, ts_id, in_id))
        data = intent_resp.json() or {}
        leap = data.get("quantumLeap") or {}
        if not leap.get("uid") or not leap.get("channelAuthToken"):
            return {"ok": False, "error": "OTP rejected"}
        return {"ok": True, "session": {"state": state, "uid": leap["uid"], "token": leap["channelAuthToken"],
            "as_id": leap.get("asId", ""), "ts_id": ts_id, "in_id": in_id, "instance_id": uuid.uuid4().hex}}

def verify_meesho_otp_sync(phone, otp, session):
    otp_headers = {"user-agent": OTPLESS_UA, "content-type": "application/json; charset=utf-8"}
    otp_body = {"selectedCountryCode": "91", "mobile": phone, "otp": otp, "value": f"91{phone}",
        "isOTPAutoRead": "false", "uid": session["uid"], "token": session["token"],
        "asId": session["as_id"], "origin": OTPLESS_ORIGIN, "version": "V4",
        "tsId": session["ts_id"], "inId": session["in_id"],
        "deviceInfo": json.dumps(DEVICE_INFO, separators=(",", ":")),
        "loginUri": OTPLESS_LOGIN_URI, "appId": OTPLESS_APP_ID, "isHeadless": True,
        "packageName": OTPLESS_PACKAGE, "package": OTPLESS_PACKAGE,
        "otpHash": OTPLESS_OTP_HASH, "platform": "HEADLESS"}
    with httpx.Client(timeout=20.0) as client:
        verify_resp = client.post(f"https://user-auth.otpless.app/v3/lp/user/transaction/otp/{session['state']}",
            headers=otp_headers, json=otp_body)
        data = verify_resp.json() or {}
        one_tap = data.get("oneTap") or {}
        token = one_tap.get("token")
        id_token = (one_tap.get("merchantUserInfo") or {}).get("idToken")
        if not token or not id_token:
            return {"ok": False, "error": "OTP verify failed"}
        key = _gen_key()
        login_body = {"login_type": "otpless", "otpless": {"token": token,
            "id_token": _aes_gcm_encrypt(id_token.encode(), key), "aes_key_encrypted": _rsa_encrypt(key), "version": "v2"},
            "ga_id": str(uuid.uuid4())}
        login_resp = client.post(f"{MEESHO_API}/2.0/user/login",
            headers=_api_headers(session["instance_id"], ANON_XO, "anonymous"), json=login_body)
        if login_resp.status_code != 200:
            return {"ok": False, "error": f"Login failed HTTP {login_resp.status_code}"}
        ldata = login_resp.json() or {}
        user = ldata.get("user") or {}
        xo = (ldata.get("xoox") or {}).get("xo") or ""
        if not xo:
            return {"ok": False, "error": "Login failed: no xo."}
        return {"ok": True, "user_id": user.get("user_id"), "phone": user.get("phone"),
            "xo": xo, "xo_exp": _xo_expiry(xo), "instance_id": session["instance_id"],
            "is_new": bool(user.get("new"))}

def check_number_registered_sync(phone):
    ts_id, in_id = _ts_id(), _ts_id()
    headers = {"user-agent": OTPLESS_UA}
    with httpx.Client(timeout=20.0) as client:
        state_resp = client.get("https://user-auth.otpless.app/v2/state",
            params={"origin": OTPLESS_ORIGIN, "version": "V3", "tsId": ts_id, "inId": in_id,
                "isHeadless": "true", "platform": "android", "isLoginPage": "false",
                "packageName": OTPLESS_PACKAGE, "package": OTPLESS_PACKAGE,
                "appId": OTPLESS_APP_ID, "loginUri": OTPLESS_LOGIN_URI, "deviceInfo": json.dumps(DEVICE_INFO)},
            headers=headers)
        state = (state_resp.json() or {}).get("state")
        if not state:
            return {"registered": False, "phone": phone, "error": "state_failed"}
        intent_resp = client.post(f"https://user-auth.otpless.app/v3/lp/user/transaction/intent/{state}",
            headers={**headers, "content-type": "application/json; charset=utf-8"},
            json=_build_intent_body(phone, ts_id, in_id))
        data = intent_resp.json() or {}
        leap = data.get("quantumLeap") or {}
        if leap.get("uid") and leap.get("channelAuthToken"):
            return {"registered": True, "phone": phone}
        return {"registered": False, "phone": phone, "error": data.get("errorMessage", "")}

# ============================================================ PUBLIC API
def get_meesho_offer():
    return roll_fod_sync()

def search_meesho(query, offer=None):
    return meesho_search_sync(query, offer=offer)

def get_meesho_product(product_id, offer=None):
    return meesho_product_sync(product_id, offer=offer)

def send_otp(phone):
    phone = str(phone)[-10:]
    try:
        return request_meesho_otp_sync(phone)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def verify_otp(phone, otp, session):
    try:
        return verify_meesho_otp_sync(phone, otp, session)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_number(phone):
    try:
        return check_number_registered_sync(phone)
    except Exception as e:
        return {"registered": False, "phone": phone, "error": str(e)}
