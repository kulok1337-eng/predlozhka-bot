#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
«Типичный Норильск (ПРЕДЛОЖКА)»
Люди кидают текст / фото / видео / альбомы -> пост приходит админам
с кнопками -> админ жмёт «Опубликовать» -> пост выходит в канал.

Зависимостей нет: нужен только Python 3.8+
Запуск: python3 bot.py
"""

import json
import os
import random
import time
import traceback
import urllib.request

# ================== НАСТРОЙКИ ==================
TOKEN = "9108881760:AAE_PoQGe5iTPYjx1usqe57wk52K8g26Hgw"
ADMINS = [1979046241, 8079727075]
# ===============================================

API = "https://api.telegram.org/bot" + TOKEN
DATA = "data"
POSTS_DIR = os.path.join(DATA, "posts")
os.makedirs(POSTS_DIR, exist_ok=True)
CHANNEL_FILE = os.path.join(DATA, "channel.json")
SETTINGS_FILE = os.path.join(DATA, "settings.json")

WELCOME = (
    "👋 Привет!\n\n"
    "Это бот-предложка канала «Типичный Норильск».\n\n"
    "Просто пришли сюда свой пост — текст, фото, видео или альбом — "
    "и он попадёт на рассмотрение админам.\n\n"
    "✅ Если пост одобрят, он появится в канале."
)


# ---------------- Telegram API ----------------

def tg(method, **params):
    """Вызов метода Telegram Bot API, возвращает dict."""
    url = API + "/" + method
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.request.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": str(e)}


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def get_settings():
    return load_json(SETTINGS_FILE, {"anon": True})


def get_channel():
    return load_json(CHANNEL_FILE, None)


# ---------------- Вспомогательное ----------------

def name_of(msg):
    u = msg.get("from", {})
    nm = u.get("first_name", "")
    if u.get("last_name"):
        nm += " " + u["last_name"]
    return nm.strip() or "Без имени"


def admin_name(cb_or_msg):
    u = cb_or_msg.get("from", {})
    nm = u.get("first_name", "")
    if u.get("last_name"):
        nm += " " + u["last_name"]
    if u.get("username"):
        nm += f" (@{u['username']})"
    return nm.strip()


def extract_media(msg):
    """Возвращает (type, file_id) для медиа-сообщения или None."""
    for t in ("photo", "video", "animation", "document", "audio", "voice", "video_note"):
        if t in msg:
            obj = msg[t]
            if t == "photo":
                return t, obj[-1]["file_id"]
            return t, obj["file_id"]
    return None


def build_media_group(post):
    """Собирает media для sendMediaGroup из сохранённого поста-альбома."""
    media = []
    for i, m in enumerate(post["messages"]):
        if not m.get("media"):
            continue
        item = {"type": m["media"]["type"], "media": m["media"]["file_id"]}
        if i == 0 and m.get("caption"):
            item["caption"] = m["caption"]
        media.append(item)
    return media


def post_kb(post_id):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Опубликовать", "callback_data": "pub:%s" % post_id},
                {"text": "❌ Отклонить", "callback_data": "rej:%s" % post_id},
            ]
        ]
    }


# ---------------- Создание поста ----------------

def create_post(msgs):
    first = msgs[0]
    pid = "%d%d" % (int(time.time() * 1000), random.randint(100, 999))
    author = first.get("from", {})

    messages = []
    for m in msgs:
        med = extract_media(m)
        messages.append(
            {
                "chat_id": m["chat"]["id"],
                "message_id": m["message_id"],
                "media": {"type": med[0], "file_id": med[1]} if med else None,
                "caption": m.get("caption"),
            }
        )

    post = {
        "id": pid,
        "from_id": author.get("id"),
        "from_name": name_of(first),
        "username": author.get("username"),
        "album": len(msgs) > 1,
        "messages": messages,
        "status": "new",
    }
    save_json(os.path.join(POSTS_DIR, pid + ".json"), post)

    # Отправляем всем админам
    anon = get_settings().get("anon", True)
    if anon:
        who = "🕵 Анонимно"
    else:
        who = "👤 %s%s" % (
            post["from_name"],
            " (@%s)" % post["username"] if post["username"] else "",
        )
    header = "📌 Новый пост #%s\n%s\n➖➖➖➖➖➖➖➖➖" % (pid, who)

    for admin_id in ADMINS:
        try:
            tg("sendMessage", chat_id=admin_id, text=header)
            if post["album"]:
                res = tg(
                    "sendMediaGroup", chat_id=admin_id, media=build_media_group(post)
                )
                if res.get("ok"):
                    tg(
                        "sendMessage",
                        chat_id=admin_id,
                        text="Выбери действие:",
                        reply_markup=post_kb(pid),
                    )
            else:
                m = first
                tg(
                    "copyMessage",
                    chat_id=admin_id,
                    from_chat_id=m["chat"]["id"],
                    message_id=m["message_id"],
                    reply_markup=post_kb(pid),
                )
        except Exception:
            traceback.print_exc()

    # Подтверждение автору
    if post["from_id"]:
        try:
            tg(
                "sendMessage",
                chat_id=post["from_id"],
                text="✅ Пост отправлен на рассмотрение.\nЕсли его одобрят — он появится в канале.",
            )
        except Exception:
            pass


# ---------------- Публикация / отклонение ----------------

def publish_post(post):
    ch = get_channel()
    if not ch:
        return None, "no_channel"
    if post["album"]:
        media = build_media_group(post)
        if not media:
            return None, "empty"
        res = tg("sendMediaGroup", chat_id=ch, media=media)
    else:
        m = post["messages"][0]
        res = tg(
            "copyMessage",
            chat_id=ch,
            from_chat_id=m["chat_id"],
            message_id=m["message_id"],
        )
    return res, None


def answer(cb, text, alert=False):
    tg(
        "answerCallbackQuery",
        callback_query_id=cb["id"],
        text=text,
        show_alert=alert,
    )


# ---------------- Панель админа ----------------

def panel_kb():
    s = get_settings()
    ch = get_channel()
    ch_txt = ("@%s" % ch) if isinstance(ch, str) and ch.startswith("@") else (ch or "не задан")
    return {
        "inline_keyboard": [
            [{"text": "📊 Статистика", "callback_data": "stat"}],
            [{"text": "📢 Канал: %s" % ch_txt, "callback_data": "setch"}],
            [
                {
                    "text": "🕵 Анонимность авторов: %s"
                    % ("ВКЛ" if s.get("anon", True) else "ВЫКЛ"),
                    "callback_data": "anon",
                }
            ],
            [{"text": "♻️ Обновить", "callback_data": "panel"}],
        ]
    }


def show_panel(chat_id, edit_message_id=None):
    s = get_settings()
    ch = get_channel()
    text = "🛠 Панель админа\n\nКанал: %s\nАнонимность авторов: %s" % (
        ch or "не задан",
        "включена" if s.get("anon", True) else "выключена",
    )
    if edit_message_id:
        tg(
            "editMessageText",
            chat_id=chat_id,
            message_id=edit_message_id,
            text=text,
            reply_markup=panel_kb(),
        )
    else:
        tg(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            reply_markup=panel_kb(),
        )


def stats_text():
    total = new = pub = rej = 0
    for fn in os.listdir(POSTS_DIR):
        if not fn.endswith(".json"):
            continue
        p = load_json(os.path.join(POSTS_DIR, fn), {})
        total += 1
        st = p.get("status", "new")
        if st == "new":
            new += 1
        elif st == "published":
            pub += 1
        elif st == "rejected":
            rej += 1
    return (
        "📊 Статистика\n\n"
        "Всего постов: %d\n"
        "⏳ На рассмотрении: %d\n"
        "✅ Опубликовано: %d\n"
        "❌ Отклонено: %d" % (total, new, pub, rej)
    )


# ---------------- Обработка апдейтов ----------------

pending_channel = {}  # admin_id -> True (ожидаем канал)
media_groups = {}  # media_group_id -> {"msgs": [...], "t": время


def handle_message(msg):
    user = msg.get("from", {})
    uid = user.get("id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    # --- ожидаём ввод канала от админа ---
    if pending_channel.get(uid):
        ch = None
        if text.startswith("@"):
            ch = text.split()[0]
        elif msg.get("forward_from_chat"):
            ch = msg["forward_from_chat"]["id"]
        if ch is None:
            tg(
                "sendMessage",
                chat_id=msg["chat"]["id"],
                text="⚠️ Пришли @username канала или перешли сообщение из канала. /cancel — отмена.",
            )
            return
        res = tg(
            "sendMessage",
            chat_id=ch,
            text="✅ Бот-предложка «Типичный Норильск» подключён к каналу.",
        )
        if res.get("ok"):
            save_json(CHANNEL_FILE, ch)
            del pending_channel[uid]
            tg(
                "sendMessage",
                chat_id=msg["chat"]["id"],
                text="✅ Канал сохранён: %s" % ch,
            )
        else:
            tg(
                "sendMessage",
                chat_id=msg["chat"]["id"],
                text="❌ Не получилось: %s\nПроверь, что бот добавлен в админы канала."
                % res.get("description", ""),
            )
        return

    # --- команды ---
    if text.startswith("/"):
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()

        if cmd == "/start":
            extra = "\n\n🛠 /panel — панель админа" if uid in ADMINS else ""
            tg("sendMessage", chat_id=msg["chat"]["id"], text=WELCOME + extra)
            return

        if cmd == "/id":
            tg(
                "sendMessage",
                chat_id=msg["chat"]["id"],
                text="Твой ID: %d\nID этого чата: %d"
                % (uid, msg["chat"]["id"]),
            )
            return

        if cmd == "/cancel":
            pending_channel.pop(uid, None)
            tg("sendMessage", chat_id=msg["chat"]["id"], text="Отменено.")
            return

        if uid not in ADMINS:
            tg("sendMessage", chat_id=msg["chat"]["id"], text="⛔️ Команда только для админов.")
            return

        if cmd in ("/panel", "/admin"):
            show_panel(msg["chat"]["id"])
            return

        if cmd == "/setchannel":
            pending_channel[uid] = True
            tg(
                "sendMessage",
                chat_id=msg["chat"]["id"],
                text="📢 Пришли @username канала или перешли сюда любое сообщение из канала.\n"
                "Бот должен быть добавлен в админы канала с правом публикации.\n"
                "/cancel — отмена.",
            )
            return

        if cmd == "/stats":
            tg("sendMessage", chat_id=msg["chat"]["id"], text=stats_text())
            return

        tg("sendMessage", chat_id=msg["chat"]["id"], text="Неизвестная команда.")
        return

    # --- альбом (несколько фото/видео одним постом) ---
    gid = msg.get("media_group_id")
    if gid:
        if gid not in media_groups:
            media_groups[gid] = {"msgs": [], "t": time.time()}
        media_groups[gid]["msgs"].append(msg)
        media_groups[gid]["t"] = time.time()
        return

    # --- обычный пост ---
    create_post([msg])


def flush_group(gid):
    g = media_groups.pop(gid, None)
    if g and g["msgs"]:
        create_post(g["msgs"])


def handle_callback(cb):
    data = cb.get("data", "")
    uid = cb["from"]["id"]
    msg = cb.get("message", {})

    if uid not in ADMINS:
        answer(cb, "⛔️ Только админы", alert=True)
        return

    if data == "panel":
        show_panel(msg["chat"]["id"], edit_message_id=msg["message_id"])
        answer(cb, "")
        return

    if data == "stat":
        answer(cb, "")
        tg("sendMessage", chat_id=msg["chat"]["id"], text=stats_text())
        return

    if data == "anon":
        s = get_settings()
        s["anon"] = not s.get("anon", True)
        save_json(SETTINGS_FILE, s)
        answer(cb, "Анонимность авторов: %s" % ("ВКЛ" if s["anon"] else "ВЫКЛ"))
        show_panel(msg["chat"]["id"], edit_message_id=msg["message_id"])
        return

    if data == "setch":
        answer(cb, "")
        pending_channel[uid] = True
        tg(
            "sendMessage",
            chat_id=msg["chat"]["id"],
            text="📢 Пришли @username канала или перешли сюда любое сообщение из канала.\n"
            "Бот должен быть админом канала.\n/cancel — отмена.",
        )
        return

    if ":" in data:
        action, pid = data.split(":", 1)
        post = load_json(os.path.join(POSTS_DIR, pid + ".json"), None)
        if not post:
            answer(cb, "Пост не найден", alert=True)
            return
        if post.get("status") != "new":
            answer(cb, "Этот пост уже обработан", alert=True)
            return

        if action == "pub":
            res, err = publish_post(post)
            if err == "no_channel":
                answer(cb, "Сначала задай канал: /setchannel", alert=True)
                return
            if not res or not res.get("ok"):
                answer(
                    cb,
                    "Ошибка: %s" % (res or {}).get("description", "?"),
                    alert=True,
                )
                return
            post["status"] = "published"
            save_json(os.path.join(POSTS_DIR, pid + ".json"), post)
            answer(cb, "✅ Опубликовано")
            note = "✅ Пост #%s опубликовал %s" % (pid, admin_name(cb))
            for admin_id in ADMINS:
                try:
                    tg("sendMessage", chat_id=admin_id, text=note)
                except Exception:
                    pass
            if post.get("from_id"):
                try:
                    tg(
                        "sendMessage",
                        chat_id=post["from_id"],
                        text="🎉 Твой пост опубликован в канале!",
                    )
                except Exception:
                    pass
            return

        if action == "rej":
            post["status"] = "rejected"
            save_json(os.path.join(POSTS_DIR, pid + ".json"), post)
            answer(cb, "❌ Отклонено")
            note = "❌ Пост #%s отклонил %s" % (pid, admin_name(cb))
            for admin_id in ADMINS:
                try:
                    tg("sendMessage", chat_id=admin_id, text=note)
                except Exception:
                    pass
            if post.get("from_id"):
                try:
                    tg(
                        "sendMessage",
                        chat_id=post["from_id"],
                        text="К сожалению, твой пост отклонён.",
                    )
                except Exception:
                    pass
            return


def handle_update(upd):
    if "message" in upd:
        handle_message(upd["message"])
    elif "callback_query" in upd:
        handle_callback(upd["callback_query"])


# ---------------- Главный цикл ----------------

def main():
    print("Бот запущен. Ожидание сообщений...")
    offset = None
    while True:
        try:
            res = tg(
                "getUpdates",
                timeout=3,
                offset=offset,
                allowed_updates=["message", "callback_query"],
            )
            if not res.get("ok"):
                print("Ошибка getUpdates:", res.get("description"))
                time.sleep(3)
                continue

            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    handle_update(upd)
                except Exception:
                    traceback.print_exc()

            # Отправляем собранные альбомы, если новых частей нет ~1 сек
            now = time.time()
            for gid in list(media_groups):
                if now - media_groups[gid]["t"] > 1.0:
                    flush_group(gid)

        except KeyboardInterrupt:
            print("Остановлено.")
            break
        except Exception:
            traceback.print_exc()
            time.sleep(3)


if __name__ == "__main__":
    main()
