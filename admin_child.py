from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite
from datetime import date, timedelta

from config import ROLE_MAIN_TRAINER
from database import db
from keyboards import get_back_button, get_main_trainer_menu
from states import AdminStates

child_info_router = Router()


# Функция для проверки прав главного тренера
async def is_main_trainer(telegram_id: int) -> bool:
    """Проверка, является ли пользователь главным тренером"""
    user = await db.get_user_by_telegram_id(telegram_id)
    return user and user['role'] == ROLE_MAIN_TRAINER


@child_info_router.callback_query(F.data.startswith("child_info_"))
async def child_info_with_actions(callback: CallbackQuery):
    """Информация о ребёнке с кнопками редактирования (удаление только для главного тренера)"""
    child_id = int(callback.data.split("_")[2])
    is_main = await is_main_trainer(callback.from_user.id)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.*, g.name as group_name, b.name as branch_name, t.full_name as trainer_name,
                          u.first_name || ' ' || u.last_name as parent_name, u.username as parent_username
                   FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   JOIN branches b ON g.branch_id = b.id 
                   JOIN trainers t ON g.trainer_id = t.id 
                   JOIN users u ON c.parent_id = u.id
                   WHERE c.id = ?""", (child_id,)
        ) as cursor:
            child = await cursor.fetchone()

        # Получаем статистику посещаемости
        month_ago = date.today() - timedelta(days=30)

        async with conn.execute(
                """SELECT 
                       COUNT(*) as total_sessions,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present_count
                   FROM attendance a
                   JOIN sessions s ON a.session_id = s.id
                   WHERE a.child_id = ? AND DATE(s.start_time) >= ?""", (child_id, month_ago.isoformat())
        ) as cursor:
            stats = await cursor.fetchone()

        # Получаем информацию о платежах
        async with conn.execute(
                """SELECT 
                       COUNT(*) as total_payments,
                       SUM(amount) as total_amount,
                       SUM(CASE WHEN status = 'in_cashbox' THEN amount ELSE 0 END) as paid_amount
                   FROM payments WHERE child_id = ?""", (child_id,)
        ) as cursor:
            payment_stats = await cursor.fetchone()

    if not child:
        await callback.message.edit_text("Ребёнок не найден", reply_markup=get_back_button())
        return

    total_sessions = stats['total_sessions'] or 0
    present_count = stats['present_count'] or 0
    attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0

    total_payments = payment_stats['total_payments'] or 0
    total_amount = payment_stats['total_amount'] or 0
    paid_amount = payment_stats['paid_amount'] or 0

    parent_info = f"{child['parent_name']}"
    if child['parent_username']:
        parent_info += f" (@{child['parent_username']})"

    text = (
        f"👶 {child['full_name']}\n\n"
        f"👤 Родитель: {parent_info}\n"
        f"👥 Группа: {child['group_name']}\n"
        f"👨‍🏫 Тренер: {child['trainer_name']}\n"
        f"🏢 Филиал: {child['branch_name']}\n\n"
        f"📊 Посещаемость за месяц:\n"
        f"   Всего занятий: {total_sessions}\n"
        f"   Посетил: {present_count}\n"
        f"   Процент: {attendance_rate:.1f}%\n\n"
        f"💰 Платежи:\n"
        f"   Всего: {total_amount:.0f} сум ({total_payments} платежей)\n"
        f"   Сдано в кассу: {paid_amount:.0f} сум"
    )

    keyboard = InlineKeyboardBuilder()

    # Кнопка редактирования доступна всем
    keyboard.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_child_{child_id}"))

    # Кнопка удаления только для главного тренера
    if is_main:
        keyboard.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_child_{child_id}"))

    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="view_children"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


# РЕДАКТИРОВАНИЕ ДЕТЕЙ (доступно всем администраторам)

@child_info_router.callback_query(
    F.data.startswith("edit_child_") & ~F.data.contains("parent") & ~F.data.contains("group"))
async def edit_child_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования ребёнка"""
    child_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.*, g.name as group_name, u.first_name || ' ' || u.last_name as parent_name
                   FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   JOIN users u ON c.parent_id = u.id
                   WHERE c.id = ?""", (child_id,)
        ) as cursor:
            child = await cursor.fetchone()

    if not child:
        await callback.message.edit_text("Ребёнок не найден", reply_markup=get_back_button())
        return

    await state.update_data(
        editing_child_id=child_id,
        current_name=child['full_name'],
        current_parent_id=child['parent_id'],
        current_group_id=child['group_id']
    )
    await state.set_state(AdminStates.editing_child_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="👤 Изменить родителя", callback_data="edit_child_parent_only"))
    keyboard.row(InlineKeyboardButton(text="👥 Изменить группу", callback_data="edit_child_group_only"))
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data=f"child_info_{child_id}"))

    await callback.message.edit_text(
        f"✏️ Редактирование ребёнка\n\n"
        f"Текущее имя: {child['full_name']}\n"
        f"Текущий родитель: {child['parent_name']}\n"
        f"Текущая группа: {child['group_name']}\n\n"
        f"Введите новое полное имя ребёнка или нажмите кнопку для изменения родителя/группы:",
        reply_markup=keyboard.as_markup()
    )


# ФУНКЦИИ УДАЛЕНИЯ (ТОЛЬКО ДЛЯ ГЛАВНОГО ТРЕНЕРА)

@child_info_router.callback_query(F.data.startswith("delete_child_"))
async def delete_child_confirm(callback: CallbackQuery):
    """Подтверждение удаления ребёнка (только для главного тренера)"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    child_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.full_name, g.name as group_name
                   FROM children c
                   JOIN groups_table g ON c.group_id = g.id
                   WHERE c.id = ?""", (child_id,)
        ) as cursor:
            child = await cursor.fetchone()

        # Проверяем связанные данные
        async with conn.execute("SELECT COUNT(*) FROM attendance WHERE child_id = ?", (child_id,)) as cursor:
            attendance_count = (await cursor.fetchone())[0]

        async with conn.execute("SELECT COUNT(*) FROM payments WHERE child_id = ?", (child_id,)) as cursor:
            payments_count = (await cursor.fetchone())[0]

    if not child:
        await callback.message.edit_text("Ребёнок не найден", reply_markup=get_back_button())
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_child_{child_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"child_info_{child_id}")
    )

    warning = ""
    if attendance_count > 0 or payments_count > 0:
        warning = f"\n\n⚠️ ВНИМАНИЕ! Это также удалит всю историю:\n• Записей посещаемости: {attendance_count}\n• Записей об оплатах: {payments_count}"

    await callback.message.edit_text(
        f"🗑 Удаление ребёнка\n\n"
        f"Вы уверены, что хотите удалить ребёнка '{child['full_name']}'?\n"
        f"Группа: {child['group_name']}{warning}\n\n"
        f"❗ Это действие нельзя отменить!",
        reply_markup=keyboard.as_markup()
    )


@child_info_router.callback_query(F.data.startswith("confirm_delete_child_"))
async def confirm_delete_child(callback: CallbackQuery):
    """Подтверждённое удаление ребёнка"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    child_id = int(callback.data.split("_")[3])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT full_name FROM children WHERE id = ?", (child_id,)) as cursor:
            child = await cursor.fetchone()

        if child:
            await conn.execute("DELETE FROM children WHERE id = ?", (child_id,))
            await conn.commit()

    await callback.message.edit_text(
        f"✅ Ребёнок '{child['full_name']}' удален из системы.",
        reply_markup=get_main_trainer_menu()
    )