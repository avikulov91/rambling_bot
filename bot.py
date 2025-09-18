import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import os

# === Настройки ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

# Пути к файлам
BASE_DIR = "/Users/ekaterinaigosina/Documents/rambling_assistant_bot"
COCKTAILS_FILE = os.path.join(BASE_DIR, "tech_cards_coctail_rambling.xlsx")
ZAGOTOVKI_FILE = os.path.join(BASE_DIR, "tech_cards_zagi.xlsx")
TINCTURES_FILE = os.path.join(BASE_DIR, "tech_cards_tinctures.xlsx")

# Загружаем алиасы
from aliases import ALIASES


# === Загружаем коктейли ===
cocktails_df = pd.read_excel(COCKTAILS_FILE)
cocktails = {}
current_name = None
for _, row in cocktails_df.iterrows():
    name = str(row["Название"]).strip().lower()
    if name and name != "nan":
        current_name = name
        if current_name not in cocktails:
            cocktails[current_name] = {
                "glass": str(row["посуда"]).strip() if not pd.isna(row["посуда"]) else "",
                "method": str(row["метод"]).strip() if not pd.isna(row["метод"]) else "",
                "garnish": str(row["гарниш"]).strip() if not pd.isna(row["гарниш"]) else "",
                "ingredients": []
            }
    if current_name:
        ingredient = str(row["Состав"]).strip()
        amount = str(row["граммовка"]).strip()
        if ingredient and ingredient != "nan":
            cocktails[current_name]["ingredients"].append((ingredient, amount))


# === Загружаем заготовки ===
zagotovki_df = pd.read_excel(ZAGOTOVKI_FILE)
zagotovki = {}
current_name = None
for _, row in zagotovki_df.iterrows():
    name = str(row["название"]).strip().lower()
    if name and name != "nan":
        current_name = name
        if current_name not in zagotovki:
            zagotovki[current_name] = {
                "ingredients": [],
                "method": str(row["приготовление"]).strip() if not pd.isna(row["приготовление"]) else "",
                "output": str(row["выход"]).strip() if not pd.isna(row["выход"]) else ""
            }
    if current_name:
        ingredient = str(row["ингридиенты"]).strip()
        amount = str(row["граммовка"]).strip()
        if ingredient and ingredient != "nan":
            zagotovki[current_name]["ingredients"].append((ingredient, amount))


# === Загружаем настойки ===
tinctures_df = pd.read_excel(TINCTURES_FILE)
tinctures = {}
current_name = None
for _, row in tinctures_df.iterrows():
    name = str(row["название"]).strip().lower()
    if name and name != "nan":
        current_name = name
        if current_name not in tinctures:
            tinctures[current_name] = {
                "ingredients": [],
                "method": str(row["метод"]).strip() if not pd.isna(row["метод"]) else ""
            }
    if current_name:
        ingredient = str(row["ингридиенты"]).strip()
        amount = str(row["граммовка"]).strip()
        if ingredient and ingredient != "nan":
            tinctures[current_name]["ingredients"].append((ingredient, amount))


# === Вспомогательные функции ===
def normalize_name(name: str) -> str:
    name = name.strip().lower()
    return ALIASES.get(name, name)

def format_cocktail(name: str, data: dict) -> str:
    text = f"🍸 *{name.title()}*\n"
    text += f"🥂 Посуда: {data['glass']}\n"
    text += f"⚒️ Метод: {data['method']}\n"
    text += f"🍋 Гарниш: {data['garnish']}\n\n"
    text += "📋 *Ингредиенты:*\n"
    for ing, amt in data["ingredients"]:
        text += f"— {ing} — {amt}\n"
    return text

def format_zagotovka(name: str, data: dict) -> str:
    text = f"🧪 *{name.title()}*\n\n"
    text += "📋 *Ингредиенты:*\n"
    for ing, amt in data["ingredients"]:
        text += f"— {ing} — {amt}\n"
    text += f"\n⚒️ Приготовление: {data['method']}\n"
    text += f"📦 Выход: {data['output']}\n"
    return text

def format_tincture(name: str, data: dict) -> str:
    text = f"🧪 *{name.title()}*\n\n"
    text += "📋 *Ингредиенты:*\n"
    for ing, amt in data["ingredients"]:
        text += f"— {ing} — {amt}\n"
    text += f"\n⚒️ Метод: {data['method']}\n"
    return text

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
