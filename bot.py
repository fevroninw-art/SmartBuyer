import os
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

tg_app = Application.builder().token(BOT_TOKEN).build()
api = FastAPI()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает 🚀")


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
