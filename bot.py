import asyncio
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup)

# ===== НАСТРОЙКИ (поменяй под себя) =====
TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # твой Telegram ID (узнать у @userinfobot)
GAME = "Counter Flame"
BUY_RATE = 0.50    # грн за 1 голду, когда клиент покупает
SELL_RATE = 0.30   # грн за 1 голду, когда клиент продаёт
MIN_GOLD = 10
REQUISITES = "Карта: 0000 0000 0000 0000\nПолучатель: Имя Ф."
SUPPORT_URL = "https://t.me/your_support"
REVIEWS_URL = "https://t.me/your_reviews"
# ========================================

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


def db(sql, args=()):
    con = sqlite3.connect("shop.db")
    con.row_factory = sqlite3.Row
    cur = con.execute(sql, args)
    rows, last = cur.fetchall(), cur.lastrowid
    con.commit()
    con.close()
    return rows, last


db("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
db("""CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT,
    gold INTEGER, uah REAL, info TEXT, status TEXT)""")

MENU = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
    [KeyboardButton(text="🛒 Купить"), KeyboardButton(text="⚡ Вывести голду"), KeyboardButton(text="💰 Продать голду")],
    [KeyboardButton(text="🧮 Посчитать"), KeyboardButton(text="🆘 Поддержка"), KeyboardButton(text="👤 Профиль")],
    [KeyboardButton(text="ℹ️ Отзывы")],
])


class Buy(StatesGroup):
    amount = State()


class Calc(StatesGroup):
    amount = State()


class Withdraw(StatesGroup):
    amount = State()
    nick = State()


class Sell(StatesGroup):
    amount = State()
    details = State()


def num(text):
    try:
        n = int(text.strip())
        return n if n >= MIN_GOLD else None
    except Exception:
        return None


def balance(uid):
    db("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))
    return db("SELECT balance FROM users WHERE id=?", (uid,))[0][0]["balance"]


def who(u):
    return f'<a href="tg://user?id={u.id}">{u.full_name}</a> (<code>{u.id}</code>)'


def admin_kb(oid):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm:ok:{oid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:no:{oid}"),
    ]])


# ---------- меню ----------
@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    balance(m.from_user.id)
    await m.answer(f"👋 Привет! Это магазин голды для <b>{GAME}</b>.\nВыбери действие:", reply_markup=MENU)


@dp.message(F.text == "👤 Профиль")
async def profile(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(f"👤 <b>Профиль</b>\nID: <code>{m.from_user.id}</code>\n🍯 Баланс: <b>{balance(m.from_user.id)}</b> голды")


@dp.message(F.text == "🆘 Поддержка")
async def support(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Напиши в поддержку:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🆘 Открыть чат", url=SUPPORT_URL)]]))


@dp.message(F.text == "ℹ️ Отзывы")
async def reviews(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Отзывы наших клиентов:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⭐ Читать отзывы", url=REVIEWS_URL)]]))


# ---------- калькулятор ----------
@dp.message(F.text == "🧮 Посчитать")
async def calc_start(m: Message, state: FSMContext):
    await state.set_state(Calc.amount)
    await m.answer("Сколько голды посчитать? Напиши число.")


@dp.message(Calc.amount)
async def calc_done(m: Message, state: FSMContext):
    n = num(m.text or "")
    if not n:
        return await m.answer(f"Введи число от {MIN_GOLD}.")
    await state.clear()
    await m.answer(f"🍯 {n} голды\n🛒 Купить: <b>{n * BUY_RATE:.2f} грн</b>\n💰 Продать: <b>{n * SELL_RATE:.2f} грн</b>")


# ---------- покупка ----------
@dp.message(F.text == "🛒 Купить")
async def buy_start(m: Message, state: FSMContext):
    await state.set_state(Buy.amount)
    await m.answer(f"Сколько голды хочешь купить? (от {MIN_GOLD})\nКурс: 1 голда = {BUY_RATE} грн")


@dp.message(Buy.amount)
async def buy_amount(m: Message, state: FSMContext):
    n = num(m.text or "")
    if not n:
        return await m.answer(f"Введи число от {MIN_GOLD}.")
    await state.clear()
    uah = round(n * BUY_RATE, 2)
    _, oid = db("INSERT INTO orders(user_id,kind,gold,uah,status) VALUES(?,?,?,?,?)",
                (m.from_user.id, "buy", n, uah, "new"))
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid:{oid}")]])
    await m.answer(f"🧾 Заказ #{oid}\n🍯 {n} голды за <b>{uah} грн</b>\n\nОплати по реквизитам:\n"
                   f"{REQUISITES}\n\nПосле оплаты нажми кнопку ниже.", reply_markup=kb)


@dp.callback_query(F.data.startswith("paid:"))
async def paid(c: CallbackQuery):
    oid = int(c.data.split(":")[1])
    rows, _ = db("SELECT * FROM orders WHERE id=? AND user_id=? AND status='new'", (oid, c.from_user.id))
    if not rows:
        return await c.answer("Заказ уже обработан", show_alert=True)
    o = rows[0]
    db("UPDATE orders SET status='paid' WHERE id=?", (oid,))
    await c.message.edit_reply_markup()
    await c.message.answer("⏳ Ждём подтверждение оплаты. Если нужно, пришли чек в поддержку.")
    await bot.send_message(ADMIN_ID, f"💳 Покупка #{oid}\n{who(c.from_user)}\n"
                                     f"🍯 {o['gold']} голды, {o['uah']} грн", reply_markup=admin_kb(oid))
    await c.answer()


# ---------- вывод голды в игру ----------
@dp.message(F.text == "⚡ Вывести голду")
async def wd_start(m: Message, state: FSMContext):
    bal = balance(m.from_user.id)
    if bal < MIN_GOLD:
        return await m.answer(f"На балансе {bal} голды. Минимум для вывода: {MIN_GOLD}.")
    await state.set_state(Withdraw.amount)
    await m.answer(f"Баланс: {bal} голды. Сколько вывести?")


@dp.message(Withdraw.amount)
async def wd_amount(m: Message, state: FSMContext):
    n = num(m.text or "")
    if not n or n > balance(m.from_user.id):
        return await m.answer("Введи число не больше баланса.")
    await state.update_data(gold=n)
    await state.set_state(Withdraw.nick)
    await m.answer(f"Напиши свой ник и ID в {GAME}, куда отправить голду.")


@dp.message(Withdraw.nick)
async def wd_nick(m: Message, state: FSMContext):
    n = (await state.get_data())["gold"]
    await state.clear()
    if n > balance(m.from_user.id):
        return await m.answer("Недостаточно голды на балансе.")
    db("UPDATE users SET balance=balance-? WHERE id=?", (n, m.from_user.id))
    _, oid = db("INSERT INTO orders(user_id,kind,gold,info,status) VALUES(?,?,?,?,?)",
                (m.from_user.id, "withdraw", n, m.text, "pending"))
    await m.answer(f"✅ Заявка #{oid} на вывод {n} голды создана. Скоро отправим.")
    await bot.send_message(ADMIN_ID, f"⚡ Вывод #{oid}\n{who(m.from_user)}\n🍯 {n} голды\nИгрок: {m.text}",
                           reply_markup=admin_kb(oid))


# ---------- продажа голды ----------
@dp.message(F.text == "💰 Продать голду")
async def sell_start(m: Message, state: FSMContext):
    await state.set_state(Sell.amount)
    await m.answer(f"Сколько голды хочешь продать? (от {MIN_GOLD})\nКурс: 1 голда = {SELL_RATE} грн")


@dp.message(Sell.amount)
async def sell_amount(m: Message, state: FSMContext):
    n = num(m.text or "")
    if not n:
        return await m.answer(f"Введи число от {MIN_GOLD}.")
    await state.update_data(gold=n)
    await state.set_state(Sell.details)
    await m.answer(f"Получишь <b>{n * SELL_RATE:.2f} грн</b>. Напиши номер карты для выплаты и свой ник в игре.")


@dp.message(Sell.details)
async def sell_details(m: Message, state: FSMContext):
    n = (await state.get_data())["gold"]
    await state.clear()
    uah = round(n * SELL_RATE, 2)
    _, oid = db("INSERT INTO orders(user_id,kind,gold,uah,info,status) VALUES(?,?,?,?,?,?)",
                (m.from_user.id, "sell", n, uah, m.text, "pending"))
    await m.answer(f"✅ Заявка #{oid} создана. Админ свяжется с тобой для передачи голды.")
    await bot.send_message(ADMIN_ID, f"💰 Продажа #{oid}\n{who(m.from_user)}\n🍯 {n} голды → {uah} грн\n"
                                     f"Данные: {m.text}", reply_markup=admin_kb(oid))


# ---------- действия админа ----------
@dp.callback_query(F.data.startswith("adm:"))
async def admin_action(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)
    _, act, oid = c.data.split(":")
    oid = int(oid)
    rows, _ = db("SELECT * FROM orders WHERE id=? AND status IN ('paid','pending')", (oid,))
    if not rows:
        return await c.answer("Заказ уже обработан", show_alert=True)
    o = rows[0]
    ok = act == "ok"
    db("UPDATE orders SET status=? WHERE id=?", ("done" if ok else "rejected", oid))
    if o["kind"] == "buy" and ok:
        db("INSERT OR IGNORE INTO users(id) VALUES(?)", (o["user_id"],))
        db("UPDATE users SET balance=balance+? WHERE id=?", (o["gold"], o["user_id"]))
        text = f"✅ Оплата подтверждена! 🍯 {o['gold']} голды зачислено на баланс."
    elif o["kind"] == "withdraw" and ok:
        text = f"✅ Заявка #{oid}: {o['gold']} голды отправлено в игру!"
    elif o["kind"] == "withdraw":
        db("UPDATE users SET balance=balance+? WHERE id=?", (o["gold"], o["user_id"]))
        text = f"❌ Заявка #{oid} отклонена, голда вернулась на баланс."
    elif ok:
        text = f"✅ Заявка #{oid} выполнена, выплата отправлена."
    else:
        text = f"❌ Заявка #{oid} отклонена. Напиши в поддержку."
    await bot.send_message(o["user_id"], text)
    await c.message.edit_text(c.message.html_text + f"\n\n{'✅ Выполнено' if ok else '❌ Отклонено'}")
    await c.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
