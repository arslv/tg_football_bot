from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite
from datetime import date, timedelta, datetime

from config import ROLE_PARENT
from database import db
from keyboards import get_back_button, get_parent_menu
from states import ParentStates

parent_router = Router()


@parent_router.callback_query(F.data == "my_children")
async def my_children_handler(callback: CallbackQuery):
    """Мои дети с кнопкой добавления"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    children = await db.get_children_by_parent(user['id'])

    if not children:
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="add_child_request")
        )
        keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

        await callback.message.edit_text(
            "У вас нет зарегистрированных детей.\n\n"
            "Вы можете отправить запрос администратору на добавление ребёнка.",
            reply_markup=keyboard.as_markup()
        )
        return

    text = "👶 Ваши дети:\n\n"
    for child in children:
        text += f"• {child['full_name']}\n"
        text += f"  👥 Группа: {child['group_name']}\n"
        text += f"  🏢 Филиал: {child['branch_name']}\n\n"

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="add_child_request")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


@parent_router.callback_query(F.data == "add_child_request")
async def add_child_request_handler(callback: CallbackQuery, state: FSMContext):
    """Запрос на добавление ребёнка"""
    await state.set_state(ParentStates.requesting_child_name)

    await callback.message.edit_text(
        "➕ Запрос на добавление ребёнка\n\n"
        "Введите полное имя ребёнка:",
        reply_markup=get_back_button()
    )


@parent_router.message(StateFilter(ParentStates.requesting_child_name))
async def process_child_name_request(message: Message, state: FSMContext):
    """Обработка имени ребёнка для запроса"""
    child_name = message.text.strip()
    user = await db.get_user_by_telegram_id(message.from_user.id)

    # Отправляем уведомление администраторам (главным тренерам)
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
        ) as cursor:
            main_trainers = await cursor.fetchall()

    parent_name = f"{user['first_name']} {user['last_name']}"
    username = f"@{user['username']}" if user['username'] else "нет username"

    notification = (
        f"👶 Запрос на добавление ребёнка\n\n"
        f"👤 Родитель: {parent_name} ({username})\n"
        f"👶 Имя ребёнка: {child_name}\n\n"
        f"Используйте админ-панель для добавления ребёнка в группу."
    )

    # Отправляем уведомления всем главным тренерам
    sent_count = 0
    for trainer in main_trainers:
        try:
            await message.bot.send_message(trainer['telegram_id'], notification)
            sent_count += 1
        except Exception as e:
            print(f"Ошибка отправки уведомления главному тренеру {trainer['telegram_id']}: {e}")

    if sent_count > 0:
        await message.answer(
            f"✅ Запрос отправлен!\n\n"
            f"👶 Имя ребёнка: {child_name}\n\n"
            f"Администратор получил ваш запрос и добавит ребёнка в группу.",
            reply_markup=get_parent_menu()
        )
    else:
        await message.answer(
            f"⚠️ Запрос сохранён, но не удалось отправить уведомление администратору.\n\n"
            f"👶 Имя ребёнка: {child_name}\n\n"
            f"Пожалуйста, свяжитесь с администратором напрямую.",
            reply_markup=get_parent_menu()
        )

    await state.clear()


@parent_router.callback_query(F.data == "attendance_history")
async def attendance_history_handler(callback: CallbackQuery):
    """История посещаемости"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    children = await db.get_children_by_parent(user['id'])

    if not children:
        await callback.message.edit_text(
            "❌ У вас нет зарегистрированных детей.",
            reply_markup=get_back_button()
        )
        return

    if len(children) == 1:
        # Если ребёнок один, сразу показываем его посещаемость
        await show_child_attendance(callback, children[0]['id'], children[0]['full_name'])
    else:
        # Если детей несколько, даём выбрать
        keyboard = InlineKeyboardBuilder()
        for child in children:
            keyboard.row(
                InlineKeyboardButton(
                    text=f"👶 {child['full_name']}",
                    callback_data=f"child_attendance_{child['id']}"
                )
            )
        keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

        await callback.message.edit_text(
            "👶 Выберите ребёнка для просмотра посещаемости:",
            reply_markup=keyboard.as_markup()
        )


@parent_router.callback_query(F.data.startswith("child_attendance_"))
async def child_attendance_handler(callback: CallbackQuery):
    """Показать посещаемость конкретного ребёнка"""
    child_id = int(callback.data.split("_")[2])

    # Получаем информацию о ребёнке
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT full_name FROM children WHERE id = ?", (child_id,)
        ) as cursor:
            child = await cursor.fetchone()

    if child:
        await show_child_attendance(callback, child_id, child['full_name'])


async def show_child_attendance(callback: CallbackQuery, child_id: int, child_name: str):
    """Показать посещаемость ребёнка за последний месяц"""
    month_ago = date.today() - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Получаем посещаемость за последний месяц
        async with conn.execute(
                """SELECT a.status, s.type, s.start_time, g.name as group_name, t.full_name as trainer_name
                   FROM attendance a
                   JOIN sessions s ON a.session_id = s.id
                   JOIN groups_table g ON s.group_id = g.id
                   JOIN trainers t ON s.trainer_id = t.id
                   WHERE a.child_id = ? AND DATE(s.start_time) >= ?
                   ORDER BY s.start_time DESC
                   LIMIT 20""", (child_id, month_ago.isoformat())
        ) as cursor:
            attendance_records = await cursor.fetchall()

        # Статистика
        async with conn.execute(
                """SELECT 
                       COUNT(*) as total_sessions,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present_count
                   FROM attendance a
                   JOIN sessions s ON a.session_id = s.id
                   WHERE a.child_id = ? AND DATE(s.start_time) >= ?""", (child_id, month_ago.isoformat())
        ) as cursor:
            stats = await cursor.fetchone()

    if not attendance_records:
        await callback.message.edit_text(
            f"👶 {child_name}\n\n"
            f"❌ За последний месяц записей о посещаемости нет.",
            reply_markup=get_back_button()
        )
        return

    total_sessions = stats['total_sessions']
    present_count = stats['present_count']
    attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0

    text = (
        f"👶 {child_name}\n"
        f"📊 Посещаемость за месяц\n\n"
        f"📈 Статистика:\n"
        f"   Всего занятий: {total_sessions}\n"
        f"   Присутствовал: {present_count}\n"
        f"   Процент посещения: {attendance_rate:.1f}%\n\n"
        f"📋 Последние занятия:\n"
    )

    for record in attendance_records[:10]:  # Показываем только последние 10
        start_time = record['start_time']
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)

        status_emoji = "✅" if record['status'] == 'present' else "❌"
        session_type = "🏃 Тренировка" if record['type'] == 'training' else "⚽ Игра"

        text += f"{status_emoji} {start_time.strftime('%d.%m')} - {session_type}\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())


@parent_router.callback_query(F.data == "payment_history")
async def payment_history_handler(callback: CallbackQuery):
    """История оплат"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    children = await db.get_children_by_parent(user['id'])

    if not children:
        await callback.message.edit_text(
            "❌ У вас нет зарегистрированных детей.",
            reply_markup=get_back_button()
        )
        return

    if len(children) == 1:
        # Если ребёнок один, сразу показываем его оплаты
        await show_child_payments(callback, children[0]['id'], children[0]['full_name'])
    else:
        # Если детей несколько, даём выбрать
        keyboard = InlineKeyboardBuilder()
        for child in children:
            keyboard.row(
                InlineKeyboardButton(
                    text=f"👶 {child['full_name']}",
                    callback_data=f"child_payments_{child['id']}"
                )
            )
        keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

        await callback.message.edit_text(
            "👶 Выберите ребёнка для просмотра истории оплат:",
            reply_markup=keyboard.as_markup()
        )


@parent_router.callback_query(F.data.startswith("child_payments_"))
async def child_payments_handler(callback: CallbackQuery):
    """Показать оплаты конкретного ребёнка"""
    child_id = int(callback.data.split("_")[2])

    # Получаем информацию о ребёнке
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT full_name FROM children WHERE id = ?", (child_id,)
        ) as cursor:
            child = await cursor.fetchone()

    if child:
        await show_child_payments(callback, child_id, child['full_name'])


async def show_child_payments(callback: CallbackQuery, child_id: int, child_name: str):
    """Показать историю оплат ребёнка"""
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Получаем все платежи ребёнка
        async with conn.execute(
                """SELECT p.amount, p.month_year, p.payment_date, p.status, p.cashbox_date,
                          t.full_name as trainer_name
                   FROM payments p
                   JOIN trainers t ON p.trainer_id = t.id
                   WHERE p.child_id = ?
                   ORDER BY p.payment_date DESC""", (child_id,)
        ) as cursor:
            payments = await cursor.fetchall()

        # Статистика
        async with conn.execute(
                """SELECT 
                       COUNT(*) as total_payments,
                       SUM(amount) as total_amount,
                       SUM(CASE WHEN status = 'in_cashbox' THEN amount ELSE 0 END) as paid_amount
                   FROM payments
                   WHERE child_id = ?""", (child_id,)
        ) as cursor:
            stats = await cursor.fetchone()

    if not payments:
        await callback.message.edit_text(
            f"👶 {child_name}\n\n"
            f"❌ История оплат пуста.",
            reply_markup=get_back_button()
        )
        return

    total_payments = stats['total_payments']
    total_amount = stats['total_amount']
    paid_amount = stats['paid_amount']
    pending_amount = total_amount - paid_amount

    text = (
        f"👶 {child_name}\n"
        f"💰 История оплат\n\n"
        f"📊 Статистика:\n"
        f"   Всего платежей: {total_payments}\n"
        f"   Общая сумма: {total_amount:.0f} сум\n"
        f"   Сдано в кассу: {paid_amount:.0f} сум\n"
        f"   У тренера: {pending_amount:.0f} сум\n\n"
        f"📋 Последние платежи:\n"
    )

    # Парсим месяцы для читаемого формата
    months_ru = {
        '01': 'Янв', '02': 'Фев', '03': 'Мар', '04': 'Апр',
        '05': 'Май', '06': 'Июн', '07': 'Июл', '08': 'Авг',
        '09': 'Сен', '10': 'Окт', '11': 'Ноя', '12': 'Дек'
    }

    for payment in payments[:10]:  # Показываем только последние 10
        payment_date = payment['payment_date']
        if isinstance(payment_date, str):
            payment_date = datetime.fromisoformat(payment_date)

        year, month = payment['month_year'].split('-')
        month_name = months_ru.get(month, month)

        status_emoji = "✅" if payment['status'] == 'in_cashbox' else "⏳"
        status_text = "В кассе" if payment['status'] == 'in_cashbox' else "У тренера"

        text += (
            f"{status_emoji} {payment['amount']:.0f} сум - {month_name} {year}\n"
            f"   {payment_date.strftime('%d.%m.%Y')} - {status_text}\n"
        )

    await callback.message.edit_text(text, reply_markup=get_back_button())