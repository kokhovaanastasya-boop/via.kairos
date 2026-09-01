#!/usr/bin/env python3
"""
Telegram Bot for @via.kairos (Анастасия)
100% Обязательная подписка на канал перед выдачей подарков
Канал: https://t.me/+0hwBdSVNsDcyZGYy
Со встроенным веб-сервером для Render, кнопками «◀️ Вернуться назад»
и АВТОУДАЛЕНИЕМ предыдущих сообщений (чат всегда чистый: одно сообщение бота).
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import sys
import threading
import time
import requests

# Токен бота — ТОЛЬКО из переменной окружения.
# Старый токен 8850880508:AAHGe... отозван в BotFather и больше не работает (401).
# Никогда не храни токен в коде: он утекает вместе с репозиторием и перепиской.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    print("❌ Не задан BOT_TOKEN. Render: Environment -> BOT_TOKEN = токен от @BotFather.\n"
          "   Локально: BOT_TOKEN=123:ABC python3 bot.py", file=sys.stderr)
    sys.exit(1)
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

CHANNEL_INVITE_URL = "https://t.me/+0hwBdSVNsDcyZGYy"
MANUFLIRT_URL = "https://manuflirt.netlify.app/"
AUDIT_INSTAGRAM_URL = "https://www.instagram.com/via.kairos?igsi=MW8xbzVhZGFpMWRucA=="
PRESENTATION_PREVIEW_URL = "https://docs.google.com/presentation/d/1kEvbWzUoJ1VO8WXm3zR_dQ5dkm4Pe0Go/preview"
PDF_FILE_PATH = "Manifest_Naglosti_via_kairos.pdf"

CHANNEL_ID_FILE = "channel_id.txt"
channel_id = None

# Приоритет — переменная окружения (на Render файлы пропадают при передеплое)
_env_channel = os.getenv("CHANNEL_ID", "").strip()
if _env_channel:
    try:
        channel_id = int(_env_channel)
    except ValueError:
        logging.warning("CHANNEL_ID должен быть числом вида -1001234567890")

if channel_id is None and os.path.exists(CHANNEL_ID_FILE):
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

# === 🧹 ПАМЯТЬ СООБЩЕНИЙ БОТА (для автоудаления) ===
# {chat_id: [message_id, ...]}
# ВАЖНО: раньше словарь жил только в ОЗУ. На Render free-плане сервис засыпает
# через 15 мин простоя и перезапускается — память обнулялась, и старые сообщения
# оставались в чате навсегда. Теперь состояние пишется на диск.
MESSAGES_FILE = "messages.json"
last_bot_messages = {}
_msg_lock = threading.Lock()


def _load_messages():
    global last_bot_messages
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                last_bot_messages = {int(k): v for k, v in json.load(f).items()}
            logging.info(f"🗂 Загружена история сообщений: {len(last_bot_messages)} чат(ов)")
    except Exception as e:
        logging.warning(f"Не удалось прочитать {MESSAGES_FILE}: {e}")
        last_bot_messages = {}


def _save_messages():
    """Атомарная запись, чтобы файл не побился при рестарте посреди сохранения."""
    try:
        tmp = MESSAGES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in last_bot_messages.items()}, f)
        os.replace(tmp, MESSAGES_FILE)
    except Exception as e:
        logging.warning(f"Не удалось сохранить {MESSAGES_FILE}: {e}")


_load_messages()


# === 🌐 ВСТРОЕННЫЙ СЕРВЕР ДЛЯ RENDER (УСТРАНЯЕТ ОШИБКУ NO OPEN PORTS / TIMEOUT) ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("OK: via.kairos bot is active 24/7".encode("utf-8"))

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
            [{"text": "✅ Я подписалась! Забрать подарки 🎁", "callback_data": "check_sub"}]
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


# === 🧹 БАЗОВЫЕ ФУНКЦИИ УДАЛЕНИЯ ===
def delete_message(chat_id, message_id):
    """Тихое удаление одного сообщения."""
    if not message_id:
        return False
    try:
        r = requests.post(
            f"{API_URL}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id},
            timeout=5
        )
        return bool(r.json().get("ok"))
    except Exception:
        return False


def remember_message(chat_id, response):
    """Запоминаем message_id отправленного ботом сообщения."""
    try:
        if response and response.get("ok"):
            mid = response["result"]["message_id"]
            with _msg_lock:
                last_bot_messages.setdefault(chat_id, []).append(mid)
                _save_messages()
    except Exception:
        pass


def clear_previous(chat_id, extra_ids=None):
    """Удаляем ВСЕ предыдущие сообщения бота в этом чате (+ доп. id, напр. сообщение юзера)."""
    with _msg_lock:
        ids = last_bot_messages.pop(chat_id, [])
        _save_messages()
    if extra_ids:
        ids = list(ids) + [i for i in extra_ids if i]
    ids = sorted(set(i for i in ids if i), reverse=True)
    if not ids:
        return
    # удаляем параллельно — иначе 5 сообщений это 5 последовательных запросов (~1.5 c)
    threads = [threading.Thread(target=delete_message, args=(chat_id, mid), daemon=True)
               for mid in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=6)


# Глубина «подметания» старых сообщений, ID которых бот не помнит
# (например, отправленных прошлым деплоем до появления трекинга). 0 = выключить.
SWEEP_DEPTH = int(os.getenv("SWEEP_DEPTH", "40"))


def sweep_legacy_messages(chat_id, from_id, depth=None):
    """Пробуем снести хвост старых сообщений бота выше текущего.

    Чужие сообщения Telegram удалить не даст (вернёт 400) — это безопасно и тихо.
    Работает только для сообщений моложе 48 часов: таково ограничение Bot API.
    """
    depth = SWEEP_DEPTH if depth is None else depth
    if depth <= 0 or not from_id:
        return

    def _run():
        deleted = 0
        for mid in range(from_id - 1, max(0, from_id - depth - 1), -1):
            if delete_message(chat_id, mid):
                deleted += 1
        if deleted:
            logging.info(f"🧹 Подчищено старых сообщений в чате {chat_id}: {deleted}")

    threading.Thread(target=_run, daemon=True).start()


# === ОТПРАВКА (с автоудалением предыдущего экрана) ===
def send_message(chat_id, text, reply_markup=None, track=True):
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
        res = r.json()
        if not res.get("ok"):
            # ГЛАВНАЯ ПРИЧИНА "БОТ МОЛЧИТ": ошибка видна только здесь
            logging.error(
                f"❌ sendMessage FAILED [{res.get('error_code')}]: {res.get('description')} | chat={chat_id}"
            )
            if res.get("error_code") == 400 and "parse" in str(res.get("description", "")).lower():
                # HTML сломан — шлём тем же текстом, но без разметки, чтобы юзер не остался без ответа
                payload.pop("parse_mode", None)
                r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
                res = r.json()
                logging.warning("↩️ Отправлено без parse_mode (фолбэк)")
        if track:
            remember_message(chat_id, res)
        return res
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return None


def send_document(chat_id, file_path, caption=None, reply_markup=None, track=True):
    for alt in [file_path, "Manifest_Naglosti_via_kairos.pdf", "/home/user/Manifest_Naglosti_via_kairos.pdf"]:
        if os.path.exists(alt):
            file_path = alt
            break

    if not os.path.exists(file_path):
        return send_message(
            chat_id,
            (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}",
            reply_markup,
            track=track
        )

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
            res = r.json()
            if not res.get("ok"):
                logging.error(
                    f"❌ sendDocument FAILED [{res.get('error_code')}]: {res.get('description')} | chat={chat_id}"
                )
                return send_message(
                    chat_id,
                    (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}",
                    reply_markup,
                    track=track
                )
            if track:
                remember_message(chat_id, res)
            return res
    except Exception as e:
        logging.error(f"Error sending document: {e}")
        return send_message(
            chat_id,
            (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}",
            reply_markup,
            track=track
        )


def answer_callback(cb_id, text=None, show_alert=False):
    payload = {"callback_query_id": cb_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        requests.post(f"{API_URL}/answerCallbackQuery", json=payload, timeout=5)
    except Exception:
        pass


SUBSCRIBED_STATUSES = ("member", "administrator", "creator", "restricted")
LEFT_STATUSES = ("left", "kicked")

# Отзывать подарки, когда человек отписался от канала
REVOKE_ON_UNSUB = os.getenv("REVOKE_ON_UNSUB", "1") == "1"
# Как часто перепроверять подписчиков (сек). Нужен как подстраховка,
# если апдейт chat_member не пришёл (бот не админ / рестарт во время события).
SUB_CHECK_INTERVAL = int(os.getenv("SUB_CHECK_INTERVAL", "300"))


def get_member_status(user_id):
    """Статус пользователя в канале. None — если проверить не удалось (сеть/права)."""
    global channel_id
    if not channel_id:
        return None
    try:
        r = requests.get(
            f"{API_URL}/getChatMember",
            params={"chat_id": channel_id, "user_id": user_id},
            timeout=8
        )
        res = r.json()
        if res.get("ok"):
            return res.get("result", {}).get("status", "")
        logging.warning(f"getChatMember: {res.get('description')}")
    except Exception as e:
        logging.error(f"Error checking sub: {e}")
    return None


def is_subscribed_api(user_id):
    """Проверка подписки. При ошибке НЕ блокируем человека (пропускаем)."""
    if not channel_id:
        return True
    status = get_member_status(user_id)
    if status is None:
        return True
    return status in SUBSCRIBED_STATUSES


REVOKE_TEXT = (
    "🖤 <b>Твои подарки убраны из чата.</b>\n\n"
    "Они были доступны, пока ты в моём канале — там всё самое честное про деньги, "
    "наглость и высокие чеки.\n\n"
    "Возвращайся: подпишись заново и забери книгу и гайд обратно 👇"
)


def revoke_gifts(user_chat_id, notify=True):
    """Человек отписался — сносим все подарки и экраны, зовём обратно."""
    with _msg_lock:
        has_something = bool(last_bot_messages.get(user_chat_id))
    if not has_something:
        return
    logging.info(f"🚫 Отписка: отзываю подарки у {user_chat_id}")
    clear_previous(user_chat_id)
    if notify:
        send_message(user_chat_id, REVOKE_TEXT, get_sub_keyboard())


def subscription_watchdog():
    """Фоновая перепроверка: кто ушёл из канала — у того забираем подарки."""
    while True:
        time.sleep(SUB_CHECK_INTERVAL)
        if not (REVOKE_ON_UNSUB and channel_id):
            continue
        with _msg_lock:
            chats = [c for c in last_bot_messages.keys() if c > 0]  # только личные чаты
        for cid in chats:
            status = get_member_status(cid)
            if status in LEFT_STATUSES:   # None (ошибка) НЕ трогаем — иначе снесём лишнее
                revoke_gifts(cid)
            time.sleep(0.2)  # бережём лимиты API


BOOK_TEXT = (
    "🫦 <b>Интерактивная книга «Финансовый флирт»</b>\n"
    "<i>Искусство просить дорого, отвечать дерзко и уходить красиво</i>\n\n"
    "Хватит быть «удобной». Внутри — не просто фразы, а готовый арсенал для тех, "
    "кто устал оправдывать свои цены и хочет превратить деньги в игру, "
    "где главная героиня — ты.\n\n"
    "<b>Ты получишь:</b>\n\n"
    "💎 <b>100 готовых фраз</b> для любых переговоров: от первого свидания "
    "до контракта на миллион.\n"
    "📜 <b>4 закона</b> безупречного финансового поведения, которые работают "
    "как заклинание.\n"
    "🛡 <b>10 щитов</b> против возражений и манипуляций, после которых мужчина "
    "сам предложит больше.\n"
    "👠 <b>Мастер-класс по уходу:</b> как сорвать куш и выйти из-за стола "
    "переговоров королевой, оставив его с чувством, что он упустил нечто грандиозное.\n\n"
    "<b>Твой ход:</b> нажми на кнопку, чтобы открыть книгу прямо в Telegram 👇\n\n"
    "<i>Хочешь применить это на своей стратегии — записывайся на личный разбор.</i>"
)

MANIFEST_TEXT = (
    "⚡️ <b>«Манифест Наглости»</b> (12 слайдов)\n"
    "<i>Твой личный детокс от установок «быть хорошей»</i>\n\n"
    "<b>Внутри гайда:</b>\n\n"
    "🔎 <b>Диагностика</b> твоей роли, которая сливает деньги.\n"
    "📝 <b>Экспресс-тест</b> на твой уровень здоровой наглости "
    "(спойлер: его нужно прокачать).\n"
    "🚀 <b>Готовая формула дохода:</b> Личность → Бренд → Доход.\n"
    "💬 <b>Скрипты продаж в переписке</b>, которые закрывают сделки без стеснения.\n\n"
    "Пора прекращать быть скромной и начинать зарабатывать с удовольствием 🖤"
)

# Полный оффер для «Я жадная» — уходит ОТДЕЛЬНЫМ сообщением (лимит подписи к файлу 1024)
BOTH_TEXT = (
    "🔥 <b>Обожаю жадных до жизни и денег девушек! Именно такие и забирают всё лучшее</b>\n\n"
    "🫦 <b>Интерактивная книга «Финансовый флирт»</b>\n"
    "<i>Искусство просить дорого, отвечать дерзко и уходить красиво</i>\n\n"
    "Хватит быть «удобной». Внутри — не просто фразы, а готовый арсенал для тех, "
    "кто устал оправдывать свои цены и хочет превратить деньги в игру, "
    "где главная героиня — ты.\n\n"
    "💎 <b>100 готовых фраз</b> для любых переговоров: от первого свидания "
    "до контракта на миллион.\n"
    "📜 <b>4 закона</b> безупречного финансового поведения, которые работают как заклинание.\n"
    "🛡 <b>10 щитов</b> против возражений и манипуляций, после которых мужчина "
    "сам предложит больше.\n"
    "👠 <b>Мастер-класс по уходу:</b> как сорвать куш и выйти из-за стола "
    "переговоров королевой.\n\n"
    "🎁 <b>БОНУС К СТАРТУ: «Манифест Наглости»</b> (12 слайдов)\n"
    "Твой личный детокс от установок «быть хорошей».\n\n"
    "🔎 <b>Диагностика</b> твоей роли, которая сливает деньги.\n"
    "📝 <b>Экспресс-тест</b> на твой уровень здоровой наглости.\n"
    "🚀 <b>Формула дохода:</b> Личность → Бренд → Чек от 80 000 до 150 000 ₽.\n"
    "💬 <b>Скрипты продаж в переписке</b> без стеснения.\n\n"
    "<b>Твой ход:</b> жми на кнопки ниже — книга открывается прямо в Telegram, "
    "гайд прикреплён файлом 👇\n\n"
    "Пора прекращать быть скромной и начинать зарабатывать с удовольствием 🖤"
)

MENU_TEXT = (
    "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
    "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
)


# Telegram: подпись к файлу — до 1024 символов, текст — до 4096.
# Эмодзи считаются за 2, поэтому берём запас.
CAPTION_LIMIT = 900


def send_offer(chat_id, text, keyboard, attach_pdf=True):
    """Длинный оффер уходит текстом, файл — следом с короткой подписью."""
    if not attach_pdf:
        return send_message(chat_id, text, keyboard)

    if len(text) <= CAPTION_LIMIT:
        return send_document(chat_id, PDF_FILE_PATH, caption=text, reply_markup=keyboard)

    send_message(chat_id, text)  # сначала полное описание
    return send_document(
        chat_id,
        PDF_FILE_PATH,
        caption="📎 <b>«Манифест Наглости»</b> — твой гайд во вложении 🖤",
        reply_markup=keyboard
    )


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

    # Мгновенная реакция на выход из канала (бот должен быть админом канала)
    if "chat_member" in update:
        cm = update["chat_member"]
        try:
            if channel_id and cm["chat"]["id"] == channel_id:
                new_status = cm["new_chat_member"]["status"]
                uid = cm["new_chat_member"]["user"]["id"]
                if new_status in LEFT_STATUSES and REVOKE_ON_UNSUB:
                    revoke_gifts(uid)          # в личке chat_id == user_id
                elif new_status in SUBSCRIBED_STATUSES:
                    logging.info(f"➕ Новый подписчик канала: {uid}")
        except Exception as e:
            logging.warning(f"chat_member: {e}")
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
        user_id = (msg.get("from") or {}).get("id")  # у анонимных постов "from" нет -> раньше KeyError убивал цикл
        user_msg_id = msg.get("message_id")
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
                clear_previous(chat_id, extra_ids=[user_msg_id])
                send_message(chat_id, f"✅ Канал «{fwd.get('title')}» успешно привязан!")
                return

        logging.info(f"Message from {chat_id}: {text}")

        # 🧹 сносим прошлый экран бота + само сообщение пользователя
        clear_previous(chat_id, extra_ids=[user_msg_id])
        # и хвост старых сообщений, ID которых бот не помнит (прошлый деплой)
        sweep_legacy_messages(chat_id, user_msg_id)

        start_text = (
            "Привет! Рада видеть тебя здесь 🖤\n\n"
            "Я — <b>Анастасия (@via.kairos)</b>.\n"
            "Забираю страхи, выбиваю синдром «хорошей девочки» и возвращаю природную дерзость.\n\n"
            "🔒 <b>Для получения подарков обязательно подпишись на мой канал:</b>\n"
        )
        res = send_message(chat_id, start_text, get_sub_keyboard())
        if res and res.get("ok"):
            logging.info(f"✅ Приветствие отправлено в чат {chat_id}")
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
            # 🧹 удаляем экран с подпиской
            clear_previous(chat_id, extra_ids=[message_id])
            send_message(chat_id, MENU_TEXT, get_main_keyboard())
            return

        # 2. Кнопка «◀️ Вернуться назад»
        elif data == "back_to_menu":
            answer_callback(cb_id)
            clear_previous(chat_id, extra_ids=[message_id])
            send_message(chat_id, MENU_TEXT, get_main_keyboard())
            return

        answer_callback(cb_id)

        # 🧹 перед выдачей подарка удаляем меню / прошлый экран
        clear_previous(chat_id, extra_ids=[message_id])

        # 3. Выбор гайда «Манифест наглости»
        if data == "gift_money":
            send_offer(chat_id, MANIFEST_TEXT, get_manifest_keyboard(), attach_pdf=True)

        # 4. Выбор книги «Финансовый флирт»
        elif data == "gift_book":
            send_offer(chat_id, BOOK_TEXT, get_book_keyboard(), attach_pdf=False)

        # 5. Выбор «Я жадная: хочу забрать ВСЁ»
        elif data == "gift_both":
            send_offer(chat_id, BOTH_TEXT, get_both_keyboard(), attach_pdf=True)


def main():
    # Запускаем встроенный HTTP-сервер для Render в отдельном потоке
    http_thread = threading.Thread(target=start_health_server, daemon=True)
    http_thread.start()

    logging.info("🚀 Starting Bot...")

    # Проверка токена — сразу видно в логах Render, живой бот или нет
    try:
        me = requests.get(f"{API_URL}/getMe", timeout=10).json()
        if me.get("ok"):
            logging.info(f"✅ Токен рабочий: @{me['result'].get('username')} (id={me['result'].get('id')})")
        else:
            logging.error(f"❌ ТОКЕН НЕВЕРНЫЙ: {me}")
            sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Нет связи с Telegram API: {e}")

    try:
        requests.post(
            f"{API_URL}/deleteWebhook",
            json={"drop_pending_updates": DROP_PENDING},
            timeout=10
        )
        requests.post(f"{API_URL}/setChatMenuButton", json={"menu_button": {"type": "default"}}, timeout=10)
    except Exception:
        pass

    threading.Thread(target=subscription_watchdog, daemon=True).start()
    logging.info(
        f"👀 Watchdog подписки: проверка каждые {SUB_CHECK_INTERVAL} c, "
        f"отзыв подарков {'ВКЛ' if REVOKE_ON_UNSUB else 'ВЫКЛ'}"
    )

    if channel_id:
        logging.info(f"🔗 Канал привязан: {channel_id}")
    else:
        logging.warning("⚠️ Канал НЕ привязан (channel_id.txt пуст) — проверка подписки пропускается. "
                        "Добавь бота админом в канал ИЛИ перешли ему любой пост из канала.")

    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API_URL}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": json.dumps(ALLOWED_UPDATES)
                },
                timeout=40
            )
            if r.status_code == 409:
                logging.error("❌ CONFLICT 409: этот же токен уже опрашивается другим процессом "
                              "(второй деплой/локальный запуск). Оставь только ОДИН экземпляр бота!")
                time.sleep(5)
                continue
            if r.status_code == 200:
                res = r.json()
                if res.get("ok"):
                    for update in res.get("result", []):
                        offset = update["update_id"] + 1
                        try:
                            handle_update(update)
                        except Exception as e:
                            logging.exception(f"Ошибка обработки апдейта: {e}")
            else:
                logging.error(f"getUpdates HTTP {r.status_code}: {r.text[:200]}")
                time.sleep(2)
            time.sleep(0.1)
        except requests.exceptions.ReadTimeout:
            continue
        except Exception as e:
            logging.error(f"Polling loop: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
