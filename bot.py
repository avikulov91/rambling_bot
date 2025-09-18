import os
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from aliases import ALIASES

# === Конфигурация ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COCKTAILS_FILE = os.path.join(BASE_DIR, "tech_cards_coctail_rambling.xlsx")
ZAGOTOVKI_FILE = os.path.join(BASE_DIR, "tech_cards_zagi.xlsx")
TINCTURES_FILE = os.path.join(BASE_DIR, "tech_cards_tinctures.xlsx")

# === Загрузка данных ===
def load_cocktails():
    df = pd.read_excel(COCKTAILS_FILE)
    cocktails = {}
    for name in df["Название"].dropna().unique():
        subset = df[df["Название"] == name]
        cocktails[name.strip().lower().replace(" ", "_")] = {
            "name": name.strip(),
            "glass": str(subset["посуда"].iloc[0]),
            "method": str(subset["метод"].iloc[0]),
            "garnish": str(subset["гарниш"].iloc[0]),
            "ingredients": [
                {"ingredient": str(row["Состав"]), "amount": str(row["граммовка"])}
                for _, row in subset.iterrows()
                if pd.notna(row["Состав"]) and pd.notna(row["граммовка"])
            ],
        }
    return cocktails

def load_zagot():
    df = pd.read_excel(ZAGOTOVKI_FILE)
    zagot = {}
    for name in df["название"].dropna().unique():
        subset = df[df["название"] == name]
        zagot[name.strip().lower().replace(" ", "_")] = {
            "name": name.strip(),
            "ingredients": [
                {"ingredient": str(row["ингридиенты"]), "amount": str(row["граммовка"])}
                for _, row in subset.iterrows()
                if pd.notna(row["ингридиенты"])
            ],
            "method": str(subset["приготовление"].iloc[0]) if "приготовление" in subset else "",
            "yield": str(subset["выход"].iloc[0]) if "выход" in subset else "",
        }
    return zagot

def load_tinctures():
    df = pd.read_excel(TINCTURES_FILE)
    tinctures = {}
    for name in df["название"].dropna().unique():
        subset = df[df["название"] == name]
        tinctures[name.strip().lower().replace(" ", "_")] = {
            "name": name.strip(),
            "ingredients": [
                {"ingredient": str(row["ингридиенты"]), "amount": str(row["граммовка"])}
                for _, row in subset.iterrows()
                if pd.notna(row["ингридиенты"])
            ],
            "method": str(subset["метод"].iloc[0]) if "метод" in subset else "",
        }
    return tinctures

COCKTAILS = load_cocktails()
ZAGOTOVKI = load_zagot()
TINCTURES = load_tinctures()

# === Алиасы ===
def resolve_alias(query: str):
    q = query.strip().lower()
    return ALIASES.get(q, q.replace(" ", "_"))

# === Премиксы ===
EXCLUDE_FROM_PREMIX = ["juice", "сок", "cream", "сливки", "milk", "молоко", "sparkling", "сода", "water", "wine"]

def make_premix(ingredients, bottle_size):
    premix = []
    for item in ingredients:
        ing = item["ingredient"].lower()
        if any(ex in ing for ex in EXCLUDE_FROM_PREMIX):
            continue
        try:
            amount_val = float(item["amount"].split()[0])
            unit = item["amount"].split()[1]
            scaled = (amount_val / 100) * bottle_size
            scaled = int(scaled // 10 * 10)
            premix.append(f"{item['ingredient']}: {scaled} {unit}")
        except:
            continue
    return premix

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Пиши название коктейля, заготовки или настойки.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    key = resolve_alias(query)

    # коктейли
    if key in COCKTAILS:
        c = COCKTAILS[key]
        text = f"🍸 *{c['name']}*\n🥃 {c['glass']}\n⚙️ {c['method']}\n🍊 {c['garnish']}\n\n"
        for ing in c["ingredients"]:
            text += f"- {ing['ingredient']} — {ing['amount']}\n"
        keyboard = [
            [InlineKeyboardButton("500 мл", callback_data=f"premix_{key}_500")],
            [InlineKeyboardButton("700 мл", callback_data=f"premix_{key}_700")],
            [InlineKeyboardButton("1000 мл", callback_data=f"premix_{key}_1000")],
        ]
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # заготовки
    if key in ZAGOTOVKI:
        z = ZAGOTOVKI[key]
        text = f"🧪 *{z['name']}*\n\n"
        for ing in z["ingredients"]:
            text += f"- {ing['ingredient']} — {ing['amount']}\n"
        text += f"\n⚙️ {z['method']}\n📦 Выход: {z['yield']}"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    # настойки
    if key in TINCTURES:
        t = TINCTURES[key]
        text = f"🧪 *{t['name']}*\n\n"
        for ing in t["ingredients"]:
            text += f"- {ing['ingredient']} — {ing['amount']}\n"
        text += f"\n⚙️ {t['method']}"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    await update.message.reply_text("❓ Не нашёл. Попробуй другое название.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("premix_"):
        _, key, size = data.split("_")
        c = COCKTAILS.get(key)
        if not c:
            await query.edit_message_text("⚠️ Ошибка: коктейль не найден.")
            return
        premix = make_premix(c["ingredients"], int(size))
        if not premix:
            await query.edit_message_text("⚠️ В премикс ничего не входит.")
            return
        text = f"🥤 Премикс для *{c['name']}* ({size} мл):\n\n"
        text += "\n".join(premix)
        await query.edit_message_text(text, parse_mode="Markdown")

# === Запуск ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()
