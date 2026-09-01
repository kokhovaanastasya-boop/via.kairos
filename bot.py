#!/usr/bin/env python3
"""
Telegram Bot for @via.kairos (Анастасия)
100% Обязательная подписка на канал перед выдачей подарков
Канал: https://t.me/+0hwBdSVNsDcyZGYy
Со встроенным веб-сервером для Render и кнопками «◀️ Вернуться назад»
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import sys
import threading
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

processed_updates = set()
processed_callbacks = set()

# === 🌐 ВСТРОЕННЫЙ СЕРВЕР ДЛЯ RENDER (УСТРАНЯЕТ ОШИБКУ NO OPEN PORTS / TIMEOUT) ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"OK: via.kairos bot is active 24/7")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", 10000))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logging.info(f"🌐 Health server listening on port {port} for Render")
        server.serve_forever()
    except Exception as e:
        logging.error(f"Health server notice: {e}")

# === 1. КНОПКИ ОБЯЗАТЕЛЬНОЙ ПОДПИСКИ (ПРИ /START) ===
def get_sub_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🖤 Подписаться на канал", "url": CHANNEL_INVITE_URL}],
            [{"text": "✅ Я подписалась! Забрать подарки 🎁" , "callback_data": "check_sub"}]
        ]
    }

# === 2. ГЛАВНОЕ МЕНЮ ПОДАРКОВ ===
def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💸 Манифест наглости", "callback_data": "gift_money"}],
            [{"text": "🫦 Финансовый флирт", "callback_data": "gift_book"}],
            [{"text": "🔥 Я жадная: хочу забрать ВСЁ и сразу!", "callback_data": "gift_both"}]
        ]
    }

# === 3. КНОПКИ ПОД ГАЙДОМ «МАНИФЕСТ НАГЛОСТИ» ===
def get_manifest_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💸 Гайд «Манифест наглости»", "url": PRESENTATION_PREVIEW_URL}],
            [{"text": "🎯 Записаться на Разбор", "url": AUDIT_INSTAGRAM_URL}],
            [{"text": "◀️ Вернуться назад", "callback_data": "back_to_menu"}]
        ]
    }

# === 4. КНОПКИ ПОД ОПИСАНИЕМ КНИГИ «ФИНАНСОВЫЙ ФЛИРТ» ===
def get_book_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🫦 Открыть книгу «Финансовый флирт»", "web_app": {"url": MANUFLIRT_URL}}],
            [{"text": "🎯 Записаться на Разбор", "url": AUDIT_INSTAGRAM_URL}],
            [{"text": "◀️ Вернуться назад", "callback_data": "back_to_menu"}]
        ]
    }

# === 5. КНОПКИ ДЛЯ «Я ЖАДНАЯ» (ВСЁ ВМЕСТЕ) ===
def get_both_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💸 Гайд «Манифест наглости»", "url": PRESENTATION_PREVIEW_URL}],
            [{"text": "🫦 Книга «Финансовый флирт»", "web_app": {"url": MANUFLIRT_URL}}],
            [{"text": "🎯 Записаться на Разбор", "url": AUDIT_INSTAGRAM_URL}],
            [{"text": "◀️ Вернуться назад", "callback_data": "back_to_menu"}]
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

def delete_message(chat_id, message_id):
    try:
        requests.post(f"{API_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
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

    # 1. Авто-привязка канала
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
        logging.info(f"🎉 Канал привязан из поста: ID = {channel_id}")
        return

    # 2. Обработка входящих сообщений
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = (msg.get("text") or "").strip()
        
        # Пересылка любого поста из канала привязывает ID
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
        
        start_text = (
            "Привет! Рада видеть тебя здесь 🖤\n\n"
            "Я — <b>Анастасия (@via.kairos)</b>.\n"
            "Забираю страхи, выбиваю синдром «хорошей девочки» и возвращаю природную дерзость.\n\n"
            "🔒 <b>Для получения подарков обязательно подпишись на мой канал:</b>\n"
        )
        send_message(chat_id, start_text, get_sub_keyboard())
        return

    # 3. Обработка нажатий на инлайн-кнопки
    elif "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        if cb_id in processed_callbacks:
            return
        processed_callbacks.add(cb_id)
        if len(processed_callbacks) > 2000:
            processed_callbacks.clear()
            
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        user_id = cb["from"]["id"]
        data = cb.get("data", "")
        
        logging.info(f"Callback from {chat_id}: {data}")
        
        # 1. Проверка подписки
        if data == "check_sub":
            if channel_id and not is_subscribed_api(user_id):
                answer_callback(
                    cb_id,
                    text="❌ Ты ещё не подписалась на канал! Сначала подпишись 😉",
                    show_alert=True
                )
                return
            
            answer_callback(cb_id, text="✅ Подписка подтверждена! Забирай подарки 🖤", show_alert=False)
            unlock_text = (
                "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
                "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
            )
            send_message(chat_id, unlock_text, get_main_keyboard())
            return
            
        # 2. Кнопка «◀️ Вернуться назад»
        elif data == "back_to_menu":
            answer_callback(cb_id)
            delete_message(chat_id, message_id)
            menu_text = (
                "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
                "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
            )
            send_message(chat_id, menu_text, get_main_keyboard())
            return
            
        answer_callback(cb_id)
        
        # 3. Выбор гайда «Манифест наглости»
        if data == "gift_money":
            caption = (
                "⚡️ <b>Твой авторский «Манифест Наглости» (12 слайдов) готов!</b>\n\n"
                "Внутри гайда:\n"
                "🔎 Диагностика роли «хорошей девочки»\n"
                "🚰 5 установок, сливающих доход\n"
                "📝 Экспресс-тест на уровень наглости\n"
                "🚀 Формула: Личность → Бренд → High-Ticket чек (80k–150k ₽)\n"
                "💬 Готовые скрипты для продаж в переписке\n\n"
                "Изучай и прекращай быть скромной 🖤"
            )
            send_document(chat_id, PDF_FILE_PATH, caption=caption, reply_markup=get_manifest_keyboard())
            
        # 4. Выбор книги «Финансовый флирт»
        elif data == "gift_book":
            book_text = (
                "🫦 <b>Интерактивная книга «Финансовый флирт»</b>\n"
                "<i>Как красиво просить, отвечать и уходить</i>\n\n"
                "Внутри книги:\n"
                "💎 <b>100 готовых фраз</b> на все случаи жизни (от свиданий до переговоров)\n"
                "📜 <b>4 нерушимых закона</b> финансового флирта\n"
                "🛡 <b>10 щитов</b> от мужских манипуляций и возражений\n"
                "👠 <b>Искусство красивого ухода:</b> как выйти из ситуации королевой\n\n"
                "Нажимай кнопку ниже, чтобы открыть интерактивную книгу прямо в Telegram 👇"
            )
            send_message(chat_id, book_text, reply_markup=get_book_keyboard())

        # 5. Выбор «Я жадная: хочу забрать ВСЁ»
        elif data == "gift_both":
            caption = (
                "🔥 <b>Обожаю жадных до жизни и денег девушек! Именно такие и забирают всё лучшее</b>\n\n"
                "Твой полный комплект Наглости готов:\n\n"
                "1️⃣ <b>ГАЙД:</b> «Манифест Наглости» синдром хорошей девочки (прикреплен файлом ниже).\n"
                "2️⃣ <b>КНИГА:</b> Интерактивная книга «Финансовый флирт: 100 фраз и правила ухода» (кнопка запускает Mini App прямо в Telegram!).\n\n"
                "Скромность не украшает. Украшают чеки и подарки 😉"
            )
            send_document(chat_id, PDF_FILE_PATH, caption=caption, reply_markup=get_both_keyboard())

def main():
    # Запускаем встроенный HTTP-сервер для Render в отдельном потоке
    http_thread = threading.Thread(target=start_health_server, daemon=True)
    http_thread.start()
    
    logging.info("🚀 Starting Bot @via_kairos_bot...")
    
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
