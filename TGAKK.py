import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Вставьте сюда ваш токен от BotFather
TOKEN = '8780814774:AAGIo1vtj6rCp_io8s5f-vUwsrpvrI3k19Y'
# Вставьте сюда ваш числовой ID (чтобы бот знал, куда слать уведомления о покупке)
ADMIN_ID = 8577851888 

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    text = (
        "Привет 👋\n\n"
        "Этот бот поможет тебе купить Telegram аккаунты по НИЗКИМ ЦЕНАМ!\n\n"
        "Скорее выбирай кнопку ниже."
    )
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data='profile')],
        [InlineKeyboardButton("🛒 Купить", callback_data='buy')],
        [InlineKeyboardButton("🆘 Тех. Поддержка", url='https://t.me/Aleks148F')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Если это вызов через кнопку (callback), редактируем старое сообщение
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    # Если это команда /start, отправляем новое сообщение
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user

    if data == 'profile':
        text = (
            f"Твой профиль:\n"
            f"Юзернейм — @{user.username if user.username else 'не установлен'}\n"
            f"Имя — {user.first_name}"
        )
        keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data='main_menu')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'main_menu':
        await start(update, context)

    elif data == 'buy':
        text = "Выбирай страну:"
        keyboard = [
            [InlineKeyboardButton("🇬🇧 Великобритания - 75 звёзд", callback_data='buy_UK')],
            [InlineKeyboardButton("🇩🇪 Германия - 100 звёзд", callback_data='buy_GER')],
            [InlineKeyboardButton("🇮🇷 Иран - нет в наличии", callback_data='soon')],
            [InlineKeyboardButton("🇻🇳 Вьетнам - 50 звёзд", callback_data='buy_VIET')], # Новая кнопка
            [InlineKeyboardButton("🇺🇸 США - 50 звезд", callback_data='buy_SHA')],
            [InlineKeyboardButton("🔙 В меню", callback_data='main_menu')]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('buy_'):
        # Словарь для сопоставления callback_data и названия страны
        country_map = {
            'buy_UK': 'Великобритания (75 звёзд)',
            'buy_GER': 'Германия (100 звёзд)',
            'buy_VIET': 'Вьетнам (50 звёзд)',    'buy_SHA' : 'США (50 звезд)' # Добавлено в обработку
        }
        selected_country = country_map.get(data)
        
        # Сообщение пользователю
        await query.message.edit_text(
            "Окей, скоро тебе отпишет администрация. Не забудь сказать как будешь оплачивать! "
            "(Поддерживаются методы USDT (@send) и звёзды)"
        )
        
        # Кнопка возврата в меню
        keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data='main_menu')]]
        await query.message.reply_text("Вернуться назад:", reply_markup=InlineKeyboardMarkup(keyboard))

        # Уведомление администратору (@Aleks148F)
        admin_text = (
            f"🔔 НОВЫЙ ЗАКАЗ!\n\n"
            f"Пользователь: {user.first_name}\n"
            f"Юзернейм: @{user.username if user.username else 'скрыт'}\n"
            f"Выбрал товар: {selected_country}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомления админу: {e}")

    elif data == 'soon':
        await query.answer("Этот товар пока недоступен", show_alert=True)

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
