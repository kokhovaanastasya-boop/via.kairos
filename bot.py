#!/usr/bin/env python3
"""
Telegram-бот @via_kairos_bot — выдача подарков за подписку на канал.

Что умеет:
  • обязательная подписка на канал перед выдачей подарков;
  • в чате всегда один экран — предыдущие сообщения бота удаляются;
  • подарки живут, пока человек подписан; отписался — подарки отзываются;
  • встроенный веб-сервер для Render (иначе сервис падает с "no open ports").
"""

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# =============================================================================
#  НАСТРОЙКИ — вставляй значения между кавычками
# =============================================================================

BOT_TOKEN = "8850880508:AAHkNZVl8XphClnwPAVIT80hTm5-CJeh_L4"          # токен от @BotFather

CHANNEL_ID = -1002611112542               # ID канала «I Allow» (число, без кавычек)
CHANNEL_INVITE_URL = "https://t.me/+0hwBdSVNsDcyZGYy"

MANUFLIRT_URL = "https://manuflirt.netlify.app/"
AUDIT_INSTAGRAM_URL = "https://www.instagram.com/via.kairos?igsi=MW8xbzVhZGFpMWRucA=="
PRESENTATION_PREVIEW_URL = "https://docs.google.com/presentation/d/1kEvbWzUoJ1VO8WXm3zR_dQ5dkm4Pe0Go/preview"
PDF_FILE_PATH = "Manifest_Naglosti_via_kairos.pdf"

REVOKE_ON_UNSUB = True     # отзывать подарки, когда человек ушёл из канала
SUB_CHECK_INTERVAL = 300   # как часто перепроверять подписчиков, сек
SWEEP_DEPTH = 40           # сколько старых сообщений подчищать при /start
MESSAGES_FILE = "messages.json"

# =============================================================================

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "channel_post", "chat_member"]
SUBSCRIBED_STATUSES = ("member", "administrator", "creator", "restricted")
LEFT_STATUSES = ("left", "kicked")
CAPTION_LIMIT = 900        # у Telegram лимит подписи 1024, берём запас на эмодзи

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

channel_id = CHANNEL_ID
processed_updates = set()
processed_callbacks = set()


# =============================================================================
#  ТЕКСТЫ
# =============================================================================

START_TEXT = (
    "Привет! Рада видеть тебя здесь 🖤\n\n"
    "Я — <b>Анастасия (@via.kairos)</b>.\n"
    "Забираю страхи, выбиваю синдром «хорошей девочки» и возвращаю природную дерзость.\n\n"
    "🔒 <b>Для получения подарков обязательно подпишись на мой канал:</b>"
)

MENU_TEXT = (
    "⚡️ <b>Твой подарок — это не просто подарок. Это пропуск в мой мир наглости😉</b>\n\n"
    "Выбирай, какой подарок хочешь забрать прямо сейчас 👇"
)

BOOK_TEXT = (
    "🫦 <b>Интерактивная книга «Финансовый флирт»</b>\n"
    "<i>Искусство просить дорого, отвечать дерзко и уходить красиво</i>\n\n"
    "Хватит быть «удобной». Внутри — не просто фразы, а готовый арсенал для тех, "
    "кто устал оправдывать свои цены и хочет превратить деньги в игру, "
    "где главная героиня — ты.\n\n"
    "<b>Ты получишь:</b>\n\n"
    "💎 <b>100 готовых фраз</b> для любых переговоров: от первого свидания "
    "до контракта на миллион.\n"
    "📜 <b>4 закона</b> безупречного финансового поведения, которые работают как заклинание.\n"
    "🛡 <b>10 щитов</b> против возражений и манипуляций, после которых мужчина "
    "сам предложит больше.\n"
    "👠 <b>Мастер-класс по уходу:</b> как сорвать куш и выйти из-за стола переговоров "
    "королевой, оставив его с чувством, что он упустил нечто грандиозное.\n\n"
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
    "🚀 <b>Готовая формула дохода:</b> Личность → Бренд → Чек от 80 000 до 150 000 ₽.\n"
    "💬 <b>Скрипты продаж в переписке</b>, которые закрывают сделки без стеснения.\n\n"
    "Пора прекращать быть скромной и начинать зарабатывать с удовольствием 🖤"
)

BOTH_TEXT = (
    "🔥 <b>Обожаю жадных до жизни и денег девушек! Именно такие и забирают всё лучшее</b>\n\n"
    "🫦 <b>Интерактивная книга «Финансовый флирт»</b>\n"
    "<i>Искусство просить дорого, отвечать дерзко и уходить красиво</i>\n\n"
    "Хватит быть «удобной». Внутри — не просто фразы, а готовый арсенал для тех, "
    "кто устал оправдывать свои цены и хочет превратить деньги в игру, "
    "где главная героиня — ты.\n\n"
    "💎 <b>100 готовых фраз</b> для любых переговоров: от первого свидания "
    "до контракта на миллион.\n"
    "📜 <b>4 закона</b> безупречного финансового поведения.\n"
    "🛡 <b>10 щитов</b> против возражений и манипуляций.\n"
    "👠 <b>Мастер-класс по уходу:</b> как сорвать куш и выйти из-за стола переговоров "
    "королевой.\n\n"
    "🎁 <b>БОНУС К СТАРТУ: «Манифест Наглости»</b> (12 слайдов)\n"
    "Твой личный детокс от установок «быть хорошей».\n\n"
    "🔎 <b>Диагностика</b> роли, которая сливает деньги.\n"
    "📝 <b>Экспресс-тест</b> на уровень здоровой наглости.\n"
    "🚀 <b>Формула дохода:</b> Личность → Бренд → Чек от 80 000 до 150 000 ₽.\n"
    "💬 <b>Скрипты продаж в переписке</b> без стеснения.\n\n"
    "<b>Твой ход:</b> книга открывается прямо в Telegram, гайд прикреплён файлом 👇\n\n"
    "Пора прекращать быть скромной и начинать зарабатывать с удовольствием 🖤"
)

NOT_SUBSCRIBED_ALERT = "❌ Ты ещё не подписалась на канал! Сначала подпишись 😉"
SUBSCRIBED_ALERT = "✅ Подписка подтверждена! Забирай подарки 🖤"

REVOKE_TEXT = (
    "🖤 <b>Твои подарки убраны из чата.</b>\n\n"
    "Они были доступны, пока ты в моём канале — там всё самое честное про деньги, "
    "наглость и высокие чеки.\n\n"
    "Возвращайся: подпишись заново и забери книгу и гайд обратно 👇"
)


# =============================================================================
#  КЛАВИАТУРЫ
# =============================================================================

def kb_subscribe():
    return {"inline_keyboard": [
        [{"text": "🖤 Подписаться на канал", "url": CHANNEL_INVITE_URL}],
        [{"text": "✅ Я подписалась! Забрать подарки 🎁", "callback_data": "check_sub"}],
    ]}


def kb_menu():
    return {"inline_keyboard": [
        [{"text": "💸 Манифест наглости", "callback_data": "gift_money"}],
        [{"text": "🫦 Финансовый флирт", "callback_data": "gift_book"}],
        [{"text": "🔥 Я жадная: хочу забрать ВСЁ и сразу!", "callback_data": "gift_both"}],
    ]}


def kb_manifest():
    return {"inline_keyboard": [
        [{"text": "💸 Гайд «Манифест наглости»", "url": PRESENTATION_PREVIEW_URL}],
        [{"text": "🎯 Записаться на Разбор", "url": AUDIT_INSTAGRAM_URL}],
        [{"text": "◀️ Вернуться назад", "callback_data": "back_to_menu"}],
    ]}


def kb_book():
    return {"inline_keyboard": [
        [{"text": "🫦 Открыть книгу «Финансовый флирт»", "web_app": {"url": MANUFLIRT_URL}}],
        [{"text": "🎯 Записаться на Разбор", "url": AUDIT_INSTAGRAM_URL}],
        [{"text": "◀️ Вернуться назад", "callback_data": "back_to_menu"}],
    ]}


def kb_both():
    return {"inline_keyboard": [
        [{"text": "💸 Гайд «Манифест наглости»", "url": PRESENTATION_PREVIEW_URL}],
        [{"text": "🫦 Книга «Финансовый флирт»", "web_app": {"url": MANUFLIRT_URL}}],
        [{"text": "🎯 Записаться на Разбор", "url": AUDIT_INSTAGRAM_URL}],
        [{"text": "◀️ Вернуться назад", "callback_data": "back_to_menu"}],
    ]}


# =============================================================================
#  ПАМЯТЬ ОТПРАВЛЕННЫХ СООБЩЕНИЙ
#  Хранится на диске: Render перезапускает сервис, а ID удаляемых
#  сообщений теряться не должны.
# =============================================================================

sent_messages = {}          # {chat_id: [message_id, ...]}
_lock = threading.Lock()


def load_state():
    global sent_messages
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, encoding="utf-8") as f:
                sent_messages = {int(k): v for k, v in json.load(f).items()}
            logging.info(f"🗂 История сообщений загружена: {len(sent_messages)} чат(ов)")
    except Exception as e:
        logging.warning(f"Не удалось прочитать {MESSAGES_FILE}: {e}")
        sent_messages = {}


def save_state():
    try:
        tmp = MESSAGES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in sent_messages.items()}, f)
        os.replace(tmp, MESSAGES_FILE)   # атомарно: файл не побьётся при рестарте
    except Exception as e:
        logging.warning(f"Не удалось сохранить {MESSAGES_FILE}: {e}")


def remember(chat_id, response):
    if response and response.get("ok"):
        with _lock:
            sent_messages.setdefault(chat_id, []).append(response["result"]["message_id"])
            save_state()


# =============================================================================
#  TELEGRAM API
# =============================================================================

def api_post(method, **kwargs):
    try:
        return requests.post(f"{API_URL}/{method}", timeout=kwargs.pop("timeout", 10), **kwargs).json()
    except Exception as e:
        logging.error(f"{method}: {e}")
        return None


def send_message(chat_id, text, keyboard=None, track=True):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = keyboard

    res = api_post("sendMessage", json=payload)

    if res and not res.get("ok"):
        logging.error(f"❌ sendMessage [{res.get('error_code')}]: {res.get('description')} | chat={chat_id}")
        if "parse" in str(res.get("description", "")).lower():
            payload.pop("parse_mode")          # сломалась разметка — шлём без неё
            res = api_post("sendMessage", json=payload)
            logging.warning("↩️ Отправлено без parse_mode")

    if track:
        remember(chat_id, res)
    return res


def send_document(chat_id, caption=None, keyboard=None, track=True):
    if not os.path.exists(PDF_FILE_PATH):
        logging.warning(f"Файл {PDF_FILE_PATH} не найден — отправляю ссылку")
        return send_message(
            chat_id,
            (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}",
            keyboard, track,
        )

    data = {"chat_id": chat_id, "parse_mode": "HTML"}
    if caption:
        data["caption"] = caption
    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)

    try:
        with open(PDF_FILE_PATH, "rb") as f:
            files = {"document": ("Манифест_Наглости_via_kairos.pdf", f, "application/pdf")}
            res = requests.post(f"{API_URL}/sendDocument", data=data, files=files, timeout=30).json()
    except Exception as e:
        logging.error(f"sendDocument: {e}")
        res = None

    if not res or not res.get("ok"):
        if res:
            logging.error(f"❌ sendDocument [{res.get('error_code')}]: {res.get('description')}")
        return send_message(
            chat_id,
            (caption or "") + f"\n\n📖 <b>Читать онлайн:</b> {PRESENTATION_PREVIEW_URL}",
            keyboard, track,
        )

    if track:
        remember(chat_id, res)
    return res


def answer_callback(callback_id, text=None, alert=False):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = alert
    api_post("answerCallbackQuery", json=payload, timeout=5)


def delete_message(chat_id, message_id):
    if not message_id:
        return False
    res = api_post("deleteMessage", json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
    return bool(res and res.get("ok"))


# =============================================================================
#  УДАЛЕНИЕ ПРЕДЫДУЩИХ СООБЩЕНИЙ
# =============================================================================

def clear_chat(chat_id, extra_ids=None):
    """Сносит все сообщения бота в чате (+ переданные id) параллельно."""
    with _lock:
        ids = sent_messages.pop(chat_id, [])
        save_state()

    ids = sorted({i for i in list(ids) + list(extra_ids or []) if i}, reverse=True)
    if not ids:
        return

    threads = [threading.Thread(target=delete_message, args=(chat_id, i), daemon=True) for i in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=6)


def sweep_old(chat_id, from_id):
    """Подчищает хвост старых сообщений, ID которых бот не помнит.

    Чужие сообщения Telegram удалить не даст (вернёт 400) — это безопасно.
    Работает только для сообщений моложе 48 часов: ограничение Bot API.
    """
    if SWEEP_DEPTH <= 0 or not from_id:
        return

    def run():
        count = sum(delete_message(chat_id, mid)
                    for mid in range(from_id - 1, max(0, from_id - SWEEP_DEPTH - 1), -1))
        if count:
            logging.info(f"🧹 Подчищено старых сообщений в чате {chat_id}: {count}")

    threading.Thread(target=run, daemon=True).start()


# =============================================================================
#  ПОДПИСКА НА КАНАЛ
# =============================================================================

def get_member_status(user_id):
    """Статус в канале. None — если проверить не удалось (сеть/права)."""
    if not channel_id:
        return None
    try:
        res = requests.get(
            f"{API_URL}/getChatMember",
            params={"chat_id": channel_id, "user_id": user_id},
            timeout=8,
        ).json()
        if res.get("ok"):
            return res["result"].get("status", "")
        logging.warning(f"getChatMember: {res.get('description')}")
    except Exception as e:
        logging.error(f"getChatMember: {e}")
    return None


def is_subscribed(user_id):
    """При ошибке проверки человека НЕ блокируем."""
    if not channel_id:
        return True
    status = get_member_status(user_id)
    return True if status is None else status in SUBSCRIBED_STATUSES


def revoke_gifts(chat_id):
    """Человек отписался — убираем подарки и зовём обратно."""
    with _lock:
        if not sent_messages.get(chat_id):
            return
    logging.info(f"🚫 Отписка: отзываю подарки у {chat_id}")
    clear_chat(chat_id)
    send_message(chat_id, REVOKE_TEXT, kb_subscribe())


def watchdog():
    """Подстраховка, если апдейт об отписке не пришёл (бот лежал, нет прав)."""
    while True:
        time.sleep(SUB_CHECK_INTERVAL)
        if not (REVOKE_ON_UNSUB and channel_id):
            continue
        with _lock:
            chats = [c for c in sent_messages if c > 0]   # только личные чаты
        for cid in chats:
            if get_member_status(cid) in LEFT_STATUSES:   # None не трогаем
                revoke_gifts(cid)
            time.sleep(0.2)                               # бережём лимиты API


# =============================================================================
#  ВЫДАЧА ПОДАРКОВ
# =============================================================================

def send_offer(chat_id, text, keyboard, with_pdf):
    """Длинный текст не влезает в подпись к файлу — тогда шлём его отдельно."""
    if not with_pdf:
        return send_message(chat_id, text, keyboard)

    if len(text) <= CAPTION_LIMIT:
        return send_document(chat_id, caption=text, keyboard=keyboard)

    send_message(chat_id, text)
    return send_document(
        chat_id,
        caption="📎 <b>«Манифест Наглости»</b> — твой гайд во вложении 🖤",
        keyboard=keyboard,
    )


# =============================================================================
#  ОБРАБОТКА АПДЕЙТОВ
# =============================================================================

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    message_id = msg.get("message_id")
    text = (msg.get("text") or "").strip()

    # пересланный пост из канала — быстрый способ узнать ID канала
    fwd = msg.get("forward_from_chat")
    if fwd and fwd.get("type") == "channel":
        logging.info(f"🎉 ID канала «{fwd.get('title')}»: {fwd['id']}")
        clear_chat(chat_id, [message_id])
        send_message(chat_id, f"✅ Канал «{fwd.get('title')}»\nID: <code>{fwd['id']}</code>")
        return

    logging.info(f"Сообщение от {chat_id}: {text}")

    clear_chat(chat_id, [message_id])
    sweep_old(chat_id, message_id)

    if send_message(chat_id, START_TEXT, kb_subscribe()):
        logging.info(f"✅ Приветствие отправлено в чат {chat_id}")


def handle_callback(cb):
    callback_id = cb["id"]
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    user_id = cb["from"]["id"]
    data = cb.get("data", "")

    logging.info(f"Кнопка от {chat_id}: {data}")

    if data == "check_sub":
        if not is_subscribed(user_id):
            answer_callback(callback_id, NOT_SUBSCRIBED_ALERT, alert=True)
            return
        answer_callback(callback_id, SUBSCRIBED_ALERT)
        clear_chat(chat_id, [message_id])
        send_message(chat_id, MENU_TEXT, kb_menu())
        return

    answer_callback(callback_id)
    clear_chat(chat_id, [message_id])

    if data == "back_to_menu":
        send_message(chat_id, MENU_TEXT, kb_menu())
    elif data == "gift_money":
        send_offer(chat_id, MANIFEST_TEXT, kb_manifest(), with_pdf=True)
    elif data == "gift_book":
        send_offer(chat_id, BOOK_TEXT, kb_book(), with_pdf=False)
    elif data == "gift_both":
        send_offer(chat_id, BOTH_TEXT, kb_both(), with_pdf=True)


def handle_update(update):
    global channel_id

    update_id = update.get("update_id")
    if update_id in processed_updates:
        return
    processed_updates.add(update_id)
    if len(processed_updates) > 2000:
        processed_updates.clear()

    # выход из канала — забираем подарки
    if "chat_member" in update:
        cm = update["chat_member"]
        if channel_id and cm["chat"]["id"] == channel_id:
            status = cm["new_chat_member"]["status"]
            user_id = cm["new_chat_member"]["user"]["id"]
            if status in LEFT_STATUSES and REVOKE_ON_UNSUB:
                revoke_gifts(user_id)          # в личке chat_id == user_id
            elif status in SUBSCRIBED_STATUSES:
                logging.info(f"➕ Новый подписчик канала: {user_id}")
        return

    # бота добавили в канал администратором
    if "my_chat_member" in update:
        chat = update["my_chat_member"]["chat"]
        if chat.get("type") in ("channel", "supergroup"):
            logging.info(f"🎉 Бот добавлен в «{chat.get('title')}», ID: {chat['id']}")
        return

    if "channel_post" in update:
        return

    if "message" in update:
        handle_message(update["message"])
        return

    if "callback_query" in update:
        cb = update["callback_query"]
        if cb["id"] in processed_callbacks:
            return
        processed_callbacks.add(cb["id"])
        if len(processed_callbacks) > 2000:
            processed_callbacks.clear()
        handle_callback(cb)


# =============================================================================
#  ВЕБ-СЕРВЕР ДЛЯ RENDER
#  Без открытого порта Render считает деплой неудачным и гасит сервис.
# =============================================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("OK: via.kairos bot is active 24/7".encode())

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def start_health_server():
    port = int(os.getenv("PORT", 10000))
    try:
        logging.info(f"🌐 Health-сервер слушает порт {port}")
        HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except Exception as e:
        logging.error(f"Health-сервер: {e}")


# =============================================================================
#  ЗАПУСК
# =============================================================================

def main():
    load_state()
    threading.Thread(target=start_health_server, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()

    logging.info("🚀 Запуск бота...")

    me = api_post("getMe")
    if me and me.get("ok"):
        logging.info(f"✅ Токен рабочий: @{me['result']['username']}")
    else:
        logging.error(f"❌ Проблема с токеном: {me}")

    logging.info(f"🔗 Канал: {channel_id} | отзыв подарков при отписке: "
                 f"{'ВКЛ' if REVOKE_ON_UNSUB else 'ВЫКЛ'}")

    api_post("deleteWebhook", json={"drop_pending_updates": False})
    api_post("setChatMenuButton", json={"menu_button": {"type": "default"}})

    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": offset, "timeout": 25,
                        "allowed_updates": json.dumps(ALLOWED_UPDATES)},
                timeout=40,
            )

            if r.status_code == 409:
                logging.error("❌ CONFLICT 409: тот же токен опрашивает другой процесс. "
                              "Оставь только ОДИН запущенный экземпляр бота!")
                time.sleep(5)
                continue

            if r.status_code != 200:
                logging.error(f"getUpdates HTTP {r.status_code}: {r.text[:200]}")
                time.sleep(2)
                continue

            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle_update(update)
                except Exception as e:
                    logging.exception(f"Ошибка обработки апдейта: {e}")

        except requests.exceptions.ReadTimeout:
            continue
        except Exception as e:
            logging.error(f"Цикл опроса: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()

