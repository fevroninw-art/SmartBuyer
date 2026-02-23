import os
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

tg_app = Application.builder().token(BOT_TOKEN).build()
api = FastAPI()
# Хранилище отслеживаний
# структура:
# {
#   user_id: [
#       {"query": "айфон", "limit": 80000},
#       {"query": "ps5", "limit": 50000}
#   ]
# }
tracked_items = {}

def search_products(query: str):
    # Временная заглушка. Потом заменим на парсинг/API.
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3"},
    ]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает 🚀\nНапиши: найди iPhone 15")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    low = text.lower()

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
            f"Выбрано: {item['title']}\nЦена: {item['price']} ₽\nСсылка: {item['url']}"
        )
        return

    # 2) Команда "найди ..."
    if low.startswith("найди"):
        query = text[5:].strip()
        if not query:
            await update.message.reply_text("Напиши так: найди iPhone 15")
            return

        items = search_products(query)
        context.user_data["last_items"] = items  # сохраняем список для выбора по номеру

        message = "Нашёл:\n\n"
        for i, item in enumerate(items, start=1):
            message += f"{i}. {item['title']} — {item['price']} ₽\n"
        message += "\nНапиши номер (1/2/3), чтобы выбрать."

        await update.message.reply_text(message)
        return

    # 3) Команда "следи ..."
elif low.startswith("следи"):
    user_id = update.effective_user.id
    query_text = text[5:].strip()

    if not query_text:
        await update.message.reply_text("Напиши так: следи айфон до 80000")
        return

    import re
    numbers = re.findall(r"\d+", query_text)

    if not numbers:
        await update.message.reply_text("Укажи лимит цены, например: следи айфон до 80000")
        return

    limit = int(numbers[-1])
    query = re.sub(r"\d+", "", query_text).replace("до", "").strip()

    if user_id not in tracked_items:
        tracked_items[user_id] = []

    tracked_items[user_id].append({
        "query": query,
        "limit": limit
    })

    await update.message.reply_text(
        f"Добавил отслеживание:\nТовар: {query}\nЛимит: {limit} ₽"
    )
    return
# 4) Всё остальное
    else:
        await update.message.reply_text("Я понимаю:\n1) найди ...\n2) следи ...\n3) номер (после найди)")


# Важно: хендлеры добавляем до запуска приложения
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))


@api.on_event("startup")
async def on_startup():
    # Инициализация PTB приложения
    await tg_app.initialize()
    await tg_app.start()

    # Render даст публичный URL сервиса. Его положим в WEBHOOK_URL (например: https://xxx.onrender.com/webhook)
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        print("WARNING: WEBHOOK_URL is not set, webhook will not be registered")
        return

    await tg_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )
    print(f"Webhook set to: {webhook_url}")


@api.on_event("shutdown")
async def on_shutdown():
    await tg_app.stop()
    await tg_app.shutdown()


@api.post("/webhook")
async def telegram_webhook(request: Request):
    # Проверка секрета (Telegram шлёт заголовок, если указан secret_token)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
