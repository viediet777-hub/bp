import aiohttp
import json
import logging

logger = logging.getLogger(__name__)
BOT_TOKEN = ""


def set_token(token):
    global BOT_TOKEN
    BOT_TOKEN = token


def sbtn(text, callback_data, style="primary", icon_id=None):
    btn = {"text": text, "callback_data": callback_data, "style": style}
    if icon_id:
        btn["icon_custom_emoji_id"] = icon_id
    return btn


def sbtn_url(text, url, style="success", icon_id=None):
    btn = {"text": text, "url": url, "style": style}
    if icon_id:
        btn["icon_custom_emoji_id"] = icon_id
    return btn


ICON = {
    "home": "5258362837411045098",
    "cart": "5456140674028019486",
    "wallet": "5258204546391351475",
    "order": "5397782960512444700",
    "success": "5222079954421818267",
    "danger": "6334696528145286813",
    "back": "5222079954421818267",
    "download": "5244837092042750681",
    "user": "5424818078833715060",
    "admin": "5452165780579843515",
    "chart": "5258330865674494479",
    "users": "5258011929993026890",
    "broadcast": "5258115571848846212",
    "support": "5258073068852485953",
    "star": "5461117441612462242",
    "refresh": "5258477770735885832",
    "link": "5226513232549664618",
}


async def send_msg(chat_id, text, reply_markup=None, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                data = await r.json()
                if not data.get("ok"):
                    logger.error(f"send_msg failed: {data}")
                return data
    except Exception as e:
        logger.error(f"send_msg error: {e}")
        return {"ok": False, "description": str(e)}


async def edit_msg(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"edit_msg error: {e}")
        return {"ok": False}


async def answer_cb(query_id, text="", show_alert=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"callback_query_id": query_id, "text": text, "show_alert": show_alert}) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"answer_cb error: {e}")
        return {"ok": False}


async def send_photo(chat_id, photo, caption="", reply_markup=None, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                data = await r.json()
                if not data.get("ok"):
                    logger.error(f"send_photo failed: {data}")
                return data
    except Exception as e:
        logger.error(f"send_photo error: {e}")
        return {"ok": False, "description": str(e)}


async def send_doc(chat_id, file_content, filename, caption="", parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        data = aiohttp.FormData()
        data.add_field("chat_id", str(chat_id))
        data.add_field("caption", caption)
        data.add_field("parse_mode", parse_mode)
        data.add_field("document", file_content.encode("utf-8"), filename=filename, content_type="text/plain")
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data=data) as r:
                result = await r.json()
                if not result.get("ok"):
                    logger.error(f"send_doc failed: {result}")
                return result
    except Exception as e:
        logger.error(f"send_doc error: {e}")
        return {"ok": False, "description": str(e)}


async def delete_msg(chat_id, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"chat_id": chat_id, "message_id": message_id}) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"delete_msg error: {e}")
        return {"ok": False}


def get_chat_member(chat_id, user_id):
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    try:
        return requests.get(url, params={"chat_id": chat_id, "user_id": user_id}).json()
    except Exception as e:
        logger.error(f"get_chat_member error: {e}")
        return {"ok": False}
