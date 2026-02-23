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
def search_products(query: str):
    # Временная заглушка. Потом заменим на парсинг/API.
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3"},
    ]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает 🚀")
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    low = text.lower()

    if low.startswith("найди"):
        query = text[5:].strip()
        if not query:
            await update.message.reply_text("Напиши так: найди iPhone 15")
            return
        items = search_products(query)

message = "Нашёл:\n\n"
for i, item in enumerate(items, start=1):
    message += f"{i}. {item['title']} — {item['price']} ₽\n"

message += "\nНапиши номер, чтобы выбрать."
await update.message.reply_text(message)

    elif low.startswith("следи"):
        query = text[5:].strip()
        if not query:
            await update.message.reply_text("Напиши так: следи iPhone 15 до 85к")
            return
        await update.message.reply_text(f"Ок. Буду следить за: {query}")
# test preview
    else:
        await update.message.reply_text("Я понимаю:\n1) найди ...\n2) следи ...")
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
tg_app.add_handler(CommandHandler("start", start))


@api.on_event("startup")
async def on_startup():
    # Важно: инициализация PTB приложения
    await tg_app.initialize()
    await tg_app.start()

    # Render даст тебе публичный URL сервиса. Его положим в WEBHOOK_URL.
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        # Не падаем, но предупреждаем в логах.
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
    # Проверка секрета (Telegram шлёт заголовок, если ты указал secret_token)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
