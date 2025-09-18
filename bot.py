import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
from aliases import ALIASES

# === Пути к файлам ===
COCKTAILS_FILE = "tech_cards_coctail_rambling.xlsx"
ZAGOTOVKI_FILE = "tech_cards_zagi.xlsx"
TINCTURES_FILE = "tech_cards_tinctures.xlsx"

# === Токен бота ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

# === Исключения для премиксов ===
EXCLUDE_FROM_PREMIX = ["сок", "juice", "sparkling", "игрист", "сода", "soda", "сливки", "cream"]

# === Загрузка Excel с нормализацией заголовков ===
def load_excel(file_path, mode="cocktail"):
    df = pd.read_excel(file_path, sheet_name=0)
    df.columns = df.columns.str.strip().str.lower()  # нормализуем заголовки
    df = df.ffill()  # заполняем пустые названия вниз
    if mode == "cocktail":
        return df[["название", "посуда", "метод", "гарниш", "состав", "граммовка"]]
    elif mode == "zagi":
        return df[["название", "ингридиенты", "граммовка", "приготовление", "выход"]]
    elif mode == "tincture":
        return df[["название", "ингридиенты", "граммовка", "метод"]]
    return df

cocktails_df = load_excel(COCKTAILS_FILE, mode="cocktail")
zagi_df = load_excel(ZAGOTOVKI_FILE, mode="zagi")
tinctures_df = load_excel(TINCTURES_FILE, mode="tincture")

print(f"✅ Загружено коктейлей: {cocktails_df['название'].nunique()}")
print(f"✅ Загружено заготовок: {zagi_df['название'].nunique()}")
print(f"✅ Загружено настоек: {tinctures_df['название'].nunique()}")

# === Алиасы ===
def resolve_alias(name):
    name = name.strip().lower()
    return ALIASES.get(name, name)

# === Форматирование коктейля ===
def format_cocktail(name):
    df = cocktails_df[cocktails_df["название"].str.lower() == name]
    if df.empty:
        return "❌ Коктейль не найден."
    row = df.iloc[0]
    text = f"🍸 *{row['название'].title()}*\n\n"
    text += f"🥃 Посуда: {row['посуда']}\n"
    text += f"⚙️ Метод: {row['метод']}\n"
    text += f"🍊 Гарниш: {row['гарниш']}\n\n"
    text += "🧾 Ингредиенты:\n"
    for _, r in df.iterrows():
        text += f"- {r['состав']} — {r['граммовка']}\n"
    return text

# === Премиксы ===
def format_premix(name, volume):
    df = cocktails_df[cocktails_df["название"].str.lower() == name]
    if df.empty:
        return "❌ Коктейль не найден."
    text = f"🥤 Премикс для *{df.iloc[0]['название'].title()}* ({volume} мл):\n\n"
    for _, r in df.iterrows():
        ingr = str(r["состав"]).lower()
        if any(bad in ingr for bad in EXCLUDE_FROM_PREMIX):
            continue
        try:
            amount = float(str(r["граммовка"]).split()[0])
        except:
            continue
        scaled = (amount / 100) * volume
        scaled = int(scaled // 10 * 10)
        text += f"- {r['состав']} — {scaled} мл\n"
    return text

# === Форматирование заготовок ===
def format_zagot(name):
    df = zagi_df[zagi_df["название"].str.lower() == name]
    if df.empty:
        return "❌ Заготовка не найдена."
    row = df.iloc[0]
    text = f"🧪 *{row['название'].title()}*\n\n"
    text += "🧾 Ингредиенты:\n"
    for _, r in df.iterrows():
        text += f"- {r['ингридиенты']} — {r['граммовка']}\n"
    text += f"\n⚙️ Приготовление: {row['приготовление']}\n"
    text += f"📦 Выход: {row['выход']}\n"
    return text

# === Форматирование настоек ===
def format_tincture(name):
    df = tinctures_df[tinctures_df["название"].str.lower() == name]
    if df.empty:
        return "❌ Настойка не найдена."
    row = df.iloc[0]
    text = f"🧪 *{row['название'].title()}*\n\n"
    text += "🧾 Ингредиенты:\n"
    for _, r in df.iterrows():
        text += f"- {r['ингридиенты']} — {r['граммовка']}\n"
    text += f"\n⚙️ Метод: {row['метод']}\n"
    return text

# === Хендлеры ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Введи название коктейля, 'заготовки' или 'настойки'.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    resolved = resolve_alias(query)

    if query == "заготовки":
        buttons = [[InlineKeyboardButton(name.title(), callback_data=f"zagi:{name}")]
                   for name in zagi_df["название"].unique()]
        await update.message.reply_text("🧪 Выбери заготовку:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if query == "настойки":
        buttons = [[InlineKeyboardButton(name.title(), callback_data=f"tincture:{name}")]
                   for name in tinctures_df["название"].unique()]
        await update.message.reply_text("🧪 Выбери настойку:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if resolved in cocktails_df["название"].str.lower().values:
        text = format_cocktail(resolved)
        buttons = [
            [InlineKeyboardButton("🥤 500 мл", callback_data=f"premix:{resolved}:500"),
             InlineKeyboardButton("🥤 700 мл", callback_data=f"premix:{resolved}:700"),
             InlineKeyboardButton("🥤 1000 мл", callback_data=f"premix:{resolved}:1000")]
        ]
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        return

    await update.message.reply_text("❌ Не понял запрос. Напиши название коктейля, 'заготовки' или 'настойки'.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    if data[0] == "premix":
        _, name, vol = data
        await query.message.reply_text(format_premix(name, int(vol)), parse_mode="Markdown")
    elif data[0] == "zagi":
        _, name = data
        await query.message.reply_text(format_zagot(name), parse_mode="Markdown")
    elif data[0] == "tincture":
        _, name = data
        await query.message.reply_text(format_tincture(name), parse_mode="Markdown")

# === MAIN ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
