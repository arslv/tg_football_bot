from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite
from datetime import date, timedelta

from config import ROLE_CASHIER
from database import db
from keyboards import get_back_button, get_cashier_menu
from states import CashierStates

cashier_router = Router()


@cashier_router.callback_query(F.data == "accept_money")
async def accept_money_handler(callback: CallbackQuery):
    """Принять деньги от тренеров"""
    # Получаем всех тренеров, у которых есть деньги
    trainers_with_money = await db.get_all_payments_with_trainer()

    if not trainers_with_money:
        await callback.message.edit_text(
            "❌ Нет тренеров с деньгами для сдачи в кассу.",
            reply_markup=get_back_button()
        )
        return

    # Группируем платежи по тренерам
    trainers_summary = {}
    for payment in trainers_with_money:
        trainer_name = payment['trainer_name']
        if trainer_name not in trainers_summary:
            trainers_summary[trainer_name] = {
                'trainer_id': payment['trainer_id'],
                'total_amount': 0,
                'payments_count': 0
            }
        trainers_summary[trainer_name]['total_amount'] += payment['amount']
        trainers_summary[trainer_name]['payments_count'] += 1

    keyboard = InlineKeyboardBuilder()
    for trainer_name, summary in trainers_summary.items():
        keyboard.row(
            InlineKeyboardButton(
                text=f"💰 {trainer_name} ({summary['total_amount']:.0f} руб.)",
                callback_data=f"accept_from_trainer_{summary['trainer_id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        "💰 Выберите тренера для принятия денег:",
        reply_markup=keyboard.as_markup()
    )


@cashier_router.callback_query(F.data.startswith("accept_from_trainer_"))
async def accept_from_trainer(callback: CallbackQuery, state: FSMContext):
    """Подтверждение принятия денег от тренера"""
    trainer_id = int(callback.data.split("_")[3])

    # Получаем платежи этого тренера
    payments = await db.get_payments_with_trainer(trainer_id)
    if not payments:
        await callback.message.edit_text(
            "❌ У этого тренера нет денег для сдачи.",
            reply_markup=get_back_button()
        )
        return

    total_amount = sum(payment['amount'] for payment in payments)
    trainer_name = payments[0]['trainer_name']

    await state.update_data(trainer_id=trainer_id, total_amount=total_amount, trainer_name=trainer_name)
    await state.set_state(CashierStates.confirming_payment_receipt)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Подтвердить получение", callback_data="confirm_money_receipt"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")
    )

    await callback.message.edit_text(
        f"💰 Подтвердить получение денег?\n\n"
        f"👨‍🏫 Тренер: {trainer_name}\n"
        f"💵 Сумма: {total_amount:.0f} руб.\n"
        f"📋 Платежей: {len(payments)}",
        reply_markup=keyboard.as_markup()
    )


@cashier_router.callback_query(F.data == "confirm_money_receipt", StateFilter(CashierStates.confirming_payment_receipt))
async def confirm_money_receipt(callback: CallbackQuery, state: FSMContext):
    """Подтверждение получения денег"""
    data = await state.get_data()

    # Переводим все платежи тренера в кассу
    await db.move_payments_to_cashbox(data['trainer_id'])

    # Отправляем уведомление главному тренеру
    from notifications import NotificationService
    from handlers import notification_service
    if notification_service:
        await notification_service.notify_money_to_cashbox(data['trainer_id'], data['total_amount'])

    await callback.message.edit_text(
        f"✅ Деньги приняты!\n\n"
        f"👨‍🏫 Тренер: {data['trainer_name']}\n"
        f"💰 Сумма: {data['total_amount']:.0f} руб.\n"
        f"📅 Время: {date.today().strftime('%d.%m.%Y')}",
        reply_markup=get_cashier_menu()
    )

    await state.clear()


@cashier_router.callback_query(F.data == "pending_payments")
async def pending_payments_handler(callback: CallbackQuery):
    """Список всех непереданных сумм"""
    trainers_with_money = await db.get_all_payments_with_trainer()

    if not trainers_with_money:
        await callback.message.edit_text(
            "✅ Все деньги сданы в кассу!",
            reply_markup=get_back_button()
        )
        return

    # Группируем по тренерам
    trainers_summary = {}
    for payment in trainers_with_money:
        trainer_name = payment['trainer_name']
        if trainer_name not in trainers_summary:
            trainers_summary[trainer_name] = {'total': 0, 'count': 0, 'payments': []}
        trainers_summary[trainer_name]['total'] += payment['amount']
        trainers_summary[trainer_name]['count'] += 1
        trainers_summary[trainer_name]['payments'].append(payment)

    text = "💰 Непереданные суммы:\n\n"
    total_all = 0

    for trainer_name, summary in trainers_summary.items():
        text += f"👨‍🏫 {trainer_name}\n"
        text += f"   💵 {summary['total']:.0f} руб. ({summary['count']} платежей)\n"

        # Показываем детали по каждому платежу
        for payment in summary['payments'][:3]:  # Показываем только первые 3
            text += f"   • {payment['child_name']}: {payment['amount']:.0f} руб.\n"
        if len(summary['payments']) > 3:
            text += f"   • ... и ещё {len(summary['payments']) - 3}\n"
        text += "\n"
        total_all += summary['total']

    text += f"💎 Общая сумма: {total_all:.0f} руб."

    await callback.message.edit_text(text, reply_markup=get_back_button())


@cashier_router.callback_query(F.data == "financial_report")
async def financial_report_handler(callback: CallbackQuery):
    """Финансовый отчёт кассира"""
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Деньги в кассе всего
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'in_cashbox'"
        ) as cursor:
            total_in_cashbox = (await cursor.fetchone())[0]

        # Деньги у тренеров
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'with_trainer'"
        ) as cursor:
            total_with_trainers = (await cursor.fetchone())[0]

        # Сдано в кассу сегодня
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'in_cashbox' AND DATE(cashbox_date) = ?",
                (today.isoformat(),)
        ) as cursor:
            today_cashbox = (await cursor.fetchone())[0]

        # Сдано за неделю
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'in_cashbox' AND DATE(cashbox_date) >= ?",
                (week_ago.isoformat(),)
        ) as cursor:
            week_cashbox = (await cursor.fetchone())[0]

        # Сдано за месяц
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'in_cashbox' AND DATE(cashbox_date) >= ?",
                (month_ago.isoformat(),)
        ) as cursor:
            month_cashbox = (await cursor.fetchone())[0]

    text = (
        f"📊 Финансовый отчёт\n\n"
        f"💰 Всего в кассе: {total_in_cashbox:.0f} руб.\n"
        f"👨‍🏫 У тренеров: {total_with_trainers:.0f} руб.\n"
        f"💎 Общая сумма: {total_in_cashbox + total_with_trainers:.0f} руб.\n\n"
        f"📅 Поступления:\n"
        f"   Сегодня: {today_cashbox:.0f} руб.\n"
        f"   За неделю: {week_cashbox:.0f} руб.\n"
        f"   За месяц: {month_cashbox:.0f} руб."
    )

    await callback.message.edit_text(text, reply_markup=get_back_button())