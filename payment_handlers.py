from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite
from datetime import date

from config import ROLE_TRAINER
from database import db
from keyboards import get_back_button, get_trainer_menu, get_amount_keyboard, get_month_keyboard
from states import PaymentStates

payment_router = Router()


@payment_router.callback_query(F.data == "payment")
async def payment_handler(callback: CallbackQuery):
    """Отметка оплаты - исправленная версия"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден", reply_markup=get_back_button())
        return

    trainer = await db.get_trainer_by_user_id(user['id'])
    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    # Получаем детей всех групп тренера одним запросом с именами групп
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.id, c.full_name, c.parent_id, c.group_id, c.created_at,
                          u.telegram_id as parent_telegram_id, u.first_name as parent_name,
                          g.name as group_name
                   FROM children c 
                   JOIN users u ON c.parent_id = u.id 
                   JOIN groups_table g ON c.group_id = g.id
                   WHERE g.trainer_id = ?
                   ORDER BY g.name, c.full_name""", (trainer['id'],)
        ) as cursor:
            all_children = await cursor.fetchall()

    if not all_children:
        await callback.message.edit_text(
            "В ваших группах нет детей.",
            reply_markup=get_back_button()
        )
        return

    keyboard = InlineKeyboardBuilder()
    for child in all_children:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👶 {child['full_name']} ({child['group_name']})",
                callback_data=f"payment_child_{child['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        "💰 Выберите ребёнка для отметки оплаты:",
        reply_markup=keyboard.as_markup()
    )


@payment_router.callback_query(F.data.startswith("payment_child_"))
async def select_child_for_payment(callback: CallbackQuery, state: FSMContext):
    """Выбор ребёнка для оплаты"""
    child_id = int(callback.data.split("_")[2])

    # Получаем информацию о ребёнке
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.full_name, g.name as group_name 
                   FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   WHERE c.id = ?""", (child_id,)
        ) as cursor:
            child_info = await cursor.fetchone()

    if not child_info:
        await callback.message.edit_text("Ребёнок не найден", reply_markup=get_back_button())
        return

    await state.update_data(child_id=child_id, child_name=child_info['full_name'], group_name=child_info['group_name'])
    await state.set_state(PaymentStates.waiting_for_amount)

    await callback.message.edit_text(
        f"👶 Ребёнок: {child_info['full_name']}\n"
        f"👥 Группа: {child_info['group_name']}\n\n"
        f"💰 Выберите или введите сумму оплаты:",
        reply_markup=get_amount_keyboard()
    )


@payment_router.callback_query(F.data.startswith("amount_"), StateFilter(PaymentStates.waiting_for_amount))
async def select_amount(callback: CallbackQuery, state: FSMContext):
    """Выбор суммы оплаты"""
    amount = int(callback.data.split("_")[1])
    data = await state.get_data()

    await state.update_data(amount=amount)
    await state.set_state(PaymentStates.waiting_for_month)

    await callback.message.edit_text(
        f"👶 Ребёнок: {data['child_name']}\n"
        f"💰 Сумма: {amount} сум\n\n"
        f"📅 За какой месяц оплата?",
        reply_markup=get_month_keyboard()
    )


@payment_router.callback_query(F.data == "custom_amount", StateFilter(PaymentStates.waiting_for_amount))
async def custom_amount_handler(callback: CallbackQuery, state: FSMContext):
    """Ввод произвольной суммы"""
    await state.set_state(PaymentStates.waiting_for_custom_amount)

    await callback.message.edit_text(
        "💰 Введите сумму оплаты (только число):",
        reply_markup=get_back_button()
    )


@payment_router.message(StateFilter(PaymentStates.waiting_for_custom_amount))
async def process_custom_amount(message: Message, state: FSMContext):
    """Обработка произвольной суммы"""
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("Сумма должна быть больше 0. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("Введите корректную сумму (только число). Попробуйте снова:")
        return

    data = await state.get_data()
    await state.update_data(amount=amount)
    await state.set_state(PaymentStates.waiting_for_month)

    await message.answer(
        f"👶 Ребёнок: {data['child_name']}\n"
        f"💰 Сумма: {amount:.0f} сум\n\n"
        f"📅 За какой месяц оплата?",
        reply_markup=get_month_keyboard()
    )


@payment_router.callback_query(F.data.startswith("month_"), StateFilter(PaymentStates.waiting_for_month))
async def select_month(callback: CallbackQuery, state: FSMContext):
    """Выбор месяца оплаты"""
    month_year = callback.data.split("_")[1]  # Формат: 2025-01
    data = await state.get_data()

    await state.update_data(month_year=month_year)
    await state.set_state(PaymentStates.confirming_payment)

    # Парсим месяц для читаемого формата
    year, month = month_year.split('-')
    months_ru = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = months_ru.get(month, month)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_payment"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")
    )

    await callback.message.edit_text(
        f"💰 Подтверждение оплаты\n\n"
        f"👶 Ребёнок: {data['child_name']}\n"
        f"👥 Группа: {data['group_name']}\n"
        f"💵 Сумма: {data['amount']:.0f} сум\n"
        f"📅 За период: {month_name} {year}\n\n"
        f"Подтвердите получение оплаты:",
        reply_markup=keyboard.as_markup()
    )


@payment_router.callback_query(F.data == "confirm_payment", StateFilter(PaymentStates.confirming_payment))
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    """Подтверждение оплаты"""
    data = await state.get_data()
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    trainer = await db.get_trainer_by_user_id(user['id'])

    # Создаём запись об оплате
    payment_id = await db.create_payment(
        data['child_id'],
        trainer['id'],
        data['amount'],
        data['month_year']
    )

    # Отправляем уведомления
    try:
        from handlers_complete_fixed import notification_service
        if notification_service:
            await notification_service.notify_payment_received(
                data['child_id'],
                data['amount'],
                data['month_year']
            )
    except ImportError:
        # Если не удается импортировать, продолжаем без уведомлений
        pass

    # Парсим месяц для отображения
    year, month = data['month_year'].split('-')
    months_ru = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = months_ru.get(month, month)

    await callback.message.edit_text(
        f"✅ Оплата зафиксирована!\n\n"
        f"👶 Ребёнок: {data['child_name']}\n"
        f"💰 Сумма: {data['amount']:.0f} сум\n"
        f"📅 За период: {month_name} {year}\n"
        f"🕐 Время: {date.today().strftime('%d.%m.%Y')}\n\n"
        f"Родители получили уведомление об оплате.",
        reply_markup=get_trainer_menu()
    )

    await state.clear()


@payment_router.callback_query(F.data == "to_cashbox")
async def to_cashbox_handler(callback: CallbackQuery):
    """Сдать деньги в кассу"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден", reply_markup=get_back_button())
        return

    trainer = await db.get_trainer_by_user_id(user['id'])
    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    # Получаем все платежи у тренера
    payments = await db.get_payments_with_trainer(trainer['id'])

    if not payments:
        await callback.message.edit_text(
            "У вас нет денег для сдачи в кассу.",
            reply_markup=get_back_button()
        )
        return

    total_amount = sum(payment['amount'] for payment in payments)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Сдать в кассу", callback_data="confirm_cashbox"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")
    )

    text = f"💵 Сдача денег в кассу\n\n"
    text += f"💰 Общая сумма: {total_amount:.0f} сум\n"
    text += f"📋 Платежей: {len(payments)}\n\n"
    text += f"Детали:\n"

    for payment in payments[:5]:  # Показываем только первые 5
        text += f"• {payment['child_name']}: {payment['amount']:.0f} сум\n"

    if len(payments) > 5:
        text += f"• ... и ещё {len(payments) - 5}\n"

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


@payment_router.callback_query(F.data == "confirm_cashbox")
async def confirm_cashbox(callback: CallbackQuery):
    """Подтверждение сдачи в кассу"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    trainer = await db.get_trainer_by_user_id(user['id'])

    # Получаем сумму перед переводом
    payments = await db.get_payments_with_trainer(trainer['id'])
    total_amount = sum(payment['amount'] for payment in payments)

    if total_amount == 0:
        await callback.message.edit_text(
            "Нет денег для сдачи.",
            reply_markup=get_back_button()
        )
        return

    # Переводим все платежи в кассу
    await db.move_payments_to_cashbox(trainer['id'])

    # Отправляем уведомление
    try:
        from handlers_complete_fixed import notification_service
        if notification_service:
            await notification_service.notify_money_to_cashbox(trainer['id'], total_amount)
    except ImportError:
        # Если не удается импортировать, продолжаем без уведомлений
        pass

    await callback.message.edit_text(
        f"✅ Деньги сданы в кассу!\n\n"
        f"💰 Сумма: {total_amount:.0f} сум\n"
        f"📅 Дата: {date.today().strftime('%d.%m.%Y')}\n\n"
        f"Администратор получил уведомление.",
        reply_markup=get_trainer_menu()
    )