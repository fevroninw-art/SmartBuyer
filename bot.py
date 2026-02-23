import os
import re
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

tg_app = Application.builder().token(BOT_TOKEN).build()
api = FastAPI()

# Хранилище отслеживаний (в памяти). После перезапуска Render очистится.
# структура:
# {
#   user_id: [
#       {"query": "айфон", "limit": 80000},
#       {"query": "ps5", "limit": 50000}
#   ]
# }
tracked_items: dict[int, list[dict]] = {}


def search_products(query: str):
    # Временная заглушка. Потом заменим на парсинг/API.
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3"},
    ]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот работает 🚀\n"
        "Команды:\n"
        "• найди iPhone 15\n"
        "• следи айфон до 80000\n"
        "• (после 'найди') можно прислать номер 1/2/3"
    )


def _parse_follow_command(text: str):
    """
    Принимает строку после слова 'следи', например:
      'айфон до 80000'
      'iPhone 15 85000'
    Возвращает (query, limit) или (None, None) если не распарсилось.
    """
    s = text.strip()
    if not s:
        return None, None

    nums = re.findall(r"\d+", s)
    if not nums:
        return None, None

    limit = int(nums[-1])

    # Убираем числа, слово "до" и лишние пробелы
    query = re.sub(r"\d+", " ", s)
    query = re.sub(r"\bдо\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()

    if not query:
        return None, None

    return query, limit


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
        context.user_data["last_items"] = items  # сохраняем список для выбора по номеру

        message = "Нашёл:\n\n"
        for i, item in enumerate(items, start=1):
            message += f"{i}. {item['title']} — {item['price']} ₽\n"
        message += "\nНапиши номер (1/2/3), чтобы выбрать."

        await update.message.reply_text(message)
        return

    # 3) Команда "следи ..."
    if low.startswith("следи"):
        user_id = update.effective_user.id
        payload = text[5:].strip()

        query, limit = _parse_follow_command(payload)
        if query is None or limit is None:
            await update.message.reply_text("Напиши так: следи айфон до 80000")
            return

        tracked_items.setdefault(user_id, []).append({"query": query, "limit": limit})

        await update.message.reply_text(
            f"Добавил отслеживание:\n"
            f"Товар: {query}\n"
            f"Лимит: {limit} ₽"
        )
        return

    # 4) Всё остальное
    await update.message.reply_text(
        "Я понимаю:\n"
        "1) найди ...\n"
        "2) следи ... до <цена>\n"
        "3) номер (после найди)"
    )


# Важно: хендлеры добавляем до запуска приложения
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))


@api.on_event("startup")
async def on_startup():
    await tg_app.initialize()
    await tg_app.start()

    # WEBHOOK_URL должен быть вида: https://<твой-сервис>.onrender.com/webhook
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
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
