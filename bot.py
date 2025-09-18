import os
import pandas as pd
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from aliases import ALIASES

# === Настройки ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

# Пути к файлам (для сервера Render и GitHub)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COCKTAILS_FILE = os.path.join(BASE_DIR, "tech_cards_coctail_rambling.xlsx")
ZAGOTOVKI_FILE = os.path.join(BASE_DIR, "tech_cards_zagi.xlsx")
TINCTURES_FILE = os.path.join(BASE_DIR, "tech_cards_tinctures.xlsx")

# Flask-приложение
app = Flask(__name__)

# Создаём Application (без polling)
application = Application.builder().token(TOKEN).build()


# === Функции загрузки Excel ===
def load_excel(file, mode="cocktail"):
    df = pd.read_excel(file)
    df = df.ffill()  # заполняем пустые ячейки
    df.columns = df.columns.str.strip()
    if "Название" in df.columns:
        df["Название"] = df["Название"].astype(str).str.strip().str.lower()
    return df


cocktails_df = load_excel(COCKTAILS_FILE, "cocktail")
zagi_df = load_excel(ZAGOTOVKI_FILE, "zagi")
tinctures_df = load_excel(TINCTURES_FILE, "tinctures")

print(f"✅ Загружено коктейлей: {cocktails_df['Название'].nunique()}")
print(f"✅ Загружено заготовок: {zagi_df['Название'].nunique()}")
print(f"✅ Загружено настоек: {tinctures_df['Название'].nunique()}")


# === Хендлеры ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍸 Коктейли", callback_data="show_cocktails")],
        [InlineKeyboardButton("🧪 Заготовки", callback_data="show_zagi")],
        [InlineKeyboardButton("🧪 Настойки", callback_data="show_tinctures")],
    ]
    await update.message.reply_text(
        "👋 Привет! Я Rambling-бот.\nВыбери категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    key = ALIASES.get(text, text)

    # === Коктейли ===
    if key in cocktails_df["Название"].values:
        row = cocktails_df[cocktails_df["Название"] == key].iloc[0]
        reply = f"🍸 *{row['Название'].title()}*\n\n"
        reply += f"Посуда: {row['посуда']}\nМетод: {row['метод']}\nГарниш: {row['гарниш']}\n\n"
        ingredients = cocktails_df[cocktails_df["Название"] == key][["Состав", "граммовка"]]
        for _, ing in ingredients.iterrows():
            reply += f"- {ing['Состав']} — {ing['граммовка']}\n"

        keyboard = [
            [
                InlineKeyboardButton("📦 Премикс 500 мл", callback_data=f"premix_500_{key}"),
                InlineKeyboardButton("📦 Премикс 700 мл", callback_data=f"premix_700_{key}"),
                InlineKeyboardButton("📦 Премикс 1000 мл", callback_data=f"premix_1000_{key}"),
            ]
        ]
        await update.message.reply_text(reply, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # === Заготовки ===
    if key in zagi_df["Название"].values:
        row = zagi_df[zagi_df["Название"] == key]
        reply = f"🧪 *{key.title()}*\n\n"
        for _, r in row.iterrows():
            reply += f"- {r['ингридиенты']} — {r['граммовка']}\n"
        reply += f"\nМетод: {row.iloc[0]['приготовление']}\nВыход: {row.iloc[0]['выход']}"
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    # === Настойки ===
    if key in tinctures_df["Название"].values:
        row = tinctures_df[tinctures_df["Название"] == key]
        reply = f"🧪 *{key.title()}*\n\n"
        for _, r in row.iterrows():
            reply += f"- {r['ингридиенты']} — {r['граммовка']}\n"
        reply += f"\nМетод: {row.iloc[0]['метод']}"
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    await update.message.reply_text("❌ Ничего не найдено. Попробуй ещё раз.")


# === Callback ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "show_cocktails":
        names = cocktails_df["Название"].unique()
        keyboard = [[InlineKeyboardButton(n.title(), callback_data=f"cocktail_{n}")] for n in names[:20]]
        await query.message.reply_text("🍸 Выбери коктейль:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "show_zagi":
        names = zagi_df["Название"].unique()
        keyboard = [[InlineKeyboardButton(n.title(), callback_data=f"zagi_{n}")] for n in names[:20]]
        await query.message.reply_text("🧪 Выбери заготовку:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "show_tinctures":
        names = tinctures_df["Название"].unique()
        keyboard = [[InlineKeyboardButton(n.title(), callback_data=f"tinct_{n}")] for n in names[:20]]
        await query.message.reply_text("🧪 Выбери настойку:", reply_markup=InlineKeyboardMarkup(keyboard))


# === Регистрируем хендлеры ===
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_callback))


# === Flask endpoint для Telegram ===
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


# Установка webhook вручную
@app.route("/setwebhook")
def set_webhook():
    url = "https://rambling-bot.onrender.com/webhook"
    application.bot.set_webhook(url)
    return f"Webhook установлен: {url}", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def make_premix(name: str, data: dict, volume: int) -> str:
    text = f"📦 *Премикс {name.title()}* ({volume} мл)\n\n"
    ingredients = []
    total = sum(
        float(amt.replace("ml", "").replace("мл", "").strip())
        for ing, amt in data["ingredients"]
        if "ml" in amt or "мл" in amt
    )
    for ing, amt in data["ingredients"]:
        if any(x in ing.lower() for x in ["сок", "juice", "sparkling", "сода", "soda", "cream", "сливк"]):
            continue
        try:
            base_amt = float(amt.replace("ml", "").replace("мл", "").strip())
            scaled = int((base_amt / total) * volume)
            scaled = scaled - (scaled % 10)  # округление вниз до 10
            ingredients.append((ing, f"{scaled} мл"))
        except:
            pass
    for ing, amt in ingredients:
        text += f"— {ing} — {amt}\n"
    return text


# === Хэндлеры ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Напиши название коктейля или слово *Заготовки* / *Настойки*.", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    key = normalize_name(query)

    if key in cocktails:
        data = cocktails[key]
        text = format_cocktail(key, data)
        keyboard = [
            [
                InlineKeyboardButton("📦 500 мл", callback_data=f"premix|{key}|500"),
                InlineKeyboardButton("📦 700 мл", callback_data=f"premix|{key}|700"),
                InlineKeyboardButton("📦 1000 мл", callback_data=f"premix|{key}|1000"),
            ]
        ]
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query == "заготовки":
        keyboard = [[InlineKeyboardButton(name.title(), callback_data=f"zagotovka|{name}")] for name in zagotovki.keys()]
        await update.message.reply_text("🧪 *Список заготовок:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif key in zagotovki:
        data = zagotovki[key]
        text = format_zagotovka(key, data)
        await update.message.reply_text(text, parse_mode="Markdown")
    elif query == "настойки":
        keyboard = [[InlineKeyboardButton(name.title(), callback_data=f"tincture|{name}")] for name in tinctures.keys()]
        await update.message.reply_text("🧪 *Список настоек:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif key in tinctures:
        data = tinctures[key]
        text = format_tincture(key, data)
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Не нашёл. Попробуй другое название.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")

    if data[0] == "premix":
        name, volume = data[1], int(data[2])
        text = make_premix(name, cocktails[name], volume)
        await query.message.reply_text(text, parse_mode="Markdown")
    elif data[0] == "zagotovka":
        name = data[1]
        text = format_zagotovka(name, zagotovki[name])
        await query.message.reply_text(text, parse_mode="Markdown")
    elif data[0] == "tincture":
        name = data[1]
        text = format_tincture(name, tinctures[name])
        await query.message.reply_text(text, parse_mode="Markdown")


# === Основной запуск ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print(f"✅ Загружено коктейлей: {len(cocktails)}")
    print(f"✅ Загружено заготовок: {len(zagotovki)}")
    print(f"✅ Загружено настоек: {len(tinctures)}")
    print("🤖 Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
