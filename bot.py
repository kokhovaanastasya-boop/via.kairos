#!/usr/bin/env python3
"""
Ultra-Fast Pure Python Telegram Bot for @via.kairos (Анастасия)
С проверкой обязательной подписки на канал: https://t.me/+0hwBdSVNsDcyZGYy
"""

import os
import sys
import time
import json
import logging
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "8850880508:AAHGeajr-6aDhqGWmfQaE5jdL4uWNg2e9io")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
MANUFLIRT_URL = "https://manuflirt.netlify.app/"
CHANNEL_INVITE_URL = "https://t.me/+0hwBdSVNsDcyZGYy"
AUDIT_INSTAGRAM_URL = "https://www.instagram.com/via.kairos?igsi=MW8xbzVhZGFpMWRucA=="
PRESENTATION_PREVIEW_URL = "https://docs.google.com/presentation/d/1kEvbWzUoJ1VO8WXm3zR_dQ5dkm4Pe0Go/preview"
PDF_FILE_PATH = "Manifest_Naglosti_via_kairos.pdf"

CHANNEL_ID_FILE = "channel_id.txt"
channel_id = None

if os.path.exists(CHANNEL_ID_FILE):
    try:
        with open(CHANNEL_ID_FILE, "r") as f:
            channel_id = int(f.read().strip())
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# === КЛАВИАТУРА ПРОВЕРКИ ПОДПИСКИ ===
def get_subscription_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🖤 1. Подписаться на канал", "url": CHANNEL_INVITE_URL}],
            [{"text": "✅ 2. Я подписалась! Забрать подарки", "callback_data": "check_sub"}]
        ]
    }

# === ГЛАВНОЕ МЕНЮ (ПОСЛЕ ПОДПИСКИ) ===
def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💸 Манифест наглости", "callback_data": "gift_money"}],
            [{"text": "👑 Финансовый флирт", "web_app": {"url": MANUFLIRT_URL}}],
            [{"text": "🔥 Я жадная: хочу забрать ВСЁ и сразу!", "callback_data": "gift_both"}]
        ]
    }

def get_after_gift_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📖 Читать Манифест онлайн (Google Docs)", "url": PRESENTATION_PREVIEW_URL}],
            [{"text": "👑 Книга «Финансовый флирт» (Mini App)", "web_app": {"url": MANUFLIRT_URL}}],
            [{"text": "🖤 Мой Telegram-канал", "url": CHANNEL_INVITE_URL}],
            [{"text": "🎯 Записаться на Разбор в Instagram", "url": AUDIT_INSTAGRAM_URL}]
        ]
    }

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
        return r.json()
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return None

def send_document(chat_id, file_path, caption=None, reply_markup=None):
    if not os.path.exists(file_path):
        return send_message(chat_id, caption or "Файл гайда готов!", reply_markup)
    
    data = {
        "chat_id": chat_id,
        "parse_mode": "HTML"
    }
    if caption:
        data["caption"] = caption
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    
    try:
        with open(file_path, "rb") as f:
            files = {"document": ("Манифест_Наглости_via_kairos.pdf", f, "application/pdf")}
            r = requests.post(f"{API_URL}/sendDocument", data=data, files=files, timeout=30)
            return r.json()
    except Exception as e:
        logging.error(f"Error sending document: {e}")
        return send_message(chat_id, caption or "Файл гайда готов!", reply_markup)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        requests.post(f"{API_URL}/answerCallbackQuery", json=payload, timeout=5)
    except Exception:
        pass

def is_user_subscribed(user_id):
    global channel_id
    if not channel_id:
        return True
    try:
        r = requests.get(f"{API_URL}/getChatMember", params={"chat_id": channel_id, "user_id": user_id}, timeout=5)
        res = r.json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["member", "administrator", "creator", "restricted"]
    except Exception as e:
        logging.error(f"Check sub error: {e}")
    return True

def handle_update(update):
    global channel_id
    
    if "my_chat_member" in update:
        chat = update["my_chat_member"]["chat"]
        if chat.get("type") in ["channel", "supergroup"]:
            channel_id = chat["id"]
            with open(CHANNEL_ID_FILE, "w") as f:
                f.write(str(channel_id))
            logging.info(f"🎉 Канал успешно привязан к боту! ID: {channel_id}")
            return
            
    if "channel_post" in update:
        chat = update["channel_post"]["chat"]
        channel_id = chat["id"]
        with open(CHANNEL_ID_FILE, "w") as f:
            f.write(str(channel_id))
        logging.info(f"🎉 Канал привязан из поста! ID: {channel_id}")
        return

    # 1. Handle Messages
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip()
        
        logging.info(f"Received message from {chat_id}: {text}")
        
        if text.startswith("/start") or text.startswith("/help") or "старт" in text.lower():
            if channel_id and not is_user_subscribed(user_id):
                sub_text = (
                    "Привет! Рада видеть тебя здесь 🖤\n\n"
                    "Я — <b>Анастасия (@via.kairos)</b>.\n"
                    "Забираю страхи, выбиваю синдром «хорошей девочки» и возвращаю природную дерзость.\n\n"
                    "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
                    "🔒 <i>Доступ к подаркам открывается только для подписчиц моего канала:</i>\n\n"
                    "1. Подпишись на канал по кнопке ниже 👇\n"
                    "2. Нажми кнопку <b>«✅ Я подписалась!»</b>"
                )
                send_message(chat_id, sub_text, get_subscription_keyboard())
                return

            welcome_text = (
                "Привет! Рада видеть тебя здесь 🖤\n\n"
                "Я — <b>Анастасия (@via.kairos)</b>.\n"
                "Забираю страхи, выбиваю синдром «хорошей девочки» и возвращаю природную дерзость.\n\n"
                "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
                "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
            )
            send_message(chat_id, welcome_text, get_main_keyboard())
        
        elif any(w in text.lower() for w in ["наглост", "гайд", "манифест", "деньг"]):
            caption = (
                "⚡️ <b>Твой «Манифест Наглости» (12 слайдов) готов!</b>\n\n"
                "Внутри гайда:\n"
                "❌ Диагностика: как роль «хорошей девочки» режет чек\n"
                "🛑 5 установок, которые сливают доход\n"
                "📝 Экспресс-тест на уровень наглости\n"
                "🚀 Формула: Личность → Бренд → High-Ticket чек (80k–150k ₽)\n"
                "💬 Готовые скрипты для продаж в переписке\n\n"
                "Изучай и прекращай быть скромной 🖤"
            )
            send_document(chat_id, PDF_FILE_PATH, caption=caption, reply_markup=get_after_gift_keyboard())
        
        elif any(w in text.lower() for w in ["книг", "флирт", "подар"]):
            send_message(
                chat_id,
                "👑 <b>Интерактивная книга «Финансовый флирт»</b>\n\nОткрывай прямо внутри Telegram:",
                get_after_gift_keyboard()
            )
        
        elif any(w in text.lower() for w in ["разбор", "интенсив"]):
            send_message(
                chat_id,
                f"🎯 <b>Запись на личный разбор / интенсив:</b>\n\nНапиши мне в Instagram Direct: {AUDIT_INSTAGRAM_URL} с кодовым словом <b>РАЗБОР</b>!"
            )
        else:
            send_message(chat_id, "⚡️ <b>Выбирай подарок:</b>", get_main_keyboard())

    # 2. Handle Callback Queries (Button Clicks)
    elif "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        user_id = cb["from"]["id"]
        data = cb.get("data", "")
        
        logging.info(f"Received callback from {chat_id}: {data}")
        
        if data == "check_sub":
            if channel_id and not is_user_subscribed(user_id):
                answer_callback_query(cb_id, text="❌ Ты ещё не подписалась на канал! Подпишись по кнопке выше 😉", show_alert=True)
                return
            
            answer_callback_query(cb_id, text="✅ Подписка подтверждена! Добро пожаловать 🖤", show_alert=False)
            welcome_text = (
                "🔥 <b>Подписка подтверждена! Добро пожаловать в мой мир наглости 🖤</b>\n\n"
                "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
            )
            send_message(chat_id, welcome_text, get_main_keyboard())
            return
            
        answer_callback_query(cb_id)
        
        if data == "gift_money":
            caption = (
                "⚡️ <b>Твой авторский «Манифест Наглости» (12 слайдов) готов!</b>\n\n"
                "Внутри гайда:\n"
                "❌ Диагностика роли «хорошей девочки»\n"
                "🛑 5 установок, сливающих доход\n"
                "📝 Экспресс-тест на уровень наглости\n"
                "🚀 Формула: Личность → Бренд → High-Ticket чек (80k–150k ₽)\n"
                "💬 Готовые скрипты для продаж в переписке\n\n"
                "Изучай и прекращай быть скромной 🖤"
            )
            send_document(chat_id, PDF_FILE_PATH, caption=caption, reply_markup=get_after_gift_keyboard())
            
        elif data == "gift_both":
            caption = (
                "🔥 <b>Обожаю жадных до жизни и денег девушек! Именно такие и забирают всё лучшее</b>\n\n"
                "Твой полный комплект Наглости готов:\n\n"
                "1️⃣ <b>ГАЙД:</b> 12-страничный «Манифест Наглости» (прикреплен файлом ниже).\n"
                "2️⃣ <b>КНИГА:</b> Интерактивная книга «Финансовый флирт: 100 фраз и правила ухода» (кнопка запускает Mini App прямо в Telegram!).\n\n"
                "Скромность не украшает. Украшают чеки и подарки 😉"
            )
            send_document(chat_id, PDF_FILE_PATH, caption=caption, reply_markup=get_after_gift_keyboard())

def main():
    logging.info("🚀 Starting Subscription-Verification Polling Bot @via_kairos_bot...")
    
    try:
        requests.post(f"{API_URL}/deleteWebhook", json={"drop_pending_updates": False}, timeout=10)
    except Exception:
        pass
    
    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API_URL}/getUpdates", 
                params={"offset": offset, "timeout": 10}, 
                timeout=15
            )
            if r.status_code == 200:
                res = r.json()
                if res.get("ok"):
                    for update in res.get("result", []):
                        offset = update["update_id"] + 1
                        handle_update(update)
            time.sleep(0.1)
        except Exception as e:
            logging.error(f"Polling loop notice: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
