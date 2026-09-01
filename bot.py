#!/usr/bin/env python3
"""
Telegram Bot for @via.kairos (Анастасия)
100% Обязательная подписка на канал перед выдачей подарков
Канал: https://t.me/+0hwBdSVNsDcyZGYy
"""

import json
import logging
import os
import sys
import time
import requests

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "8850880508:AAHGeajr-6aDhqGWmfQaE5jdL4uWNg2e9io")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

CHANNEL_INVITE_URL = "https://t.me/+0hwBdSVNsDcyZGYy"
MANUFLIRT_URL = "https://manuflirt.netlify.app/"
AUDIT_INSTAGRAM_URL = "https://www.instagram.com/via.kairos?igsi=MW8xbzVhZGFpMWRucA=="
PRESENTATION_PREVIEW_URL = "https://docs.google.com/presentation/d/1kEvbWzUoJ1VO8WXm3zR_dQ5dkm4Pe0Go/preview"
PDF_FILE_PATH = "Manifest_Naglosti_via_kairos.pdf"

CHANNEL_ID_FILE = "channel_id.txt"
channel_id = None

if os.path.exists(CHANNEL_ID_FILE):
    try:
        with open(CHANNEL_ID_FILE, "r") as f:
            c = f.read().strip()
            if c:
                channel_id = int(c)
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Кэш для защиты от повторных сообщений и дублей
processed_updates = set()
processed_callbacks = set()

# === 1. КНОПКИ ОБЯЗАТЕЛЬНОЙ ПОДПИСКИ (ПОКАЗЫВАЮТСЯ ВСЕГДА ПРИ /START) ===
def get_sub_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🖤 Подписаться на канал", "url": CHANNEL_INVITE_URL}],
            [{"text": "✅ Я подписалась! Забрать подарки", "callback_data": "check_sub"}]
        ]
    }

# === 2. МЕНЮ ВЫБОРА ПОДАРКОВ (ПОЯВЛЯЕТСЯ ТОЛЬКО ПОСЛЕ ПОДПИСКИ) ===
def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💸 Манифест наглости", "callback_data": "gift_money"}],
            [{"text": "📖 Финансовый флирт", "web_app": {"url": MANUFLIRT_URL}}],
            [{"text": "🔥 Я жадная: хочу забрать ВСЁ и сразу!", "callback_data": "gift_both"}]
        ]
    }

# === 3. КНОПКИ ПОД ФАЙЛОМ ГАЙДА (ТОЛЬКО 3 КНОПКИ) ===
def get_after_gift_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💸 Гайд «Манифест наглости»", "url": PRESENTATION_PREVIEW_URL}],
            [{"text": "📖 Книга «Финансовый флирт»", "web_app": {"url": MANUFLIRT_URL}}],
            [{"text": "🎯 Записаться на Разбор ", "url": AUDIT_INSTAGRAM_URL}]
        ]
    }

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
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
    for alt in [file_path, "Manifest_Naglosti_via_kairos.pdf", "/home/user/Manifest_Naglosti_via_kairos.pdf"]:
        if os.path.exists(alt):
            file_path = alt
            break
            
    if not os.path.exists(file_path):
        return send_message(chat_id, (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}", reply_markup)
    
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
        return send_message(chat_id, (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}", reply_markup)

def answer_callback(cb_id, text=None, show_alert=False):
    payload = {"callback_query_id": cb_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        requests.post(f"{API_URL}/answerCallbackQuery", json=payload, timeout=5)
    except Exception:
        pass

def is_subscribed_api(user_id):
    """Проверка подписки через Telegram Bot API"""
    global channel_id
    if not channel_id:
        return True
    try:
        r = requests.get(f"{API_URL}/getChatMember", params={"chat_id": channel_id, "user_id": user_id}, timeout=5)
        res = r.json()
        if res.get("ok"):
            status = res.get("result", {}).get("status", "")
            return status in ["member", "administrator", "creator", "restricted"]
    except Exception as e:
        logging.error(f"Error checking sub: {e}")
    return True

def handle_update(update):
    global channel_id
    
    update_id = update.get("update_id")
    if update_id in processed_updates:
        return
    processed_updates.add(update_id)
    if len(processed_updates) > 2000:
        processed_updates.clear()

    # Авто-привязка канала при добавлении бота админом
    if "my_chat_member" in update:
        chat = update["my_chat_member"]["chat"]
        if chat.get("type") in ["channel", "supergroup"]:
            channel_id = chat["id"]
            try:
                with open(CHANNEL_ID_FILE, "w") as f:
                    f.write(str(channel_id))
            except Exception:
                pass
            logging.info(f"🎉 Канал привязан: ID = {channel_id}")
            return
            
    if "channel_post" in update:
        chat = update["channel_post"]["chat"]
        channel_id = chat["id"]
        try:
            with open(CHANNEL_ID_FILE, "w") as f:
                f.write(str(channel_id))
        except Exception:
            pass
        logging.info(f"🎉 Канал привязан: ID = {channel_id}")
        return

    # Обработка сообщений
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip()
        
        # Пересылка любого сообщения из канала боту сразу привязывает ID
        if "forward_from_chat" in msg:
            fwd = msg["forward_from_chat"]
            if fwd.get("type") == "channel":
                channel_id = fwd["id"]
                try:
                    with open(CHANNEL_ID_FILE, "w") as f:
                        f.write(str(channel_id))
                except Exception:
                    pass
                send_message(chat_id, f"✅ Канал «{fwd.get('title')}» успешно привязан!")
                return

        logging.info(f"Message from {chat_id}: {text}")
        
        # На команду /start всегда отправляем блок подписки
        start_text = (
            "Привет! Рада видеть тебя здесь 🖤\n\n"
            "Я — <b>Анастасия (@via.kairos)</b>.\n"
            "Забираю страхи, выбиваю синдром «хорошей девочки» и возвращаю природную дерзость.\n\n"
            "🔒 <b>Для получения подарков обязательно подпишись на мой канал:</b>\n"
        )
        send_message(chat_id, start_text, get_sub_keyboard())
        return

    # Обработка нажатий на инлайн-кнопки
    elif "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        if cb_id in processed_callbacks:
            return
        processed_callbacks.add(cb_id)
        if len(processed_callbacks) > 2000:
            processed_callbacks.clear()
            
        chat_id = cb["message"]["chat"]["id"]
        user_id = cb["from"]["id"]
        data = cb.get("data", "")
        
        logging.info(f"Callback from {chat_id}: {data}")
        
        # 1. Нажатие на кнопку «Я подписалась!»
        if data == "check_sub":
            if channel_id and not is_subscribed_api(user_id):
                answer_callback(
                    cb_id,
                    text="❌ Ты ещё не подписалась на канал! Сначала подпишись 😉",
                    show_alert=True
                )
                return
            
            # Подписка подтверждена!
            answer_callback(cb_id, text="✅ Подписка подтверждена! Забирай подарки 🖤", show_alert=False)
            
            unlock_text = (
                "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
                "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
            )
            send_message(chat_id, unlock_text, get_main_keyboard())
            return
            
        answer_callback(cb_id)
        
        # 2. Выдача «Манифест наглости»
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
            
        # 3. Выдача «Я жадная: хочу забрать ВСЁ»
        elif data == "gift_both":
            caption = (
                "🔥 <b>Обожаю жадных до жизни и денег девушек! Именно такие и забирают всё лучшее</b>\n\n"
                "Твой полный комплект Наглости готов:\n\n"
                "1️⃣ <b>ГАЙД:</b> «Манифест Наглости» синдром хорошей девочки.\n"
                "2️⃣ <b>КНИГА:</b> Книга «Как красиво просить,отвечать и уходить».\n\n"
                "Скромность не украшает. Украшают чеки и подарки 😉"
            )
            send_document(chat_id, PDF_FILE_PATH, caption=caption, reply_markup=get_after_gift_keyboard())

def main():
    logging.info("🚀 Starting 100% Clean Polling Bot @via_kairos_bot...")
    
    try:
        requests.post(f"{API_URL}/deleteWebhook", json={"drop_pending_updates": True}, timeout=10)
        requests.post(f"{API_URL}/setChatMenuButton", json={"menu_button": {"type": "default"}}, timeout=10)
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
            logging.error(f"Polling loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
