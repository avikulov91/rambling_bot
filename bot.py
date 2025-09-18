# bot.py — Flask + Webhook (python-telegram-bot==20.3)
import os
import re
import math
import asyncio
import threading
from typing import List, Tuple, Optional

import pandas as pd
from flask import Flask, request, jsonify
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
except Exception as e:
    print(f"⚠️ Не удалось импортировать aliases.py: {e}")
    ALIASES = {}

# ---------- Утилиты ----------
def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r'[\"“”„’\']', " ", s)
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
    "title": "название",

    "посуда": "посуда",
    "glass": "посуда",

    "метод": "метод",
    "method": "метод",
    "метод приготовления": "метод",
    "приготовление": "приготовление",

    "гарниш": "гарниш",
    "garnish": "гарниш",

    "состав": "состав",
    "ингредиент": "состав",

    "ингредиенты": "ингредиенты",
    "ингридиенты": "ингредиенты",  # опечатка

    "граммовка": "граммовка",
    "amount": "граммовка",

    "выход": "выход",
    "yield": "выход",
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

    # Если нет "название" — берём первую колонку как имя
    if "название" not in df.columns and len(df.columns) > 0:
        df.insert(0, "название", df.iloc[:, 0])

    # Приводим к строкам, чистим
    if "название" in df.columns:
        df["название"] = df["название"].astype(str).apply(normalize_text)
        df = df[~df["название"].isin(["", "название", "name", "title", "none", "nan"])]

    # Остальные текстовые
    for col in df.columns:
        if df[col].dtype == object and col != "граммовка":
            df[col] = df[col].astype(str).apply(normalize_text)
        if col == "граммовка":
            df[col] = df[col].astype(str).str.strip()

    print(f"✅ Загружено {kind}: {df['название'].nunique() if 'название' in df.columns else 0}")
    return df

# ---------- Загружаем данные ----------
cocktails_df = load_table(COCKTAILS_FILE, "коктейлей")
zagi_df      = load_table(ZAGOTOVKI_FILE, "заготовок")
tinct_df     = load_table(TINCTURES_FILE, "настоек")

cocktail_names = sorted(cocktails_df["название"].unique()) if "название" in cocktails_df.columns else []
zagi_names     = sorted(zagi_df["название"].unique()) if "название" in zagi_df.columns else []
tinct_names    = sorted(tinct_df["название"].unique()) if "название" in tinct_df.columns else []

cocktail_names_set = set(cocktail_names)
zagi_names_set     = set(zagi_names)
tinct_names_set    = set(tinct_names)

print("📌 Колонки коктейлей:", cocktails_df.columns.tolist())
print("📌 Колонки заготовок:", zagi_df.columns.tolist())
print("📌 Колонки настоек:", tinct_df.columns.tolist())

# ---------- Форматтеры ----------
def title_cap(s: str) -> str:
    return " ".join(w.capitalize() for w in (s or "").split())

def format_cocktail(name: str) -> str:
    g = cocktails_df[cocktails_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл коктейль."
    lines = [f"🍸 *{title_cap(name)}*", ""]
    if "посуда" in g.columns and pd.notna(g["посуда"].iloc[0]):   lines.append(f"🥃 Посуда: {g['посуда'].iloc[0]}")
    if "метод" in g.columns and pd.notna(g["метод"].iloc[0]):     lines.append(f"🛠 Метод: {g['метод'].iloc[0]}")
    if "гарниш" in g.columns and pd.notna(g["гарниш"].iloc[0]):   lines.append(f"🌿 Гарниш: {g['гарниш'].iloc[0]}")
    lines.append("")
    if "состав" in g.columns and "граммовка" in g.columns:
        for _, r in g.iterrows():
            ing, amt = str(r["состав"]).strip(), str(r["граммовка"]).strip()
            if ing and ing not in ["", "состав"] and amt:
                lines.append(f"— {ing} — {amt}")
    else:
        lines.append("_Нет данных об ингредиентах_")
    return "\n".join(lines)

def format_zagotovka(name: str) -> str:
    g = zagi_df[zagi_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл заготовку."
    lines = [f"🧪 *{title_cap(name)}*", ""]
    if "ингредиенты" in g.columns and "граммовка" in g.columns:
        for _, r in g.iterrows():
            ing, amt = str(r["ингредиенты"]).strip(), str(r["граммовка"]).strip()
            if ing and ing not in ["", "ингредиенты"] and amt:
                lines.append(f"— {ing} — {amt}")
    if "приготовление" in g.columns and pd.notna(g["приготовление"].iloc[0]):
        lines.append("")
        lines.append(f"🧯 Метод: {g['приготовление'].iloc[0]}")
    if "выход" in g.columns and pd.notna(g["выход"].iloc[0]):
        lines.append(f"📦 Выход: {g['выход'].iloc[0]}")
    return "\n".join(lines)

def format_tincture(name: str) -> str:
    g = tinct_df[tinct_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл настойку."
    lines = [f"🧪 *{title_cap(name)}*", ""]
    if "ингредиенты" in g.columns and "граммовка" in g.columns:
        for _, r in g.iterrows():
            ing, amt = str(r["ингредиенты"]).strip(), str(r["граммовка"]).strip()
            if ing and ing not in ["", "ингредиенты"] and amt:
                lines.append(f"— {ing} — {amt}")
    if "метод" in g.columns and pd.notna(g["метод"].iloc[0]):
        lines.append("")
        lines.append(f"🧯 Метод: {g['метод'].iloc[0]}")
    return "\n".join(lines)

# ---------- Премиксы ----------
EXCLUDE_TOKENS = [
    "juice", "сок", "sparkling", "игрист", "soda", "сода", "cola", "кола", "coke", "sprite",
    "tonic", "тоник", "cream", "сливк", "milk", "молоко", "puree", "пюре",
    "top", "дэш", "dash", "barspoon", "бс", "щепотка", "pinch", "pt",
]
ALLOW_CREAM_LIQUEUR = ["baileys", "irish cream", "сливочн ликер", "сливочн ликёр", "liqueur", "ликер", "ликёр"]

def is_cream_liqueur(ing: str) -> bool:
    s = normalize_text(ing)
    if "baileys" in s or "irish cream" in s:
        return True
    if "сливочн" in s and any(x in s for x in ["ликер", "ликёр", "liqueur"]):
        return True
    return False

def parse_ml(s: str) -> Optional[float]:
    if s is None:
        return None
    t = str(s).strip().lower()
    if any(x in t for x in ["top", "дэш", "dash", "barspoon", "pt", "щепотка", "pinch"]):
        return None
    m = re.search(r"(\d+([.,]\d+)?)\s*(ml|мл)?\b", t)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    if re.search(r"\b(g|гр|грамм|oz|унц)\b", t):
        return None
    return val

def make_premix(name: str, volume: int) -> str:
    g = cocktails_df[cocktails_df["название"] == name]
    if g.empty or "состав" not in g.columns or "граммовка" not in g.columns:
        return "❌ Не удалось посчитать премикс."
    usable: List[Tuple[str, float]] = []
    for _, r in g.iterrows():
        ing = str(r["состав"]).strip()
        amt = str(r["граммовка"]).strip()
        if not ing or ing in ["", "состав"]:
            continue
        if not is_cream_liqueur(ing) and any(tok in normalize_text(ing) for tok in EXCLUDE_TOKENS):
            continue
        ml = parse_ml(amt)
        if ml is None or ml <= 0:
            continue
        usable.append((ing, ml))
    if not usable:
        return f"📦 *Премикс {title_cap(name)}* ({volume} мл)\n\n_Нет подходящих ингредиентов для премикса_"
    total = sum(x[1] for x in usable)
    lines = [f"📦 *Премикс {title_cap(name)}* ({volume} мл)", ""]
    for ing, ml in usable:
        scaled = (ml / total) * volume
        scaled = math.floor(scaled / 10.0) * 10
        if scaled > 0:
            lines.append(f"— {ing} — {int(scaled)} мл")
    return "\n".join(lines)

# ---------- Клавиатура / Пагинация ----------
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍸 Коктейли", callback_data="list|cocktails|0")],
        [InlineKeyboardButton("🧪 Заготовки", callback_data="list|zagi|0")],
        [InlineKeyboardButton("🧪 Настойки", callback_data="list|tinct|0")],
    ])

def paged_names(kind: str, page: int, page_size: int = 20) -> Tuple[List[str], int]:
    names = {
        "cocktails": cocktail_names,
        "zagi":      zagi_names,
        "tinct":     tinct_names,
    }.get(kind, [])
    total_pages = max(1, math.ceil(len(names) / page_size))
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    return names[start:start + page_size], total_pages

def make_list_kb(kind: str, page: int) -> InlineKeyboardMarkup:
    items, total_pages = paged_names(kind, page)
    rows = [[InlineKeyboardButton(title_cap(n), callback_data=f"show|{kind}|{n}")] for n in items]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"list|{kind}|{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"list|{kind}|{page+1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)

# ---------- Хэндлеры ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Rambling-бот.\nНапиши название или выбери категорию:",
        reply_markup=main_menu_kb()
    )

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_raw = update.message.text or ""
    q = resolve_alias(q_raw)

    # Категории быстрым словом
    if q in ["коктейли", "коктейль", "коктели"]:
        await update.message.reply_text("🍸 Выбери коктейль:", reply_markup=make_list_kb("cocktails", 0))
        return
    if q in ["заготовки", "заготовка", "заг"]:
        await update.message.reply_text("🧪 Выбери заготовку:", reply_markup=make_list_kb("zagi", 0))
        return
    if q in ["настойки", "настойка", "наст"]:
        await update.message.reply_text("🧪 Выбери настойку:", reply_markup=make_list_kb("tinct", 0))
        return

    # Точное совпадение
    if q in cocktail_names_set:
        text = format_cocktail(q)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📦 500 мл",  callback_data=f"premix|{q}|500"),
            InlineKeyboardButton("📦 700 мл",  callback_data=f"premix|{q}|700"),
            InlineKeyboardButton("📦 1000 мл", callback_data=f"premix|{q}|1000"),
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return
    if q in zagi_names_set:
        await update.message.reply_text(format_zagotovka(q), parse_mode="Markdown")
        return
    if q in tinct_names_set:
        await update.message.reply_text(format_tincture(q), parse_mode="Markdown")
        return

    # Мягкий поиск
    q_nothe = q.replace(" the ", " ").strip()
    candidates = [n for n in cocktail_names if q_nothe in n or n in q_nothe]
    if candidates:
        best = sorted(candidates, key=len)[0]
        text = format_cocktail(best)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📦 500 мл",  callback_data=f"premix|{best}|500"),
            InlineKeyboardButton("📦 700 мл",  callback_data=f"premix|{best}|700"),
            InlineKeyboardButton("📦 1000 мл", callback_data=f"premix|{best}|1000"),
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return
    candidates = [n for n in zagi_names if q_nothe in n or n in q_nothe]
    if candidates:
        await update.message.reply_text(format_zagotovka(candidates[0]), parse_mode="Markdown")
        return
    candidates = [n for n in tinct_names if q_nothe in n or n in q_nothe]
    if candidates:
        await update.message.reply_text(format_tincture(candidates[0]), parse_mode="Markdown")
        return

    await update.message.reply_text("❌ Не нашёл. Попробуй другое название или открой меню /start")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = (query.data or "").split("|")

    if data[0] == "list":
        kind, page = data[1], int(data[2])
        title = {"cocktails": "🍸 Выбери коктейль:",
                 "zagi":      "🧪 Выбери заготовку:",
                 "tinct":     "🧪 Выбери настойку:"}.get(kind, "Выбери:")
        await query.message.reply_text(title, reply_markup=make_list_kb(kind, page))
        return

    if data[0] == "show":
        kind, name = data[1], data[2]
        if kind == "cocktails":
            text = format_cocktail(name)
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 500 мл",  callback_data=f"premix|{name}|500"),
                InlineKeyboardButton("📦 700 мл",  callback_data=f"premix|{name}|700"),
                InlineKeyboardButton("📦 1000 мл", callback_data=f"premix|{name}|1000"),
            ]])
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        elif kind == "zagi":
            await query.message.reply_text(format_zagotovka(name), parse_mode="Markdown")
        elif kind == "tinct":
            await query.message.reply_text(format_tincture(name), parse_mode="Markdown")
        return

    if data[0] == "premix":
        name, vol = data[1], int(data[2])
        await query.message.reply_text(make_premix(name, vol), parse_mode="Markdown")
        return

# ---------- Application (PTB) ----------
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
application.add_handler(CallbackQueryHandler(on_callback))

# Запускаем PTB в фоне (нужен для обработки очереди update_queue)
async def _runner():
    await application.initialize()
    await application.start()
    print(f"✅ Коктейли:  {len(cocktail_names)}")
    print(f"✅ Заготовки: {len(zagi_names)}")
    print(f"✅ Настойки:  {len(tinct_names)}")
    # держим живым
    await asyncio.Event().wait()

def _start_async_runner():
    asyncio.run(_runner())

threading.Thread(target=_start_async_runner, daemon=True).start()

# ---------- Flask ----------
app = Flask(__name__)

@app.get("/")
def index():
    return "OK", 200

@app.get("/health")
def health():
    return jsonify(ok=True), 200

@app.post("/webhook")
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    try:
        update = Update.de_json(data, application.bot)
        # Кладём апдейт в очередь PTB (он обрабатывается в фоне)
        application.update_queue.put_nowait(update)
    except Exception as e:
        print("Webhook error:", e)
    return "ok", 200

@app.get("/setwebhook")
def set_webhook():
    # /setwebhook?url=https://<ТВОЙ_ХОСТ>/webhook
    url = request.args.get("url")
    if not url:
        return "Передай ?url=https://<host>/webhook", 400
    async def _set():
        await application.bot.set_webhook(url)
    try:
        asyncio.run(_set())
        return f"Webhook установлен: {url}", 200
    except Exception as e:
        return f"Ошибка при set_webhook: {e}", 500

# ---- Запуск Flask (локально) ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
