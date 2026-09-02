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

def _pos_int(v):
    """Like _safe_int but 0 also means 'absent' (our DB defaults ids to 0 and
    Meesho expects null there, not 0)."""
    n = _safe_int(v)
    return n if n else None

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
         "app-session-id": session_id or uuid.uuid4().hex, "app-sdk-version": "30",
         "app-client-id": "android", "shield-session-id": "", "xo": xo,
         "app-iso-language-code": "en", "meesho-user-context": context,
         "content-type": "application/json; charset=UTF-8", "user-agent": ua or "okhttp/4.9.0",
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
         "app-sdk-version": "30", "app-client-id": "android", "shield-session-id": "",
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
                # Live shape is {"supplierId":..,"variation":{"id":809,"name":"M",..},"in_stock":..}
                # so the variation id is nested; only older/other shapes have it top-level.
                # Missing ids make app.py skip the real-cart push (it needs variation_id).
                var = it.get("variation")
                var = var if isinstance(var, dict) else {}
                raw_name = it.get("variation_name") or var.get("name") or var.get("size") \
                    or var.get("value") or (it.get("variation") if not var else "") or ""
                name = str(raw_name)
                raw_vid = it.get("variation_id") or var.get("id") or it.get("id")
                if isinstance(raw_vid, dict):
                    vid = raw_vid.get("id")
                else:
                    vid = raw_vid
                if name.strip():
                    sizes.append({"name": name.strip(), "id": _safe_int(vid) or None,
                                  "in_stock": bool(it.get("in_stock", True))})
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
        # Video: bucket 180 but display 135 (actual offer), use bucket for calc, actual bucket for text
        actual = int(bucket)
        txt = f"Upto \u20b9{actual} OFF"
        return round(max(0, price - bucket), 2), txt, bucket
    if cb:
        return round(max(0, price - cb), 2), f"\u20b9{int(cb)} CASHBACK", cb
    return price, "", None

def roll_fod_sync(for_acc=None):
    """Try to get best available FOD. If for_acc provided, use its anon_xo/device to get that account's real bucket (120 etc)."""
    best = None
    # If account has anon_xo, try that exact identity first (competitor's 120 comes from this)
    if for_acc and for_acc.get("anon_xo"):
        try:
            import json as _j
            ident = for_acc.get("identity")
            if isinstance(ident, str):
                try: ident = _j.loads(ident)
                except: ident = {}
            if not isinstance(ident, dict): ident = {}
            elif "identity" in ident and isinstance(ident.get("identity"), dict):
                ident = ident.get("identity")
            dev = dict(_random_device())
            if ident.get("make"): 
                # keep brand consistent with make
                dev["brand"] = ident.get("make").lower() if ident.get("make").lower() in ["oneplus","xiaomi","samsung","motorola"] else dev["brand"]
            if ident.get("model"): dev["model"] = ident.get("model")
            if ident.get("android"): dev["os_version"] = str(ident.get("android"))
            if ident.get("screen_dpi"): dev["screen_dpi"] = int(ident.get("screen_dpi"))
            if ident.get("screen_width"): dev["screen_width"] = int(ident.get("screen_width"))
            if ident.get("screen_height"): dev["screen_height"] = int(ident.get("screen_height"))
            dev["offer_bucket"] = ""  # let Meesho decide for this anon identity
            xo_to_use = for_acc.get("anon_xo")
            # Direct FOD call with that specific xo (not random pool) to get true bucket like 120
            ua = f"Dalvik/2.1.0 (Linux; U; Android {dev['os_version']}; {dev['model']} Build/) Cronet/137.0.7100.61"
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(f"{MEESHO_API}/1.0/anonymous/fod-personalisation",
                        headers=_api_headers(uuid.uuid4().hex, xo_to_use, "anonymous", gaid=dev["gaid"], session_count=dev["session_count"], ua=ua),
                        json=_fod_body(dev))
                    if resp.status_code == 200:
                        mapped = _map_fod(resp.json())
                        if mapped["ok"] and mapped["offer"]:
                            offer = dict(mapped["offer"])
                            buck = int(offer.get("bucket") or 0)
                            offer["display_bucket"] = buck
                            offer["display_text"] = f"Upto \u20b9{buck} OFF"
                            offer["live"] = True
                            offer["title"] = "Upto"
                            offer["subtitle"] = "on 1st order"
                            return {"ok": True, "offer": offer}
            except: pass
        except Exception:
            pass
    for i in range(10):
        try:
            dev = _random_device()
            # Try high buckets first: 135,130,120,180 etc. (file has 135,120)
            if i < 3:
                dev["offer_bucket"] = random.choice(["135","130","120","180"])
            elif i < 6:
                dev["offer_bucket"] = random.choice(["120","135","125","150"])
            res = fetch_fod_sync(device=dev)
            if res.get("ok") and res.get("offer"):
                offer = dict(res["offer"])
                offer.setdefault("id", str(offer.get("bucket") or "live").lower().replace(" ", ""))
                offer.setdefault("title", "Upto")
                offer.setdefault("text", offer.get("offer_text") or "")
                offer.setdefault("subtitle", "on 1st order")
                offer["live"] = True
                buck = int(offer.get("bucket") or 0)
                # Show REAL bucket value (like competitor's 120), not hardcoded 180
                offer["display_bucket"] = buck
                offer["display_text"] = f"Upto \u20b9{buck} OFF"
                if buck >= 135:
                    return {"ok": True, "offer": offer}
                if not best or buck > int(best.get("bucket") or 0):
                    best = offer
        except Exception:
            continue
    if best:
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
    print(f"[OTP_VERIFY] phone={phone} otp={otp} state={session['state'][:20]}...", flush=True)
    with httpx.Client(timeout=20.0) as client:
        verify_resp = client.post(f"https://user-auth.otpless.app/v3/lp/user/transaction/otp/{session['state']}",
            headers=otp_headers, json=otp_body)
        data = verify_resp.json() or {}
        print(f"[OTP_VERIFY] otple_resp status={verify_resp.status_code} keys={list(data.keys())}", flush=True)
        auth_detail = data.get("authDetail") or {}
        print(f"[OTP_VERIFY] authDetail={str(auth_detail)[:200]}", flush=True)
        one_tap = data.get("oneTap") or {}
        token = one_tap.get("token")
        id_token = (one_tap.get("merchantUserInfo") or {}).get("idToken")
        if not token or not id_token:
            err_detail = auth_detail.get("status") or data.get("errorMessage") or str(data)[:300]
            print(f"[OTP_VERIFY] FAILED: {err_detail}", flush=True)
            return {"ok": False, "error": f"OTP verify failed: {err_detail}"}
        print(f"[OTP_VERIFY] OTP verified, logging in to Meesho...", flush=True)
        key = _gen_key()
        login_body = {"login_type": "otpless", "otpless": {"token": token,
            "id_token": _aes_gcm_encrypt(id_token.encode(), key), "aes_key_encrypted": _rsa_encrypt(key), "version": "v2"},
            "ga_id": str(uuid.uuid4())}
        login_resp = client.post(f"{MEESHO_API}/2.0/user/login",
            headers=_api_headers(session["instance_id"], ANON_XO, "anonymous"), json=login_body)
        print(f"[OTP_VERIFY] meesho_login status={login_resp.status_code}", flush=True)
        if login_resp.status_code != 200:
            return {"ok": False, "error": f"Login failed HTTP {login_resp.status_code}"}
        ldata = login_resp.json() or {}
        user = ldata.get("user") or {}
        xo = (ldata.get("xoox") or {}).get("xo") or ""
        print(f"[OTP_VERIFY] login result: user_id={user.get('user_id')} xo={'yes' if xo else 'no'} new={user.get('new')}", flush=True)
        if not xo:
            print(f"[OTP_VERIFY] login raw: {str(ldata)[:500]}", flush=True)
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

# ============================================================ REAL MEESHO CART/CHECKOUT/ORDER API

def _acc_uid(acc):
    """Meesho's numeric user id for an account row.

    meesho_accounts rows store the TELEGRAM id in 'user_id' and the Meesho id in
    'meesho_user_id'. Every cart/checkout call (and the app-user-id header) needs
    the Meesho one — sending the Telegram id makes Meesho treat the request as a
    different user, so adds land nowhere and review comes back empty.
    """
    if not isinstance(acc, dict):
        return 0
    for key in ("meesho_user_id", "user_id"):
        v = acc.get(key)
        if v in (None, "", 0, "0"):
            continue
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            continue
    return 0


def logged_in_headers(acc, location=None):
    """Build headers for logged-in Meesho API calls"""
    phone = acc.get("phone", "")
    uid = str(_acc_uid(acc))
    instance_id = acc.get("instance_id", "")
    xo = acc.get("xo", "")
    app_sid = acc.get("app_session_id") or uuid.uuid4().hex
    h = _api_headers(instance_id, xo, "logged_in",
                     session_id=app_sid,
                     ua="okhttp/4.9.0")
    h["app-version"] = acc.get("app_version") or "29.1"
    h["app-version-code"] = acc.get("app_version_code") or "858"
    h["app-sdk-version"] = "30"
    h["app-user-id"] = uid
    h["shield-session-id"] = acc.get("shield_session_id") or ""
    h["accept-encoding"] = "gzip"
    if phone and not phone.startswith("xxxx"):
        h["u-token"] = base64.b64encode(("+91" + phone).encode()).decode()
    if location:
        h["app-user-location"] = base64.b64encode(json.dumps(location).encode()).decode()
    else:
        h["app-user-location"] = base64.b64encode(json.dumps({
            "lat": "22.6984", "long": "75.9292", "pincode": "452010",
            "city": "indore", "address_id": ""
        }).encode()).decode()
    return h


def _cart_add_once(acc, body):
    """Single POST to /api/1.0/cart/add, returns parsed result."""
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/add",
                               headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            if data.get("success") or data.get("status") == "SUCCESS":
                result = data.get("result", {})
                return {"ok": True, "data": data, "result": result, "status": resp.status_code}
            return {"ok": False, "data": data, "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e), "data": {}}


def real_cart_add(acc, product_id, supplier_id, variation_id, variation, qty=1, cart_session=None):
    """Add product to real Meesho cart via /api/1.0/cart/add.
    Captured real app uses context='pdp' (folder 56). We try pdp first,
    then pdl fallback, and also retry with basic_return_price on CART_OOS."""
    pid = int(product_id) if product_id else 0
    vid = _pos_int(variation_id)
    sid = _pos_int(supplier_id)
    base_item = {
        "identifier": "buy_now",
        "product_id": pid,
        "supplier_id": sid,
        "variation_id": vid,
        "variation": variation or "",
        "quantity": int(qty) if qty else 1,
        "selected_price_type_id": "premium_return_price",
        "client_metadata": None,
    }
    for context in ("pdp", "pdl"):
        body = {
            "context": context,
            "identifier": "buy_now",
            "cart_session": cart_session or None,
            "replaceable": False,
            "items": [dict(base_item)],
            "address_id": None,
            "user_id": _acc_uid(acc),
        }
        r = _cart_add_once(acc, body)
        if r.get("ok"):
            data = r["data"]
            result = r["result"]
            print(f"[CART_ADD] ok context={context} cs={str(data.get('cart_session'))[:30]}", flush=True)
            return {
                "ok": True,
                "cart_session": data.get("cart_session"),
                "effective_total": result.get("effective_total"),
                "effective_total_for_upi_plugin": result.get("effective_total_for_upi_plugin"),
                "total_quantity": result.get("total_quantity"),
                "splits": result.get("splits", []),
                "price_break_up": result.get("price_break_up", []),
            }
        data = r.get("data", {})
        err_type = data.get("error_type") or data.get("message") or data.get("error") or r.get("error") or ""
        # CART_OOS -> retry with basic price
        ecode = (data.get("error") or {}).get("code") if isinstance(data.get("error"), dict) else None
        if ecode == "CART_OOS" or "CART_OOS" in str(data):
            base_item["selected_price_type_id"] = "basic_return_price"
            body["items"] = [dict(base_item)]
            r2 = _cart_add_once(acc, body)
            if r2.get("ok"):
                data2 = r2["data"]
                result2 = r2["result"]
                print(f"[CART_ADD] ok after CART_OOS retry context={context}", flush=True)
                return {
                    "ok": True,
                    "cart_session": data2.get("cart_session"),
                    "effective_total": result2.get("effective_total"),
                    "effective_total_for_upi_plugin": result2.get("effective_total_for_upi_plugin"),
                    "total_quantity": result2.get("total_quantity"),
                    "splits": result2.get("splits", []),
                    "price_break_up": result2.get("price_break_up", []),
                }
            data = r2.get("data", data)
            err_type = data.get("error_type") or str(data)[:300]
        print(f"[CART_ADD] FAILED context={context}: {err_type} raw={str(data)[:400]}", flush=True)
        # If context-specific error (e.g. invalid context), try next context
        if "context" in str(err_type).lower() or "identifier" in str(err_type).lower():
            continue
        # Non-context error -> don't retry other context, just return
        if context == "pdp":
            # still try pdl fallback for generic failures
            continue
        return {"ok": False, "error": err_type, "raw": data}
    return {"ok": False, "error": "cart add failed (both pdp/pdl)", "raw": {}}


def real_cart_review(acc, cart_session=None):
    """Get real Meesho cart review via /api/9.0/cart (review flow).
    CRITICAL: context='review' + identifier='buy_now' matches the real app's
    cart-review call. Using 'atc_cart_v2' + 'default' gives an empty cart."""
    body = {
        "context": "review", "identifier": "buy_now",
        "cart_session": cart_session or "",
        "dest_pin": None, "address_id": None, "customerAmount": None,
        "payment_modes": None, "replaceable": None, "item": None,
        "payment_instrument": None, "bank_offers": None,
        "filter_products": True, "is_self_pickup": None,
        "self_pickup_address": None, "is_emi": None,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(f"{MEESHO_API}/9.0/cart",
                               headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            if data.get("success"):
                result = data.get("result", {})
                items = []
                for s in (result.get("splits") or []):
                    sup = s.get("supplier") or {}
                    for p in (s.get("products") or []):
                        imgs = p.get("images") or []
                        items.append({
                            "identifier": p.get("identifier"),
                            "product_id": p.get("product_id"),
                            "catalog_id": (p.get("catalog") or {}).get("id") if isinstance(p.get("catalog"), dict) else None,
                            "name": p.get("name"),
                            "supplier_id": sup.get("id"),
                            "supplier_name": sup.get("name"),
                            "variation_id": p.get("variation_id"),
                            "variation": p.get("variation"),
                            "quantity": int(p.get("quantity") or 1),
                            "max_quantity": int(p.get("max_quantity") or 10),
                            "price": p.get("price"),
                            "mrp": p.get("mrp"),
                            "original_price": p.get("original_price"),
                            "image": (imgs[0] if imgs else None),
                            "images": imgs,
                            "price_type_id": (p.get("price_unbundling") or {}).get("selected_price_type_id"),
                            "discount_text": p.get("discount_text"),
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
                        "address_line_2": addr_raw.get("address_line_2"),
                        "landmark": addr_raw.get("landmark"),
                        "address_type": addr_raw.get("address_type"),
                        "latitude": coords.get("latitude") if isinstance(coords, dict) else addr_raw.get("latitude"),
                        "longitude": coords.get("longitude") if isinstance(coords, dict) else addr_raw.get("longitude"),
                        "pin_serviceable": addr_raw.get("pin_serviceable", True),
                    }
                um = result.get("user_meta") or {}
                return {
                    "ok": True,
                    "cart_session": data.get("cart_session"),
                    "effective_total": result.get("effective_total"),
                    "effective_total_for_upi_plugin": result.get("effective_total_for_upi_plugin"),
                    "total_quantity": result.get("total_quantity"),
                    "items": items,
                    "splits": result.get("splits", []),
                    "address": addr,
                    "user_meta": um,
                    "is_first_order": bool(um.get("is_first_order")),
                    "price_break_up": result.get("price_break_up", []),
                }
            return {"ok": False, "error": data.get("error_type", "review_failed"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_cart_remove(acc, item_identifier, cart_session):
    """Remove item from real Meesho cart via /api/1.0/cart/remove
    Tries both formats: prompt's {product_id} with context cart/default, and legacy identifier."""
    # Normalize - item_identifier may be pid (int) or identifier string
    pid = None
    ident = None
    if isinstance(item_identifier, dict) and "product_id" in item_identifier:
        pid = item_identifier.get("product_id")
        ident = item_identifier.get("identifier")
    elif isinstance(item_identifier, int) or (isinstance(item_identifier, str) and item_identifier.isdigit()):
        try: pid = int(item_identifier)
        except: ident = str(item_identifier)
    else:
        ident = str(item_identifier) if item_identifier else None
        try:
            if ident and ident.isdigit(): pid = int(ident)
        except: pass

    bodies = []
    if pid:
        bodies.append({"context": "cart", "identifier": "default", "cart_session": cart_session or "", "items": [{"product_id": int(pid)}], "user_id": _acc_uid(acc)})
        bodies.append({"context": "pdp", "identifier": "buy_now", "cart_session": cart_session or "", "items": [{"product_id": int(pid)}], "user_id": _acc_uid(acc)})
    if ident:
        bodies.append({"context": "atc_cart_v2", "identifier": "buy_now", "cart_session": cart_session or "", "items": [ident], "user_id": _acc_uid(acc)})
        bodies.append({"context": "cart", "identifier": "default", "cart_session": cart_session or "", "items": [ident], "user_id": _acc_uid(acc)})
    if not bodies:
        bodies.append({"context": "cart", "identifier": "default", "cart_session": cart_session or "", "items": [str(item_identifier)], "user_id": _acc_uid(acc)})

    last = {"ok": False, "error": "no body"}
    for body in bodies:
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(f"{MEESHO_API}/1.0/cart/remove", headers=logged_in_headers(acc), json=body)
                data = resp.json() or {}
                if data.get("success"):
                    return {"ok": True, "cart_session": data.get("cart_session", cart_session), "raw": data}
                last = {"ok": False, "error": data.get("error_type") or data.get("message") or str(data)[:200], "raw": data}
                # if error is not about context/identifier, don't retry other bodys? try next anyway
        except Exception as e:
            last = {"ok": False, "error": str(e)}
    return last


def real_cart_clear(acc, cart_session):
    """Clear all items from real Meesho cart"""
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


def real_cart_sync(acc, local_items, cart_session=None):
    """Reconcile local cart items into real Meesho cart. Returns latest cart_session."""
    cs = cart_session
    for c in local_items:
        pid = c.get("product_id")
        if not pid:
            continue
        r = real_cart_add(acc, pid, c.get("supplier_id"), c.get("variation_id"),
                          c.get("variation_name") or "Free Size", c.get("qty", 1), cs)
        if r.get("ok"):
            cs = r.get("cart_session", cs)
    return {"ok": True, "cart_session": cs}


def real_bind_address(acc, cart_session, address_id, dest_pin=None):
    """Bind address to cart via /api/1.0/cart/location.
    CRITICAL: context='review' + identifier='buy_now' matches the real app."""
    body = {
        "context": "review", "identifier": "buy_now",
        "cart_session": cart_session,
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
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/cart/location",
                               headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            return {"ok": data.get("success", False), "cart_session": data.get("cart_session")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_paymentinfo(acc, cart_session, payment_modes=None):
    """Get payment info via /api/1.0/cart/paymentinfo.
    Tries both atc_payment_summary/default (real Meesho cart) and payment_summary/buy_now (buy_now flow)."""
    tried = []
    for ctx, ident in [("atc_payment_summary","default"), ("payment_summary","buy_now"), ("atc_payment_summary","buy_now")]:
        body = {
            "context": ctx, "identifier": ident,
            "cart_session": cart_session,
            "dest_pin": None,
            "address_id": None,
            "customerAmount": None,
            "payment_modes": payment_modes if payment_modes is not None else ["juspay"],
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
        # normalize payment_modes: [] for COD, ["juspay"] for prepaid (captured)
        if payment_modes == []:
            body["payment_modes"] = []
        elif payment_modes == ["juspay"] or payment_modes == ["upi_qr"]:
            body["payment_modes"] = ["juspay"]
        tried.append((ctx,ident))
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(f"{MEESHO_API}/1.0/cart/paymentinfo",
                                   headers=logged_in_headers(acc), json=body)
                data = resp.json() or {}
                if data.get("success"):
                    result = data.get("result", {})
                    return {
                        "ok": True,
                        "effective_total": result.get("effective_total"),
                        "effective_total_for_upi_plugin": result.get("effective_total_for_upi_plugin"),
                        "effective_total_with_ppd": result.get("effective_total_with_ppd"),
                        "effective_total_without_ppd": result.get("effective_total_without_ppd"),
                        "payment_details": result.get("payment_details", {}),
                        "cart_session": data.get("cart_session"),
                        "price_break_up": result.get("price_break_up", []),
                        "prepaid_discount_offered": (result.get("payment_details") or {}).get("prepaid_discount_offered", 0),
                    }
                # not success, try next context
                last_err = data.get("error_type") or data.get("message") or str(data)[:200]
                # if last context, return error else continue
                if (ctx,ident) == [("atc_payment_summary","default"), ("payment_summary","buy_now"), ("atc_payment_summary","buy_now")][-1]:
                    return {"ok": False, "error": last_err, "raw": data}
                continue
        except Exception as e:
            last_exc = str(e)
            if (ctx,ident) == [("atc_payment_summary","default"), ("payment_summary","buy_now"), ("atc_payment_summary","buy_now")][-1]:
                return {"ok": False, "error": last_exc}
            continue
    return {"ok": False, "error": "paymentinfo_failed all contexts", "tried": tried}


def real_address_create(acc, name, mobile, pin, city, state, line1, line2="", landmark="", addr_type="Home"):
    """Create address on Meesho via /api/2.0/addresses.
    CRITICAL: cart_identifier='buy_now' matches the real app."""
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
            resp = client.post(f"{MEESHO_API}/2.0/addresses?context=cart&cart_identifier=buy_now",
                               headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            addr = data.get("address", {})
            if addr.get("id"):
                return {"ok": True, "meesho_address_id": addr["id"], "address": addr}
            return {"ok": False, "error": data.get("error_type", "address_create_failed"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_cart_add_many(acc, items, cart_session=""):
    """Add multiple items to real Meesho cart in ONE call via /api/1.0/cart/add.
    Captured uses context='pdp' for buy_now (folder 56). Try pdp then pdl."""
    h = logged_in_headers(acc)
    its = []
    for li in items:
        its.append({
            "identifier": "buy_now",
            "product_id": int(li.get("product_id") or 0),
            "supplier_id": _pos_int(li.get("supplier_id")),
            "variation_id": _pos_int(li.get("variation_id")),
            "variation": li.get("variation") or li.get("variation_name") or "Free Size",
            "quantity": int(li.get("quantity") or li.get("qty") or 1),
            "selected_price_type_id": li.get("price_type_id") or "premium_return_price",
            "client_metadata": None,
        })
    for context in ("pdp", "pdl"):
        body = {
            "context": context, "identifier": "buy_now",
            "cart_session": cart_session or None,
            "replaceable": False, "items": [dict(x) for x in its],
            "address_id": None, "user_id": _acc_uid(acc),
        }
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(f"{MEESHO_API}/1.0/cart/add", headers=h, json=body)
                data = resp.json() or {}
                print(f"[CART_ADD_MANY] context={context} resp={resp.status_code} data={str(data)[:400]}", flush=True)
                if data.get("success"):
                    new_cs = data.get("cart_session") or cart_session
                    result = data.get("result", {})
                    return {
                        "ok": True, "success": True,
                        "cart_session": new_cs,
                        "effective_total": result.get("effective_total"),
                        "total_quantity": result.get("total_quantity"),
                        "splits": result.get("splits", []),
                    }
                ecode = (data.get("error") or {}).get("code") if isinstance(data.get("error"), dict) else None
                if ecode == "CART_OOS" and resp.status_code == 200:
                    for li in body["items"]:
                        li["selected_price_type_id"] = "basic_return_price"
                    resp2 = client.post(f"{MEESHO_API}/1.0/cart/add", headers=h, json=body)
                    data2 = resp2.json() or {}
                    if data2.get("success"):
                        new_cs = data2.get("cart_session") or cart_session
                        result = data2.get("result", {})
                        return {"ok": True, "success": True, "cart_session": new_cs,
                                "effective_total": result.get("effective_total"),
                                "total_quantity": result.get("total_quantity"),
                                "splits": result.get("splits", [])}
                err_s = str(data.get("error_type") or data.get("message") or data)[:400]
                if "context" in err_s.lower():
                    continue
                if context == "pdp":
                    continue
                return {"ok": False, "error": data.get("error_type", "add_failed"), "raw": data}
        except Exception as e:
            print(f"[CART_ADD_MANY] EXCEPTION context={context}: {e}", flush=True)
            if context == "pdp":
                continue
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "cart add failed (both pdp/pdl)", "raw": {}}


def real_fetch_addresses(acc):
    """Fetch real address list from Meesho GET /api/3.0/addresses - tries buy_now and default, merges"""
    def _parse_addrs(data):
        out=[]
        for a in (data.get("addresses") or []):
            if not isinstance(a, dict) or not a.get("id"):
                continue
            coords = a.get("coordinates") or {}
            out.append({
                "id": a.get("id"), "name": a.get("name"),
                "mobile": str(a.get("mobile") or ""),
                "pin": a.get("pin"), "city": a.get("city"), "state": a.get("state"),
                "address_line_1": a.get("address_line_1"),
                "address_line_2": a.get("address_line_2"),
                "landmark": a.get("landmark"),
                "address_type": a.get("address_type"),
                "latitude": coords.get("latitude") if isinstance(coords, dict) else a.get("latitude"),
                "longitude": coords.get("longitude") if isinstance(coords, dict) else a.get("longitude"),
                "pin_serviceable": a.get("pin_serviceable", True),
            })
        return out
    try:
        uid = _acc_uid(acc)
        merged={}
        with httpx.Client(timeout=15.0) as client:
            for ident in ("buy_now", "default"):
                try:
                    resp = client.get(
                        f"{MEESHO_API}/3.0/addresses?offset=0&limit=50&check_pin=true"
                        f"&context=cart&cart_identifier={ident}&user_id={uid}",
                        headers=logged_in_headers(acc))
                    data = resp.json() or {}
                    for a in _parse_addrs(data):
                        merged[a["id"]] = a
                except: continue
            if merged:
                return list(merged.values())
            # final fallback: raw buy_now once more if merged empty due to exception
            return []
    except Exception as e:
        print(f"[FETCH_ADDR] EXCEPTION: {e}", flush=True)
        return []


def fresh_checkout_state(acc, cart_session=None, need_paymentinfo=True):
    """Run review -> bind address -> (paymentinfo) with fresh sessions.
    Returns dict(cs, addr, amt, order_total, upi_amount) or None.
    Uses correct payment_modes per captured API: [] for COD, ["juspay"] for UPI."""
    review = real_cart_review(acc, cart_session)
    if not review.get("ok") or not review.get("cart_session"):
        print(f"[FRESH_CHECKOUT] review_failed cs={cart_session} review={review}", flush=True)
        # Retry with empty session (stale session expired)
        if cart_session:
            print(f"[FRESH_CHECKOUT] retrying review with empty session", flush=True)
            review = real_cart_review(acc, "")
            if not review.get("ok") or not review.get("cart_session"):
                print(f"[FRESH_CHECKOUT] retry_failed: {review}", flush=True)
                return None
        else:
            return None
    cs = review["cart_session"]
    # Also handle case where review succeeds but items empty (cart not synced)
    items = review.get("items") or []
    if not items:
        print(f"[FRESH_CHECKOUT] review_ok_but_empty_items: {review}", flush=True)
        return None
    addr = review.get("address") or {}
    if not addr.get("id") and addr.get("address_id"):
        addr["id"] = addr["address_id"]
    if not (addr and addr.get("id")):
        acc_addrs = real_fetch_addresses(acc)
        if acc_addrs:
            addr = acc_addrs[0]
            print(f"[FRESH_CHECKOUT] using fetched address id={addr.get('id')}", flush=True)
        else:
            print(f"[FRESH_CHECKOUT] no_address and no fetched addrs", flush=True)
            return None
    # Bind address - log but don't fail hard if already bound (some flows return ok even if same)
    bind_result = real_bind_address(acc, cs, addr["id"], addr.get("pin"))
    if not bind_result.get("ok"):
        print(f"[FRESH_CHECKOUT] bind_failed: {bind_result} - retrying review to see if already bound", flush=True)
        # Re-review to see if bind was actually not needed
        re = real_cart_review(acc, cs)
        if re.get("ok") and re.get("address") and re["address"].get("id"):
            cs = re.get("cart_session", cs)
            print(f"[FRESH_CHECKOUT] re-review after bind fail got addr {re['address'].get('id')}", flush=True)
        else:
            return None
    else:
        cs = bind_result.get("cart_session") or cs
    order_total = upi_amount = None
    # COD vs UPI amounts: review already has both (69 vs 41). Use them directly.
    # For UPI we also want with_ppd / for_upi_plugin.
    review_cod = review.get("effective_total")
    review_upi = review.get("effective_total_for_upi_plugin") or review.get("effective_total_with_ppd")
    if need_paymentinfo:
        # Use correct modes per capture: ["juspay"] for UPI
        pi = real_paymentinfo(acc, cs, ["juspay"])
        if pi.get("ok"):
            order_total = pi.get("effective_total")
            upi_amount = pi.get("effective_total_for_upi_plugin") or pi.get("effective_total_with_ppd") or order_total
            # UPI amount should be the with_ppd one (41), COD is without (69)
            new_cs = pi.get("cart_session")
            if new_cs:
                cs = new_cs
            print(f"[FRESH_CHECKOUT] paymentinfo UPI ok total={order_total} upi={upi_amount}", flush=True)
        if order_total is None or order_total <= 0:
            order_total = review_upi or review_cod
            upi_amount = review_upi or order_total
        if upi_amount is None:
            upi_amount = order_total
    else:
        # COD: use effective_total (69) directly, no paymentinfo needed
        order_total = review_cod
        upi_amount = review_upi or review_cod
        print(f"[FRESH_CHECKOUT] COD mode using review_cod={review_cod} upi={upi_amount}", flush=True)
    if order_total is None or order_total <= 0:
        order_total = review_cod
    if order_total is None or order_total <= 0 and items:
        order_total = sum(float(it.get("price", 0)) * int(it.get("quantity", 1)) for it in items) or 1
    if order_total is None or order_total <= 0:
        print(f"[FRESH_CHECKOUT] zero_amt: {order_total} review={review}", flush=True)
        return None
    # Update is_first_order flag from live user_meta
    try:
        vm = review.get("user_meta") or {}
        if "is_first_order" in vm:
            # don't write DB here (caller does), just include in return
            pass
    except Exception:
        pass
    return {"cs": cs, "addr": addr, "amt": int(round(order_total)),
            "order_total": order_total, "upi_amount": upi_amount or order_total,
            "items": items, "total_quantity": review.get("total_quantity"),
            "effective_total": review_cod, "effective_upi": review_upi}


def real_preorder(acc, cart_session, address_id, payment_method="COD",
                  customer_amount=None, payment_aggregator=None):
    """Place real order via /api/4.0/preorders. For UPI, also calls /api/juspay/txns to get actual QR."""
    is_upi = payment_method.upper() in ("UPI", "PREPAID")
    body = {
        "payment_method_type": payment_method.upper() if payment_method.upper() != "PREPAID" else "UPI",
        "identifier": "buy_now",
        "payment_aggregator": payment_aggregator or ("JUSPAY" if is_upi else None),
        "is_selling_to_customer": False,
        "cart_session": cart_session,
        "vpa": None,
        "address_id": int(address_id),
        "direct_wallet_token": None,
        "customer_amount": customer_amount,
        "upi_package_name": "com.google.android.apps.nbu.paisa.user" if is_upi else None,
        "payment_flow_type": "qr" if is_upi else None,
        "sender_id": -1,
        "accurate_location": json.dumps({"lat": "22.7196", "long": "75.8577"}),
        "card_token": None,
        "payment_provider": "JUSPAY" if is_upi else None,
        "processor_id": "in.juspay.hyperapi" if is_upi else None,
        "payment_method": "UPI" if is_upi else "COD",
        "enable_price_unbundling": True,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(f"{MEESHO_API}/4.0/preorders",
                               headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            order_num = data.get("order_num")
            juspay_params = data.get("juspay_transaction_params", {})
            qr_params = data.get("qr_transaction_params", {})
            if order_num:
                result = {
                    "ok": True,
                    "order_num": order_num,
                    "juspay_order_id": data.get("juspay_order_id") or juspay_params.get("payload", {}).get("order_id"),
                    "qr_base64": qr_params.get("payload", {}).get("qr_base64_string"),
                    "upi_intent_url": qr_params.get("payload", {}).get("upi_intent_url"),
                    "payment_url": data.get("payment_url"),
                    "client_auth_token": juspay_params.get("payload", {}).get("client_auth_token"),
                    "raw": data,
                }
                # For UPI: call JusPay txns API to get actual QR with MEESHOONLINEPG@ybl VPA
                if is_upi and result["juspay_order_id"]:
                    try:
                        juspay_txns = real_juspay_txns(client, acc, result["juspay_order_id"])
                        if juspay_txns.get("ok"):
                            result["upi_intent_url"] = juspay_txns.get("upi_link") or result["upi_intent_url"]
                            result["merchant_vpa"] = juspay_txns.get("merchant_vpa", "")
                            result["merchant_name"] = juspay_txns.get("merchant_name", "")
                            result["tr"] = juspay_txns.get("tr", "")
                            print(f"[PREORDER] JusPay txns OK: vpa={juspay_txns.get('merchant_vpa')} tr={juspay_txns.get('tr')}", flush=True)
                    except Exception as e:
                        print(f"[PREORDER] JusPay txns failed: {e}", flush=True)
                return result
            return {"ok": False, "error": data.get("error_type", "order_failed"),
                    "message": data.get("message", ""), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_juspay_txns(client, acc, juspay_order_id):
    """Call /api/juspay/txns to generate UPI QR for a preorder.
    Returns the actual UPI link with MEESHOONLINEPG@ybl VPA (Meesho's real payment UPI)."""
    body = {
        "order_id": juspay_order_id,
        "merchant_id": "meesho",
        "redirect_after_payment": True,
        "format": "json",
        "txnPayload": {
            "payment_method_type": "UPI",
            "payment_method": "UPI",
            "txn_type": "UPI_QR",
            "offers": "",
            "sdk_params": True,
        }
    }
    try:
        resp = client.post(f"{MEESHO_API}/juspay/txns",
                           headers=logged_in_headers(acc), json=body)
        data = resp.json() or {}
        sdk = data.get("payment", {}).get("sdk_params", {}) or data.get("sdk_params", {})
        upi_link = sdk.get("pgIntentUrl", "")
        merchant_vpa = sdk.get("merchant_vpa", "")
        merchant_name = sdk.get("merchant_name", "")
        amount = sdk.get("amount", "")
        tr = sdk.get("tr", "")
        if upi_link:
            return {"ok": True, "upi_link": upi_link, "merchant_vpa": merchant_vpa,
                    "merchant_name": merchant_name, "amount": amount, "tr": tr}
        return {"ok": False, "error": "no_upi_link", "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_payment_status(acc, juspay_order_id):
    """Check payment status via /api/v3/payments/{id}/status"""
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{MEESHO_API}/v3/payments/{juspay_order_id}/status",
                              params={"sync": "true"},
                              headers=logged_in_headers(acc))
            data = resp.json() or {}
            return {"ok": True, "status": data.get("status", "UNKNOWN"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_preorder_status(acc, order_num, cart_session):
    """Check preorder status via /api/1.0/preorders/payments/status"""
    body = {
        "pre_order_id": -1,
        "is_selling_to_customer": False,
        "order_num": order_num,
        "retry_in_sec": 0,
        "cart_session": cart_session,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/preorders/payments/status",
                               headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            return {"ok": True, "status": data.get("status", "UNKNOWN"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def real_payment_options(acc, cart_session, order_total=0):
    """Get payment options via /api/v1/list/payment-options"""
    body = {
        "payment_identifier": "checkout",
        "checkout_identifier": "buy_now",
        "cart_session": cart_session or "",
        "sms_id": None,
        "order_total": order_total,
        "available_upi_apps": [],
        "skip_bnpl_eligibility": True,
        "user_id": _acc_uid(acc),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            h = logged_in_headers(acc)
            h["line-of-business"] = "MEESHO_MARKETPLACE"
            resp = client.post(f"{MEESHO_API}/v1/list/payment-options",
                               headers=h, json=body)
            data = resp.json() or {}
            return {"ok": True, "options": data.get("payment_options", []),
                    "auth_token": data.get("client_auth_token"),
                    "merchant_id": data.get("merchant_id"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================ EXTRA SYNC APIS - har cheez Meesho account se live
# Ye saare tumhare diye hue Main Flow ke hisaab se hain - koi dummy nahi

def real_cart_minview(acc):
    """GET /api/1.0/cart/minview - badge count"""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{MEESHO_API}/1.0/cart/minview", headers=logged_in_headers(acc))
            data = resp.json() or {}
            return {"ok": True, "total_quantity": data.get("total_quantity", 0), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_home_for_you(acc, limit=20):
    """GET /api/4.0/for-you?l=20&s=created_desc&c=1"""
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(f"{MEESHO_API}/4.0/for-you", params={"l": limit, "s": "created_desc", "c": 1}, headers=logged_in_headers(acc))
            data = resp.json() or {}
            return {"ok": resp.status_code==200, "data": data, "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_home_fetch(acc):
    """POST /api/1.0/home-page/fetch"""
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/home-page/fetch", headers=logged_in_headers(acc), json={})
            return {"ok": resp.status_code==200, "data": resp.json() if resp.status_code==200 else {}, "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_user_delivery_location(acc, pincode="452010"):
    """POST /api/1.0/user/delivery-location"""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/user/delivery-location", headers=logged_in_headers(acc), json={"pincode": pincode, "context": "address_add_edit", "user_id": _acc_uid(acc)})
            data = resp.json() or {}
            loc = data.get("user_delivery_location") or {}
            return {"ok": True, "city": loc.get("city"), "lat": loc.get("lat"), "long": loc.get("long"), "pincode": loc.get("pincode"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_wallet_list(acc):
    """POST /api/v1/wallet/list"""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{MEESHO_API}/v1/wallet/list", headers=logged_in_headers(acc), json={"user_id": _acc_uid(acc)})
            data = resp.json() or {}
            return {"ok": True, "items": data.get("items", []), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_bnpl_eligibility(acc, amount=0):
    """POST /api/v1/bnpl/eligibility"""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{MEESHO_API}/v1/bnpl/eligibility", headers=logged_in_headers(acc), json={"amount": amount, "ip_address": "null", "carrier_name": "Unknown", "device_manufacturer": "Google", "device_model": "Pixel 4", "user_id": _acc_uid(acc)})
            return {"ok": True, "data": resp.json() if resp.status_code==200 else {}, "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_offers_list(acc, amount="41"):
    """POST /api/v1/offers/list - bank offers"""
    body = {
        "customer": {"email": None, "id": str(_acc_uid(acc)), "phone": f"+91{acc.get('phone','')}", "udf1": "enable"},
        "merchant_key_id": "9970",
        "order": {"amount": str(amount), "currency": "INR", "merchant_id": "meesho", "payment_channel": "ANDROID", "udf1": "enable", "udf3": "applicable", "udf4": "not_applicable", "udf5": "not_applicable", "udf6": "applicable", "udf7": "variant_1", "udf8": "not_applicable", "udf9": "not_applicable", "udf10": "not_applicable"},
        "payment_method_info": [{"payment_channel": "ANDROID", "payment_method": "MOBIKWIK", "payment_method_reference": "MOBIKWIK", "payment_method_type": "WALLET", "payment_provider": "JUSPAY", "payment_aggregator": "JUSPAY"}],
        "user_id": _acc_uid(acc)
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(f"{MEESHO_API}/v1/offers/list", headers=logged_in_headers(acc), json=body)
            return {"ok": True, "data": resp.json() if resp.status_code==200 else {}, "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_payments_user_details(acc, cart_session):
    """POST /api/1.0/payments/user-details"""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/payments/user-details", headers=logged_in_headers(acc), json={"actions": ["updateOrder"], "identifier": "default", "is_headless_enabled": True, "cart_session": cart_session, "user_id": _acc_uid(acc)})
            data = resp.json() or {}
            return {"ok": True, "order_total": data.get("order_total"), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def real_user_orders(acc, limit=10, cursor=None):
    """POST /api/3.0/user/orders - real Meesho orders sync (includes Cancelled)"""
    # Try multiple filter combos - real app shows Cancelled too, so [0] alone is too narrow
    bodies = [
        {"limit": limit, "cursor": cursor, "query": None, "filters": {"sub_order_status": [], "sub_order_created": None}, "user_id": _acc_uid(acc)},
        {"limit": limit, "cursor": cursor, "query": None, "filters": {"sub_order_status": [0,1,2,3,4,5,6,7,8,9], "sub_order_created": None}, "user_id": _acc_uid(acc)},
        {"limit": limit, "cursor": cursor, "query": None, "filters": {"sub_order_status": [0], "sub_order_created": None}, "user_id": _acc_uid(acc)},
        {"limit": limit, "cursor": cursor, "user_id": _acc_uid(acc)},
    ]
    last = {"ok": False, "error": "no data"}
    for body in bodies:
        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(f"{MEESHO_API}/3.0/user/orders", headers=logged_in_headers(acc), json=body)
                data = resp.json() or {}
                lst = data.get("sub_order_list") or data.get("orders") or data.get("data") or []
                # If API returns success but empty, try next filter
                if resp.status_code == 200 and lst:
                    return {"ok": True, "orders": lst, "pagination": data.get("pagination"), "raw": data}
                # Also accept empty but ok response on first try (for fallback)
                if resp.status_code == 200:
                    last = {"ok": True, "orders": lst, "pagination": data.get("pagination"), "raw": data}
                else:
                    last = {"ok": False, "error": data.get("error_type") or f"HTTP {resp.status_code}", "raw": data}
        except Exception as e:
            last = {"ok": False, "error": str(e)}
            continue
    return last

def real_product_recommendations(acc, catalog_id, product_id, sub_sub_category_id=3354, limit=20):
    """POST /api/1.0/catalogs/recommendations"""
    body = {"catalog_id": catalog_id, "offset": 0, "recommended_catalog_ids_in_widget": None, "product_id": product_id, "origin": "main", "sub_sub_category_id": sub_sub_category_id, "limit": limit, "user_id": _acc_uid(acc)}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{MEESHO_API}/1.0/catalogs/recommendations", headers=logged_in_headers(acc), json=body)
            data = resp.json() or {}
            return {"ok": True, "catalogs": data.get("catalogs", []), "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

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


# Expose real Meesho API functions
__all__ = [
    "get_meesho_offer", "search_meesho", "get_meesho_product",
    "send_otp", "verify_otp", "check_number",
    "logged_in_headers", "real_cart_add", "real_cart_add_many", "real_cart_review",
    "real_cart_remove", "real_cart_clear", "real_cart_sync",
    "real_bind_address", "real_paymentinfo", "real_address_create",
    "real_fetch_addresses",     "real_preorder", "real_payment_status",
    "real_preorder_status", "real_payment_options", "fresh_checkout_state",
    "real_juspay_txns",
    "real_cart_minview", "real_home_for_you", "real_home_fetch", "real_user_delivery_location",
    "real_wallet_list", "real_bnpl_eligibility", "real_offers_list", "real_payments_user_details",
    "real_user_orders", "real_product_recommendations",
]
