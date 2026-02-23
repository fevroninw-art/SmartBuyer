import os
import asyncio
from fastapi import FastAPI, Request, HTTPException

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from parser import parse_follow


# ---- ENV ----
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # например: https://xxx.onrender.com/webhook
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "90"))  # 60-120 норм, по умолчанию 90

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# ---- APP ----
tg_app = Application.builder().token(BOT_TOKEN).build()
api = FastAPI()


# ---- STORAGE (in-memory) ----
# tracked_items = { user_id: [ {"query": str, "limit": int}, ... ] }
tracked_items: dict[int, list[dict]] = {}

# чтобы не спамить: уведомили по (user_id, query_lower, limit)
notified: set[tuple[int, str, int]] = set()

checker_task: asyncio.Task | None = None


# ---- SEARCH (stub) ----
def search_products(query: str):
    # Заглушка. Потом сюда подключим OpenClaw / реальные магазины.
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3"},
    ]


def get_best_offer(query: str) -> dict | None:
    items = search_products(query)
    if not items:
        return None
    return min(items, key=lambda x: x.get("price", 10**18))


# ---- COMMANDS ----
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SmartBuyer ✅\n\n"
        "Команды:\n"
        "• найди iPhone 15\n"
        "• следи айфон до 90000\n"
        "• /list — мои отслеживания\n"
        "• /stop 1 — удалить отслеживание по номеру\n\n"
        f"Проверяю каждые {CHECK_INTERVAL} сек."
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = tracked_items.get(user_id, [])

    if not items:
        await update.message.reply_text("У тебя пока нет отслеживаний. Пример: следи айфон до 90000")
        return

    msg = "Твои отслеживания:\n\n"
    for i, it in enumerate(items, start=1):
        msg += f"{i}) {it['query']} — лимит {it['limit']} ₽\n"
    msg += "\nУдалить: /stop 1"
    await update.message.reply_text(msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = tracked_items.get(user_id, [])

    if not items:
        await update.message.reply_text("Нечего удалять — отслеживаний нет. /list")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Напиши так: /stop 1")
        return

    idx = int(context.args[0]) - 1
    if idx < 0 or idx >= len(items):
        await update.message.reply_text(f"Номер должен быть от 1 до {len(items)}")
        return

    removed = items.pop(idx)
    tracked_items[user_id] = items

    # почистим notified по этому правилу
    notified.discard((user_id, removed["query"].lower(), int(removed["limit"])))

    await update.message.reply_text(f"Удалил ✅\n{removed['query']} — лимит {removed['limit']} ₽")


# ---- TEXT HANDLER ----
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    low = text.lower()
    user_id = update.effective_user.id

    # 1) выбор по номеру после "найди"
    if text.isdigit():
        items = context.user_data.get("last_items")
        if not items:
            await update.message.reply_text("Сначала напиши: найди iPhone 15")
            return

        idx = int(text) - 1
        if idx < 0 or idx >= len(items):
            await update.message.reply_text(f"Номер должен быть от 1 до {len(items)}")
            return

        item = items[idx]
        await update.message.reply_text(
            f"Выбрано: {item['title']}\n"
            f"Цена: {item['price']} ₽\n"
            f"Ссылка: {item['url']}"
        )
        return

    # 2) "найди ..."
    if low.startswith("найди"):
        query = text[5:].strip()
        if not query:
            await update.message.reply_text("Напиши так: найди iPhone 15")
            return

        items = search_products(query)
        context.user_data["last_items"] = items

        msg = "Нашёл:\n\n"
        for i, item in enumerate(items, start=1):
            msg += f"{i}. {item['title']} — {item['price']} ₽\n"
        msg += "\nНапиши номер (1/2/3), чтобы выбрать."
        await update.message.reply_text(msg)
        return

    # 3) "следи ..."
    if low.startswith("следи"):
        tail = text[5:].strip()  # всё после "следи"
        parsed = parse_follow(tail)
        if not parsed:
            await update.message.reply_text("Напиши так: следи айфон до 90000")
            return

        query, limit = parsed

        tracked_items.setdefault(user_id, []).append({"query": query, "limit": int(limit)})
        notified.discard((user_id, query.lower(), int(limit)))

        await update.message.reply_text(
            "Добавил отслеживание ✅\n"
            f"Товар: {query}\n"
            f"Лимит: {limit} ₽\n"
            f"Проверяю каждые {CHECK_INTERVAL} сек.\n"
            "Список: /list"
        )
        return

    await update.message.reply_text(
        "Я понимаю:\n"
        "• найди iPhone 15\n"
        "• следи айфон до 90000\n"
        "• /list\n"
        "• /stop 1"
    )


# ---- BACKGROUND CHECKER ----
async def checker_loop():
    while True:
        try:
            snapshot = {uid: list(items) for uid, items in tracked_items.items()}

            for uid, items in snapshot.items():
                for it in items:
                    query = str(it["query"])
                    limit = int(it["limit"])
                    key = (uid, query.lower(), limit)

                    if key in notified:
                        continue

                    best = get_best_offer(query)
                    if not best:
                        continue

                    price = int(best.get("price", 10**18))
                    if price <= limit:
                        await tg_app.bot.send_message(
                            chat_id=uid,
                            text=(
                                "🔥 Цена ниже лимита!\n"
                                f"Товар: {query}\n"
                                f"Найдено: {best['title']}\n"
                                f"Цена: {price} ₽ (лимит {limit} ₽)\n"
                                f"Ссылка: {best['url']}"
                            ),
                        )
                        notified.add(key)

        except Exception as e:
            print("checker_loop error:", repr(e))

        await asyncio.sleep(CHECK_INTERVAL)


# ---- HANDLERS ----
tg_app.add_handler(CommandHandler("start", cmd_start))
tg_app.add_handler(CommandHandler("list", cmd_list))
tg_app.add_handler(CommandHandler("stop", cmd_stop))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))


# ---- FASTAPI LIFECYCLE ----
@api.on_event("startup")
async def on_startup():
    global checker_task

    await tg_app.initialize()
    await tg_app.start()

    if WEBHOOK_URL:
        await tg_app.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
        )
        print(f"Webhook set to: {WEBHOOK_URL}")
    else:
        print("WARNING: WEBHOOK_URL is not set, webhook will not be registered")

    if checker_task is None:
        checker_task = asyncio.create_task(checker_loop())
        print(f"Checker started. Interval={CHECK_INTERVAL}s")


@api.on_event("shutdown")
async def on_shutdown():
    global checker_task

    if checker_task is not None:
        checker_task.cancel()
        checker_task = None

    await tg_app.stop()
    await tg_app.shutdown()


@api.post("/webhook")
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
