from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite

from config import ROLE_PARENT
from database import db
from keyboards import get_back_button, get_parent_menu
from states import ParentStates

parent_edit_router = Router()


# РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ДЕТЕЙ РОДИТЕЛЯМИ

@parent_edit_router.callback_query(F.data == "my_children")
async def my_children_with_edit(callback: CallbackQuery):
    """Мои дети с возможностью редактирования"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    children = await db.get_children_by_parent(user['id'])

    if not children:
        await callback.message.edit_text(
            "У вас нет зарегистрированных детей.",
            reply_markup=get_back_button()
        )
        return

    keyboard = InlineKeyboardBuilder()
    for child in children:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👶 {child['full_name']} - {child['group_name']}",
                callback_data=f"my_child_info_{child['id']}"
            )
        )
    keyboard.row(
        InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="add_child_request"),
        InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")
    )

    await callback.message.edit_text(
        "👶 Ваши дети (нажмите для просмотра/редактирования):",
        reply_markup=keyboard.as_markup()
    )


@parent_edit_router.callback_query(F.data.startswith("my_child_info_"))
async def my_child_info(callback: CallbackQuery):
    """Информация о моём ребёнке с кнопками редактирования"""
    child_id = int(callback.data.split("_")[3])
    user = await db.get_user_by_telegram_id(callback.from_user.id)

    # Проверяем, что это действительно ребёнок этого родителя
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.full_name, g.name as group_name, b.name as branch_name,
                          t.full_name as trainer_name, c.created_at
                   FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   JOIN branches b ON g.branch_id = b.id
                   JOIN trainers t ON g.trainer_id = t.id
                   WHERE c.id = ? AND c.parent_id = ?""", (child_id, user['id'])
        ) as cursor:
            child = await cursor.fetchone()

        if not child:
            await callback.message.edit_text(
                "Ребёнок не найден или не принадлежит вам.",
                reply_markup=get_back_button()
            )
            return

        # Получаем статистику посещаемости за последний месяц
        from datetime import date, timedelta
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

    total_sessions = stats['total_sessions'] or 0
    present_count = stats['present_count'] or 0
    attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0

    total_payments = payment_stats['total_payments'] or 0
    total_amount = payment_stats['total_amount'] or 0
    paid_amount = payment_stats['paid_amount'] or 0

    text = (
        f"👶 {child['full_name']}\n\n"
        f"👥 Группа: {child['group_name']}\n"
        f"👨‍🏫 Тренер: {child['trainer_name']}\n"
        f"🏢 Филиал: {child['branch_name']}\n\n"
        f"📊 Посещаемость за месяц:\n"
        f"   Всего занятий: {total_sessions}\n"
        f"   Посетил: {present_count}\n"
        f"   Процент: {attendance_rate:.1f}%\n\n"
        f"💰 Платежи:\n"
        f"   Всего: {total_amount:.0f} руб. ({total_payments} платежей)\n"
        f"   Сдано в кассу: {paid_amount:.0f} руб."
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✏️ Изменить имя", callback_data=f"edit_my_child_name_{child_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_my_child_{child_id}")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 История посещений", callback_data=f"child_attendance_{child_id}"),
        InlineKeyboardButton(text="💰 История оплат", callback_data=f"child_payments_{child_id}")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="my_children"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


@parent_edit_router.callback_query(F.data.startswith("edit_my_child_name_"))
async def edit_my_child_name_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования имени моего ребёнка"""
    child_id = int(callback.data.split("_")[4])
    user = await db.get_user_by_telegram_id(callback.from_user.id)

    # Проверяем права доступа
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT full_name FROM children WHERE id = ? AND parent_id = ?",
                (child_id, user['id'])
        ) as cursor:
            child = await cursor.fetchone()

    if not child:
        await callback.message.edit_text(
            "Ребёнок не найден или не принадлежит вам.",
            reply_markup=get_back_button()
        )
        return

    await state.update_data(editing_my_child_id=child_id, current_child_name=child['full_name'])
    await state.set_state(ParentStates.editing_child_name)

    await callback.message.edit_text(
        f"✏️ Редактирование имени ребёнка\n\n"
        f"Текущее имя: {child['full_name']}\n\n"
        f"Введите новое полное имя ребёнка:",
        reply_markup=get_back_button()
    )


@parent_edit_router.message(StateFilter(ParentStates.editing_child_name))
async def process_edit_my_child_name(message: Message, state: FSMContext):
    """Обработка нового имени ребёнка"""
    new_name = message.text.strip()
    data = await state.get_data()
    user = await db.get_user_by_telegram_id(message.from_user.id)

    # Обновляем имя ребёнка
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            "UPDATE children SET full_name = ? WHERE id = ? AND parent_id = ?",
            (new_name, data['editing_my_child_id'], user['id'])
        )
        await conn.commit()

    # Уведомляем администратора об изменении
    from handlers import notification_service
    if notification_service:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
            ) as cursor:
                main_trainers = await cursor.fetchall()

        for trainer in main_trainers:
            try:
                await notification_service.bot.send_message(
                    trainer['telegram_id'],
                    f"📝 Родитель изменил имя ребёнка\n\n"
                    f"👤 Родитель: {user['first_name']} {user['last_name']}\n"
                    f"👶 Старое имя: {data['current_child_name']}\n"
                    f"👶 Новое имя: {new_name}"
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления главному тренеру: {e}")

    await message.answer(
        f"✅ Имя ребёнка обновлено!\n\n"
        f"👶 Старое имя: {data['current_child_name']}\n"
        f"👶 Новое имя: {new_name}\n\n"
        f"Администратор получил уведомление об изменении.",
        reply_markup=get_parent_menu()
    )

    await state.clear()


@parent_edit_router.callback_query(F.data.startswith("delete_my_child_"))
async def delete_my_child_confirm(callback: CallbackQuery):
    """Подтверждение удаления моего ребёнка"""
    child_id = int(callback.data.split("_")[3])
    user = await db.get_user_by_telegram_id(callback.from_user.id)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.full_name, g.name as group_name
                   FROM children c
                   JOIN groups_table g ON c.group_id = g.id
                   WHERE c.id = ? AND c.parent_id = ?""", (child_id, user['id'])
        ) as cursor:
            child = await cursor.fetchone()

        # Проверяем связанные данные
        async with conn.execute("SELECT COUNT(*) FROM attendance WHERE child_id = ?", (child_id,)) as cursor:
            attendance_count = (await cursor.fetchone())[0]

        async with conn.execute("SELECT COUNT(*) FROM payments WHERE child_id = ?", (child_id,)) as cursor:
            payments_count = (await cursor.fetchone())[0]

    if not child:
        await callback.message.edit_text(
            "Ребёнок не найден или не принадлежит вам.",
            reply_markup=get_back_button()
        )
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_my_child_{child_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"my_child_info_{child_id}")
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


@parent_edit_router.callback_query(F.data.startswith("confirm_delete_my_child_"))
async def confirm_delete_my_child(callback: CallbackQuery):
    """Подтверждённое удаление моего ребёнка"""
    child_id = int(callback.data.split("_")[4])
    user = await db.get_user_by_telegram_id(callback.from_user.id)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT full_name FROM children WHERE id = ? AND parent_id = ?",
                (child_id, user['id'])
        ) as cursor:
            child = await cursor.fetchone()

        if child:
            await conn.execute("DELETE FROM children WHERE id = ? AND parent_id = ?", (child_id, user['id']))
            await conn.commit()

    # Уведомляем администратора об удалении
    from handlers import notification_service
    if notification_service:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
            ) as cursor:
                main_trainers = await cursor.fetchall()

        for trainer in main_trainers:
            try:
                await notification_service.bot.send_message(
                    trainer['telegram_id'],
                    f"🗑 Родитель удалил ребёнка\n\n"
                    f"👤 Родитель: {user['first_name']} {user['last_name']} (@{user['username'] or 'нет'})\n"
                    f"👶 Удалён ребёнок: {child['full_name']}"
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления главному тренеру: {e}")

    await callback.message.edit_text(
        f"✅ Ребёнок '{child['full_name']}' удален из системы.\n\n"
        f"Администратор получил уведомление.",
        reply_markup=get_parent_menu()
    )