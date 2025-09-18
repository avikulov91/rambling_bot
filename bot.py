import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from aliases import ALIASES  # импортируем словарь алиасов

# === НАСТРОЙКИ ===
TOKEN = "8442487432:AAFmTCgUAt57UcJhSbMool1IsCi8snOIPEs"

# Пути к Excel
COCKTAILS_FILE = "tech_cards_coctail_rambling.xlsx"
ZAGOTOVKI_FILE = "tech_cards_zagi.xlsx"
TINCTURES_FILE = "tech_cards_tinctures.xlsx"


# === ЗАГРУЗКА ДАННЫХ ===
def load_excel(file_path, mode="cocktails"):
    df = pd.read_excel(file_path)

    # Заполняем пустые названия предыдущими
    if "Название" in df.columns:
        df["Название"] = df["Название"].fillna(method="ffill")

    # Нормализуем
    df["Название"] = df["Название"].astype(str).str.strip().str.lower()

    # Убираем полностью пустые строки
    df = df.dropna(how="all")

    # Разные режимы
    if mode == "cocktails":
        df.columns = ["cocktail_name", "glass", "method", "garnish", "ingredient", "amount"]
    elif mode == "zagi":
        df.columns = ["name", "ingredient", "amount", "method", "output"]
    elif mode == "tinctures":
        df.columns = ["name", "ingredient", "amount", "method"]

    return df


cocktails_df = load_excel(COCKTAILS_FILE, mode="cocktails")
zagi_df = load_excel(ZAGOTOVKI_FILE, mode="zagi")
tinctures_df = load_excel(TINCTURES_FILE, mode="tinctures")

print(f"✅ Загружено коктейлей: {cocktails_df['cocktail_name'].nunique()}")
print(f"✅ Загружено заготовок: {zagi_df['name'].nunique()}")
print(f"✅ Загружено настоек: {tinctures_df['name'].nunique()}")


# === ПОИСК ===
def find_cocktail(query):
    q = query.strip().lower()

    # Алиасы
    if q in ALIASES:
        q = ALIASES[q]

    results = cocktails_df[cocktails_df["cocktail_name"] == q]
    return results if not results.empty else None


def find_zagotovka(query):
    q = query.strip().lower()
    results = zagi_df[zagi_df["name"] == q]
    return results if not results.empty else None


def find_tincture(query):
    q = query.strip().lower()
    results = tinctures_df[tinctures_df["name"] == q]
    return results if not results.empty else None


# === ХЕНДЛЕРЫ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍸 Напиши название коктейля, заготовки или настойки.\n\n"
        "🧪 Напиши 'заготовки' или 'настойки', чтобы открыть список."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    # Запрос списка
    if text == "заготовки":
        buttons = [InlineKeyboardButton(name.title(), callback_data=f"zagi|{name}") for name in zagi_df["name"].unique()]
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        await update.message.reply_text("🧪 Заготовки:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if text == "настойки":
        buttons = [InlineKeyboardButton(name.title(), callback_data=f"tinct|{name}") for name in tinctures_df["name"].unique()]
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        await update.message.reply_text("🧪 Настойки:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Коктейли
    cocktail = find_cocktail(text)
    if cocktail is not None:
        base = cocktail.iloc[0]
        ingredients = cocktail[["ingredient", "amount"]].dropna().values.tolist()
        ing_list = "\n".join([f"• {i} — {a}" for i, a in ingredients])
        msg = (
            f"🍸 {base['cocktail_name'].title()}\n"
            f"🥂 Посуда: {base['glass']}\n"
            f"⚙️ Метод: {base['method']}\n"
            f"🍋 Гарниш: {base['garnish']}\n\n"
            f"Ингредиенты:\n{ing_list}"
        )
        # Кнопки премиксов
        keyboard = [
            [InlineKeyboardButton("500 мл", callback_data=f"premix|{base['cocktail_name']}|500")],
            [InlineKeyboardButton("700 мл", callback_data=f"premix|{base['cocktail_name']}|700")],
            [InlineKeyboardButton("1000 мл", callback_data=f"premix|{base['cocktail_name']}|1000")],
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Заготовки
    z = find_zagotovka(text)
    if z is not None:
        base = z.iloc[0]
        ingredients = z[["ingredient", "amount"]].dropna().values.tolist()
        ing_list = "\n".join([f"• {i} — {a}" for i, a in ingredients])
        msg = (
            f"🧪 {base['name'].title()}\n\n"
            f"Ингредиенты:\n{ing_list}\n\n"
            f"⚙️ Метод: {base['method']}\n"
            f"📦 Выход: {base['output']}"
        )
        await update.message.reply_text(msg)
        return

    # Настойки
    t = find_tincture(text)
    if t is not None:
        base = t.iloc[0]
        ingredients = t[["ingredient", "amount"]].dropna().values.tolist()
        ing_list = "\n".join([f"• {i} — {a}" for i, a in ingredients])
        msg = (
            f"🧪 {base['name'].title()}\n\n"
            f"Ингредиенты:\n{ing_list}\n\n"
            f"⚙️ Метод: {base['method']}"
        )
        await update.message.reply_text(msg)
        return

    # Если ничего не найдено
    await update.message.reply_text("❌ Ничего не найдено.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")

    if data[0] == "premix":
        name, volume = data[1], int(data[2])
        cocktail = find_cocktail(name)
        if cocktail is not None:
            # Исключаем "соки", "сливки", "соду", "игристое"
            bad_words = ["juice", "сок", "сливки", "cream", "сода", "sparkling", "игристое"]
            premix = cocktail[~cocktail["ingredient"].str.lower().str.contains("|".join(bad_words), na=False)]
            premix = premix[["ingredient", "amount"]].dropna().values.tolist()
            # Пересчет
            scaled = []
            for i, a in premix:
                try:
                    val = float(str(a).split()[0])
                    unit = str(a).split()[1] if len(str(a).split()) > 1 else "ml"
                    new_val = (val / 100) * volume
                    new_val = int(new_val // 10 * 10)  # округление вниз до 10
                    scaled.append(f"• {i} — {new_val} {unit}")
                except:
                    scaled.append(f"• {i} — {a}")
            msg = f"🥃 Премикс для {name.title()} ({volume} мл):\n\n" + "\n".join(scaled)
            await query.edit_message_text(msg)
    elif data[0] == "zagi":
        name = data[1]
        z = find_zagotovka(name)
        if z is not None:
            base = z.iloc[0]
            ingredients = z[["ingredient", "amount"]].dropna().values.tolist()
            ing_list = "\n".join([f"• {i} — {a}" for i, a in ingredients])
            msg = (
                f"🧪 {base['name'].title()}\n\n"
                f"Ингредиенты:\n{ing_list}\n\n"
                f"⚙️ Метод: {base['method']}\n"
                f"📦 Выход: {base['output']}"
            )
            await query.edit_message_text(msg)
    elif data[0] == "tinct":
        name = data[1]
        t = find_tincture(name)
        if t is not None:
            base = t.iloc[0]
            ingredients = t[["ingredient", "amount"]].dropna().values.tolist()
            ing_list = "\n".join([f"• {i} — {a}" for i, a in ingredients])
            msg = (
                f"🧪 {base['name'].title()}\n\n"
                f"Ингредиенты:\n{ing_list}\n\n"
                f"⚙️ Метод: {base['method']}"
            )
            await query.edit_message_text(msg)


# === MAIN ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()


if __name__ == "__main__":
    main()
