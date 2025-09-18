# bot.py  — long polling версия (без Flask)
# Зависимости (в venv): pandas, openpyxl, python-telegram-bot==20.3, httpx==0.24.1, python-dotenv (опц.)
import os
import re
import math
import pandas as pd
from typing import Dict, List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# === ТВОЙ ТОКЕН ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

# === Пути к файлам (работают и локально, и на сервере) ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COCKTAILS_FILE   = os.path.join(BASE_DIR, "tech_cards_coctail_rambling.xlsx")
ZAGOTOVKI_FILE   = os.path.join(BASE_DIR, "tech_cards_zagi.xlsx")
TINCTURES_FILE   = os.path.join(BASE_DIR, "tech_cards_tinctures.xlsx")

# === Алиасы (отдельный файл рядом) ===
try:
    from aliases import ALIASES  # словарь: запрос -> каноническое имя (в нижнем регистре)
except Exception as e:
    print(f"⚠️ Не удалось импортировать aliases.py: {e}")
    ALIASES = {}

# ---------- Утилиты нормализации ----------
def normalize_text(s: str) -> str:
    """Нормализуем текст: нижний регистр, trim, одиночные пробелы, ё->е, убираем кавычки/дубликаты пробелов."""
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[\"“”„’']", " ", s)  # кавычки/апострофы -> пробел
    s = re.sub(r"\s+", " ", s)        # схлопываем пробелы
    return s

def resolve_alias(user_text: str) -> str:
    """Возвращает каноническое имя коктейля/заготовки/настойки по алиасам.
       Дополнительно превращает underscore в пробел (на случай старых ключей)."""
    t = normalize_text(user_text)
    mapped = ALIASES.get(t, t)
    mapped = normalize_text(mapped).replace("_", " ").strip()
    return mapped

# ---------- Загрузка Excel и нормализация колонок ----------
COL_SYNONYMS = {
    # нормализуем в нижний регистр: -> канонические ключи
    "название": "название",
    "name": "название",

    "посуда": "посуда",
    "glass": "посуда",

    "метод": "метод",
    "method": "метод",
    "приготовление": "приготовление",

    "гарниш": "гарниш",
    "garnish": "гарниш",

    "состав": "состав",
    "ингредиент": "состав",

    "ингредиенты": "ингредиенты",
    "ингридиенты": "ингредиенты",   # частая опечатка в файлах

    "граммовка": "граммовка",
    "amount": "граммовка",

    "выход": "выход",
    "yield": "выход",

    "метод приготовления": "метод",
}

def canon_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Понижаем регистр заголовков, тримим, переводим по словарю синонимов."""
    ren = {}
    for c in df.columns:
        k = normalize_text(str(c))
        ren[c] = COL_SYNONYMS.get(k, k)
    return df.rename(columns=ren)

def load_table(path: str, kind: str) -> pd.DataFrame:
    """Читает и нормализует таблицу, заполаяет пропуски по 'название' и чистит мусор."""
    df = pd.read_excel(path)
    df = canon_columns(df).ffill()
    if "название" in df.columns:
        df["название"] = df["название"].astype(str).apply(normalize_text)
        # уберём явные заголовки/мусор
        df = df[~df["название"].isin(["", "название", "name", "title", "none"])]
    # для удобства приведём остальные текстовые колонки
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).apply(lambda x: normalize_text(x) if col != "граммовка" else x.strip())
    # Доп. чистка граммовки: trim
    if "граммовка" in df.columns:
        df["граммовка"] = df["граммовка"].astype(str).str.strip()
    print(f"✅ Загружено {kind}: {df['название'].nunique() if 'название' in df.columns else '—'} уникальных имен")
    return df

# ---------- Загрузка данных ----------
cocktails_df = load_table(COCKTAILS_FILE, "коктейлей")
zagi_df      = load_table(ZAGOTOVKI_FILE, "заготовок")
tinct_df     = load_table(TINCTURES_FILE, "настоек")

# Сеты имён для быстрых проверок
cocktail_names = sorted(cocktails_df["название"].unique()) if "название" in cocktails_df.columns else []
zagi_names     = sorted(zagi_df.get("название", pd.Series([], dtype=str)).unique()) if "название" in zagi_df.columns else []
tinct_names    = sorted(tinct_df.get("название", pd.Series([], dtype=str)).unique()) if "название" in tinct_df.columns else []

cocktail_names_set = set(cocktail_names)
zagi_names_set     = set(zagi_names)
tinct_names_set    = set(tinct_names)

# ---------- Форматтеры ----------
def title_cap(s: str) -> str:
    """Красиво показать название (первая буква каждого слова). Не ломаем латиницу."""
    return " ".join(w.capitalize() for w in (s or "").split())

def format_cocktail(name: str) -> str:
    g = cocktails_df[cocktails_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл коктейль."
    # Берём первую строку для посуды/метода/гарниша
    glass   = g["посуда"].iloc[0]   if "посуда"   in g.columns else ""
    method  = g["метод"].iloc[0]    if "метод"    in g.columns else ""
    garnish = g["гарниш"].iloc[0]   if "гарниш"   in g.columns else ""

    lines = [f"🍸 *{title_cap(name)}*", ""]
    if glass:   lines.append(f"🥃 Посуда: {glass}")
    if method:  lines.append(f"🛠 Метод: {method}")
    if garnish: lines.append(f"🌿 Гарниш: {garnish}")
    lines.append("")

    # Ингредиенты
    if "состав" in g.columns and "граммовка" in g.columns:
        for _, r in g.iterrows():
            ing = r["состав"]
            amt = r["граммовка"]
            if ing and ing not in ["", "состав"] and amt and amt != "":
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
            ing = r["ингредиенты"]
            amt = r["граммовка"]
            if ing and ing not in ["", "ингредиенты"] and amt and amt != "":
                lines.append(f"— {ing} — {amt}")
    if "приготовление" in g.columns and g["приготовление"].iloc[0]:
        lines.append("")
        lines.append(f"🧯 Метод: {g['приготовление'].iloc[0]}")
    if "выход" in g.columns and g["выход"].iloc[0]:
        lines.append(f"📦 Выход: {g['выход'].iloc[0]}")
    return "\n".join(lines)

def format_tincture(name: str) -> str:
    g = tinct_df[tinct_df["название"] == name]
    if g.empty:
        return "❌ Не нашёл настойку."
    lines = [f"🧪 *{title_cap(name)}*", ""]
    if "ингредиенты" in g.columns and "граммовка" in g.columns:
        for _, r in g.iterrows():
            ing = r["ингредиенты"]
            amt = r["граммовка"]
            if ing and ing not in ["", "ингредиенты"] and amt and amt != "":
                lines.append(f"— {ing} — {amt}")
    if "метод" in g.columns and g["метод"].iloc[0]:
        lines.append("")
        lines.append(f"🧯 Метод: {g['метод'].iloc[0]}")
    return "\n".join(lines)

# ---------- Премиксы ----------
EXCLUDE_TOKENS = [
    # портится/газ/молочка/топы
    "juice", "сок", "sparkling", "игрист", "soda", "сода", "кола", "coke", "sprite", "tonic", "тоник",
    "cream", "сливк", "milk", "молоко",
    "puree", "пюре",
    "top", "дэш", "dash", "barspoon", "бс", "щепотка", "pinch", "pt",
]
# Разрешаем сливочный ликёр
ALLOW_CREAM_LIQUEUR = [
    "baileys", "irish cream", "сливочн", "liqueur", "ликер", "ликёр"
]

def is_cream_liqueur(ing: str) -> bool:
    s = normalize_text(ing)
    if "baileys" in s or "irish cream" in s:
        return True
    if "сливочн" in s and ("ликер" in s or "ликёр" in s or "liqueur" in s):
        return True
    return False

def parse_ml(s: str) -> Optional[float]:
    """Достаём число (мл) из строки. Возвращаем None, если это не миллилитры."""
    if s is None:
        return None
    t = s.strip().lower()
    # явные не-мл
    if any(x in t for x in ["top", "дэш", "dash", "barspoon", "pt", "щепотка", "pinch"]):
        return None
    # ловим число и смотрим, есть ли указание ml/мл (или вообще только число)
    m = re.search(r"(\d+([.,]\d+)?)\s*(ml|мл)?\b", t)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    # если есть конкретно другая единица (гр, грамм и т.п.) — не считаем это мл
    if re.search(r"\b(g|гр|грамм|oz|унц)\b", t):
        return None
    return val

def make_premix(name: str, volume: int) -> str:
    g = cocktails_df[cocktails_df["название"] == name]
    if g.empty or "состав" not in g.columns or "граммовка" not in g.columns:
        return "❌ Не удалось посчитать премикс."

    # выбираем годные ингредиенты
    usable: List[Tuple[str, float]] = []
    for _, r in g.iterrows():
        ing = r["состав"]
        amt = r["граммовка"]
        if not ing or ing in ["", "состав"]:
            continue

        # исключения (кроме сливочного ликёра)
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
        scaled = math.floor(scaled / 10.0) * 10  # округление вниз до 10 мл
        if scaled <= 0:
            continue
        lines.append(f"— {ing} — {int(scaled)} мл")

    return "\n".join(lines) if len(lines) > 2 else f"📦 *Премикс {title_cap(name)}*: _ничего не вошло_"

# ---------- Хэндлеры ----------
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍸 Коктейли", callback_data="list|cocktails|0")],
        [InlineKeyboardButton("🧪 Заготовки", callback_data="list|zagi|0")],
        [InlineKeyboardButton("🧪 Настойки", callback_data="list|tinct|0")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Rambling-бот.\n"
        "Напиши название напитка или выбери категорию ниже.",
        reply_markup=main_menu_kb()
    )

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

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")

    # Пагинация
    if data[0] == "list":
        kind, page = data[1], int(data[2])
        title = {"cocktails": "🍸 Выбери коктейль:",
                 "zagi":      "🧪 Выбери заготовку:",
                 "tinct":     "🧪 Выбери настойку:"}.get(kind, "Выбери:")
        await query.message.reply_text(title, reply_markup=make_list_kb(kind, page))
        return

    # Показ выбранного
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

    # Премиксы
    if data[0] == "premix":
        name, vol = data[1], int(data[2])
        await query.message.reply_text(make_premix(name, vol), parse_mode="Markdown")
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_raw = update.message.text or ""
    q = resolve_alias(q_raw)

    # Категории
    if q in ["заготовки", "заготовка", "заг"]:
        await update.message.reply_text("🧪 Выбери заготовку:", reply_markup=make_list_kb("zagi", 0))
        return
    if q in ["настойки", "настойка", "наст"]:
        await update.message.reply_text("🧪 Выбери настойку:", reply_markup=make_list_kb("tinct", 0))
        return
    if q in ["коктейли", "коктейль", "коктели"]:
        await update.message.reply_text("🍸 Выбери коктейль:", reply_markup=make_list_kb("cocktails", 0))
        return

    # Попытка найти напрямую
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

    # Мягкий поиск (без the, contains)
    q_nothe = q.replace(" the ", " ").strip()
    candidates = [n for n in cocktail_names if q_nothe in n or n in q_nothe]
    if not candidates:
        candidates = [n for n in zagi_names if q_nothe in n or n in q_nothe]
        if candidates:
            await update.message.reply_text(format_zagotovka(candidates[0]), parse_mode="Markdown")
            return
        candidates = [n for n in tinct_names if q_nothe in n or n in q_nothe]
        if candidates:
            await update.message.reply_text(format_tincture(candidates[0]), parse_mode="Markdown")
            return
    else:
        best = sorted(candidates, key=len)[0]
        text = format_cocktail(best)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📦 500 мл",  callback_data=f"premix|{best}|500"),
            InlineKeyboardButton("📦 700 мл",  callback_data=f"premix|{best}|700"),
            InlineKeyboardButton("📦 1000 мл", callback_data=f"premix|{best}|1000"),
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    await update.message.reply_text("❌ Не нашёл. Попробуй другое название или открой меню /start")

# ---------- Запуск ----------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"✅ Коктейли:  {len(cocktail_names)}")
    print(f"✅ Заготовки: {len(zagi_names)}")
    print(f"✅ Настойки:  {len(tinct_names)}")
    print("🤖 Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
