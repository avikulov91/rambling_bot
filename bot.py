# bot.py
import os
import re
import math
import pandas as pd
from typing import List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# === Токен ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

# === Пути к файлам ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COCKTAILS_FILE = os.path.join(BASE_DIR, "tech_cards_coctail_rambling.xlsx")
ZAGOTOVKI_FILE = os.path.join(BASE_DIR, "tech_cards_zagi.xlsx")
TINCTURES_FILE = os.path.join(BASE_DIR, "tech_cards_tinctures.xlsx")

# === Алиасы ===
try:
    from aliases import ALIASES
except Exception:
    ALIASES = {}


# ---------- Утилиты ----------
def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[\"“”„’']", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def resolve_alias(user_text: str) -> str:
    t = normalize_text(user_text)
    mapped = ALIASES.get(t, t)
    return normalize_text(mapped).replace("_", " ").strip()


# ---------- Загрузка Excel ----------
COL_SYNONYMS = {
    "название": "название",
    "name": "название",
    "ингредиенты": "ингредиенты",
    "ингридиенты": "ингредиенты",
    "состав": "состав",
    "граммовка": "граммовка",
    "посуда": "посуда",
    "метод": "метод",
    "гарниш": "гарниш",
    "приготовление": "приготовление",
    "выход": "выход",
}


def canon_columns(df: pd.DataFrame) -> pd.DataFrame:
    ren = {}
    for c in df.columns:
        key = normalize_text(str(c))
        ren[c] = COL_SYNONYMS.get(key, key)
    return df.rename(columns=ren)


def load_table(path: str, kind: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = canon_columns(df).ffill()

    # если нет "название", создаём её из первой колонки
    if "название" not in df.columns:
        df.insert(0, "название", df.iloc[:, 0].astype(str))

    df["название"] = df["название"].astype(str).apply(normalize_text)
    print(f"✅ Загружено {kind}: {df['название'].nunique()} уникальных имён")
    return df


# ---------- Загрузка данных ----------
cocktails_df = load_table(COCKTAILS_FILE, "коктейлей")
zagi_df      = load_table(ZAGOTOVKI_FILE, "заготовок")
tinct_df     = load_table(TINCTURES_FILE, "настоек")

print(f"✅ Загружено коктейлей: {cocktails_df['название'].nunique()}")
print(f"✅ Загружено заготовок: {zagi_df['название'].nunique()}")
print(f"✅ Загружено настоек: {tinct_df['название'].nunique()}")

# 👇 Дополнительно выводим список колонок
print("📌 Колонки в таблице коктейлей:", cocktails_df.columns.tolist())
print("📌 Колонки в таблице заготовок:", zagi_df.columns.tolist())
print("📌 Колонки в таблице настоек:", tinct_df.columns.tolist())


# ---------- Форматтеры ----------
def format_cocktail(name: str) -> str:
    g = cocktails_df[cocktails_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл коктейль."
    text = f"🍸 *{name.title()}*\n\n"
    if "посуда" in g: text += f"🥃 Посуда: {g['посуда'].iloc[0]}\n"
    if "метод" in g: text += f"🛠 Метод: {g['метод'].iloc[0]}\n"
    if "гарниш" in g: text += f"🌿 Гарниш: {g['гарниш'].iloc[0]}\n\n"
    if "состав" in g and "граммовка" in g:
        for _, r in g.iterrows():
            text += f"— {r['состав']} — {r['граммовка']}\n"
    return text


def format_zagotovka(name: str) -> str:
    g = zagi_df[zagi_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл заготовку."
    text = f"🧪 *{name.title()}*\n\n"
    if "ингредиенты" in g and "граммовка" in g:
        for _, r in g.iterrows():
            text += f"— {r['ингредиенты']} — {r['граммовка']}\n"
    if "приготовление" in g: text += f"\n🛠 Метод: {g['приготовление'].iloc[0]}"
    if "выход" in g: text += f"\n📦 Выход: {g['выход'].iloc[0]}"
    return text


def format_tincture(name: str) -> str:
    g = tinct_df[tinct_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл настойку."
    text = f"🧪 *{name.title()}*\n\n"
    if "ингредиенты" in g and "граммовка" in g:
        for _, r in g.iterrows():
            text += f"— {r['ингредиенты']} — {r['граммовка']}\n"
    if "метод" in g: text += f"\n🛠 Метод: {g['метод'].iloc[0]}"
    return text


# ---------- Хендлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍸 Коктейли", callback_data="list_cocktails")],
        [InlineKeyboardButton("🧪 Заготовки", callback_data="list_zagi")],
        [InlineKeyboardButton("🧪 Настойки", callback_data="list_tinct")],
    ]
    await update.message.reply_text("👋 Привет! Выбери категорию:", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = resolve_alias(update.message.text)

    if query in cocktail_names:
        await update.message.reply_text(format_cocktail(query), parse_mode="Markdown")
    elif query in zagi_names:
        await update.message.reply_text(format_zagotovka(query), parse_mode="Markdown")
    elif query in tinct_names:
        await update.message.reply_text(format_tincture(query), parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Не нашёл. Попробуй другое название.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "list_cocktails":
        names = sorted(cocktail_names)
        kb = [[InlineKeyboardButton(n.title(), callback_data=f"cocktail_{n}")] for n in names[:20]]
        await query.message.reply_text("🍸 Выбери коктейль:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == "list_zagi":
        names = sorted(zagi_names)
        kb = [[InlineKeyboardButton(n.title(), callback_data=f"zagi_{n}")] for n in names[:20]]
        await query.message.reply_text("🧪 Выбери заготовку:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == "list_tinct":
        names = sorted(tinct_names)
        kb = [[InlineKeyboardButton(n.title(), callback_data=f"tinct_{n}")] for n in names[:20]]
        await query.message.reply_text("🧪 Выбери настойку:", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data.startswith("cocktail_"):
        name = query.data.replace("cocktail_", "")
        await query.message.reply_text(format_cocktail(name), parse_mode="Markdown")
    elif query.data.startswith("zagi_"):
        name = query.data.replace("zagi_", "")
        await query.message.reply_text(format_zagotovka(name), parse_mode="Markdown")
    elif query.data.startswith("tinct_"):
        name = query.data.replace("tinct_", "")
        await query.message.reply_text(format_tincture(name), parse_mode="Markdown")


# ---------- Запуск ----------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()


if __name__ == "__main__":
    main()
