import os
import re
import asyncio
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # например: https://xxx.onrender.com/webhook

# как часто проверять (в секундах). поставь 300 = 5 минут
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

tg_app = Application.builder().token(BOT_TOKEN).build()
api = FastAPI()

# --- Хранилище отслеживаний (в памяти). После перезапуска Render всё сбросится ---
# tracked_items = { user_id: [ {"query": str, "limit": int}, ... ] }
tracked_items: dict[int, list[dict]] = {}

# чтобы не спамить: помечаем, что уже уведомили по этому (user_id, query, limit)
notified: set[tuple[int, str, int]] = set()

# фоновая задача
checker_task: asyncio.Task | None = None


def search_products(query: str):
    # Заглушка (потом заменим на реальные источники)
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3"},
    ]


def get_best_offer(query: str) -> dict | None:
    items = search_products(query)
    if not items:
        return None
    # берём самый дешёвый вариант
    return min(items, key=lambda x: x.get("price", 10**18))


def parse_follow_command(text: str) -> tuple[str, int] | None:
    """
    Примеры:
      "следи айфон до 80000"
      "следи iPhone 15 85000"
      "следи ps5 до 50к"  (50к тоже поймём как 50)
    """
    s = text.strip()

    # забираем хвост после "следи"
    tail = s[5:].strip()
    if not tail:
        return None

    # найдём число (лимит)
    m = re.findall(r"\d+", tail.replace("к", "000").replace("K", "000"))
    if not m:
        return None

    limit = int(m[-1])

    # вычищаем цифры и слово "до"
    query = re.sub(r"\d+", "", tail)
    query = query.replace("до", " ")
    query = " ".join(query.split()).strip()

    if not query:
        return None

    return query, limit


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот работает 🚀\n"
        "Команды:\n"
        "• найди iPhone 15\n"
        "• следи айфон до 80000\n"
        "После 'найди' можно прислать номер (1/2/3), чтобы выбрать."
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    low = text.lower()
    user_id = update.effective_user.id

    # 1) Пользователь прислал номер (выбор из списка)
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

    # 2) Команда "найди ..."
    if low.startswith("найди"):
        query = text[5:].strip()
        if not query:
            await update.message.reply_text("Напиши так: найди iPhone 15")
            return

        items = search_products(query)
        context.user_data["last_items"] = items

        message = "Нашёл:\n\n"
        for i, item in enumerate(items, start=1):
            message += f"{i}. {item['title']} — {item['price']} ₽\n"
        message += "\nНапиши номер (1/2/3), чтобы выбрать."

        await update.message.reply_text(message)
        return

    # 3) Команда "следи ..."
    if low.startswith("следи"):
        parsed = parse_follow_command(text)
        if not parsed:
            await update.message.reply_text("Напиши так: следи айфон до 80000")
            return

        query, limit = parsed

        tracked_items.setdefault(user_id, []).append({"query": query, "limit": limit})

        # снимаем блокировку уведомления (если ранее уже уведомляли по такому же)
        notified.discard((user_id, query.lower(), limit))

        await update.message.reply_text(
            f"Добавил отслеживание ✅\n"
            f"Товар: {query}\n"
            f"Лимит: {limit} ₽\n"
            f"Проверяю каждые {CHECK_INTERVAL} сек."
        )
        return

    # 4) Всё остальное
    await update.message.reply_text(
        "Я понимаю:\n"
        "1) найди ...\n"
        "2) следи ... до 80000\n"
        "3) номер (после найди)"
    )


async def checker_loop():
    # вечный цикл проверки
    while True:
        try:
            # копируем, чтобы не ломаться при изменениях во время итерации
            snapshot = {uid: list(items) for uid, items in tracked_items.items()}

            for uid, items in snapshot.items():
                for it in items:
                    query = it["query"]
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
            # не падаем — просто логируем
            print("checker_loop error:", repr(e))

        await asyncio.sleep(CHECK_INTERVAL)


# --- handlers ---
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))


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

    # запускаем фоновую проверку
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
