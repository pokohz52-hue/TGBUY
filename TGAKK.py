import asyncio
import logging
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

# --- НАСТРОЙКИ ---
API_TOKEN = '8269166288:AAEjLKfyE7JcdY3nNSPs4gJHW5omTMYCw1A'
ADMIN_ID = 8268348063 
LOG_CHANNEL_ID = -1003664077943  # Твой новый ID канала для логов
REF_REWARD = 0.02
TASK_REWARD = 0.01
MIN_WITHDRAW = 0.1
DAILY_BONUS_MIN = 0.001
DAILY_BONUS_MAX = 0.005

# --- БАЗА ДАННЫХ ---
class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_db()

    def create_db(self):
        with self.connection:
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, 
                referred_by INTEGER, last_bonus TEXT)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, channel_id TEXT, 
                limit_count INTEGER DEFAULT 0, current_count INTEGER DEFAULT 0)""")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS completed_tasks (user_id INTEGER, task_id INTEGER, PRIMARY KEY (user_id, task_id))")

    def user_exists(self, user_id):
        return bool(self.cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone())

    def add_user(self, user_id, referrer_id=None):
        with self.connection:
            self.cursor.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referrer_id))

    def get_user(self, user_id):
        return self.cursor.execute("SELECT balance, last_bonus FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def update_balance(self, user_id, amount):
        with self.connection:
            self.cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))

    def reset_balance(self, user_id):
        with self.connection:
            self.cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))

    def set_bonus_time(self, user_id):
        with self.connection:
            self.cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))

    def get_stats(self):
        u_count = self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_b = self.cursor.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
        return u_count, round(total_b, 3)

db = Database('bot_data.db')
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---
def main_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"), 
                InlineKeyboardButton(text="📝 Задания", callback_data="tasks"))
    builder.row(InlineKeyboardButton(text="🔗 Рефы", callback_data="refs"),
                InlineKeyboardButton(text="🎁 Бонус", callback_data="daily_bonus"))
    if user_id == ADMIN_ID:
        builder.row(InlineKeyboardButton(text="⚙️ Админка", callback_data="admin_panel"))
    return builder.as_markup()

# --- АДМИН-КОМАНДЫ ---

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace("/broadcast", "").strip()
    if not text: return await message.answer("⚠️ Введите текст: <code>/broadcast привет</code>", parse_mode="HTML")
    
    users = db.cursor.execute("SELECT user_id FROM users").fetchall()
    count = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, f"📢 <b>Рассылка:</b>\n\n{text}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Рассылка завершена. Получили {count} юзеров.")

@dp.message(Command("add_task"))
async def add_task_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4: return await message.answer("⚠️ Формат: <code>/add_task @канал лимит Текст</code>", parse_mode="HTML")
    
    try:
        with db.connection:
            db.cursor.execute("INSERT INTO tasks (text, channel_id, limit_count) VALUES (?, ?, ?)", (parts[3], parts[1], int(parts[2])))
        await message.answer(f"✅ Задание успешно добавлено!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("del_task"))
async def del_task_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2: return await message.answer("⚠️ Формат: <code>/del_task ID</code>")
    with db.connection:
        db.cursor.execute("DELETE FROM tasks WHERE id = ?", (parts[1],))
    await message.answer(f"🗑 Задание #{parts[1]} удалено из базы.")

@dp.message(Command("myid"))
async def myid_cmd(message: types.Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

# --- ОСНОВНАЯ ЛОГИКА ---

@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    if not db.user_exists(user_id):
        args = message.text.split()
        ref = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        db.add_user(user_id, ref)
        if ref and ref != user_id:
            db.update_balance(ref, REF_REWARD)
    await message.answer("<b>Добро пожаловать в меню!</b>", reply_markup=main_kb(user_id), parse_mode="HTML")

@dp.callback_query(F.data == "tasks")
async def tasks_list(callback: types.CallbackQuery):
    tasks = db.cursor.execute("SELECT id, text, limit_count, current_count FROM tasks WHERE current_count < limit_count").fetchall()
    if not tasks: return await callback.answer("Заданий пока нет!", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for tid, txt, lim, cur in tasks:
        # Админ видит ID и статистику на кнопках
        prefix = f"#{tid} ({cur}/{lim}) " if callback.from_user.id == ADMIN_ID else ""
        builder.row(InlineKeyboardButton(text=f"🎁 {prefix}{txt[:15]}...", callback_data=f"view_{tid}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu"))
    await callback.message.edit_text("Выберите задание для выполнения:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_task(callback: types.CallbackQuery):
    tid = int(callback.data.split("_")[1])
    task = db.cursor.execute("SELECT text, channel_id, current_count, limit_count FROM tasks WHERE id = ?", (tid,)).fetchone()
    if not task or task[2] >= task[3]: return await callback.answer("Задание завершено!", show_alert=True)
    
    url = f"https://t.me/{task[1].replace('@', '')}"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Перейти в канал", url=url))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data=f"check_{tid}"))
    builder.row(InlineKeyboardButton(text="🔙 К списку", callback_data="tasks"))
    await callback.message.edit_text(f"<b>Задание:</b> {task[0]}", reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("check_"))
async def check_task(callback: types.CallbackQuery):
    tid = int(callback.data.split("_")[1])
    task = db.cursor.execute("SELECT channel_id, current_count, limit_count FROM tasks WHERE id = ?", (tid,)).fetchone()
    
    if not task or task[1] >= task[2]:
        return await callback.answer("Лимит выполнений этого задания исчерпан!")

    try:
        m = await bot.get_chat_member(task[0], callback.from_user.id)
        if m.status in ['left', 'kicked', 'banned']: 
            return await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)
        
        check = db.cursor.execute("SELECT 1 FROM completed_tasks WHERE user_id=? AND task_id=?", (callback.from_user.id, tid)).fetchone()
        if not check:
            with db.connection:
                db.cursor.execute("INSERT INTO completed_tasks VALUES (?, ?)", (callback.from_user.id, tid))
                db.cursor.execute("UPDATE tasks SET current_count = current_count + 1 WHERE id = ?", (tid,))
            db.update_balance(callback.from_user.id, TASK_REWARD)
            await callback.answer(f"✅ Начислено {TASK_REWARD} USDT!", show_alert=True)
            await menu(callback)
        else:
            await callback.answer("Вы уже получили награду за это задание!")
    except Exception:
        await callback.answer("Ошибка: бот должен быть администратором в канале!")

@dp.callback_query(F.data == "withdraw")
async def withdraw(callback: types.CallbackQuery):
    u_id = callback.from_user.id
    res = db.get_user(u_id)
    if res[0] < MIN_WITHDRAW:
        return await callback.answer(f"Минимальный вывод — {MIN_WITHDRAW} USDT", show_alert=True)
    
    amount = round(res[0], 3)
    user_tag = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {u_id}"
    
    # Сообщение тебе (админу)
    await bot.send_message(ADMIN_ID, f"🚀 <b>НОВАЯ ЗАЯВКА НА ВЫВОД!</b>\nЮзер: {user_tag} ({u_id})\nСумма: <b>{amount} USDT</b>")
    
    # Пост в канал логов
    try:
        log_text = (f"💸 <b>Успешный вывод!</b>\n"
                    f"👤 Пользователь: {user_tag}\n"
                    f"💰 Сумма: <b>{amount} USDT</b>\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        await bot.send_message(LOG_CHANNEL_ID, log_text, parse_mode="HTML")
    except Exception:
        pass
    
    db.reset_balance(u_id)
    await callback.answer("Заявка успешно отправлена на модерацию!", show_alert=True)
    await menu(callback)

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    u, b = db.get_stats()
    text = (f"⚙️ <b>Панель администратора</b>\n\n"
            f"👥 Всего юзеров: {u}\n"
            f"💳 Всего на балансах: {b} USDT\n\n"
            f"Команды:\n"
            f"<code>/add_task @канал лимит текст</code>\n"
            f"<code>/del_task ID</code>\n"
            f"<code>/broadcast текст</code>")
    builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🔙 В меню", callback_data="menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    u = db.get_user(callback.from_user.id)
    text = f"👤 <b>Ваш профиль</b>\n\n💰 Баланс: <b>{round(u[0], 3)} USDT</b>"
    builder = InlineKeyboardBuilder()
    if u[0] >= MIN_WITHDRAW:
        builder.row(InlineKeyboardButton(text="💸 Вывести средства", callback_data="withdraw"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "daily_bonus")
async def daily_bonus(callback: types.CallbackQuery):
    u = db.get_user(callback.from_user.id)
    if u[1] and datetime.now() < datetime.fromisoformat(u[1]) + timedelta(days=1):
        return await callback.answer("🎁 Бонус можно забрать только раз в 24 часа!", show_alert=True)
    
    r = round(random.uniform(DAILY_BONUS_MIN, DAILY_BONUS_MAX), 4)
    db.update_balance(callback.from_user.id, r)
    db.set_bonus_time(callback.from_user.id)
    await callback.answer(f"🎉 Вы получили бонус {r} USDT!", show_alert=True)

@dp.callback_query(F.data == "menu")
async def menu(callback: types.CallbackQuery):
    await callback.message.edit_text("<b>Главное меню:</b>", reply_markup=main_kb(callback.from_user.id), parse_mode="HTML")

@dp.callback_query(F.data == "refs")
async def refs(callback: types.CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={callback.from_user.id}"
    text = (f"🔗 <b>Реферальная система</b>\n\n"
            f"Приглашайте друзей и получайте <b>{REF_REWARD} USDT</b> за каждого!\n\n"
            f"Ваша ссылка:\n<code>{link}</code>")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_kb(callback.from_user.id))

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())