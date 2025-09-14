from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Location
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime
import re
import aiosqlite

from config import ROLE_MAIN_TRAINER, ROLE_TRAINER, ROLE_PARENT, ROLE_CASHIER, ADMIN_USER_IDS
from database import db
from keyboards import *
from states import *
from notifications import NotificationService

router = Router()

# Инициализация сервиса уведомлений (будет установлен в main.py)
notification_service = None


def set_notification_service(service: NotificationService):
    global notification_service
    notification_service = service


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    await state.clear()

    user = await db.get_user_by_telegram_id(message.from_user.id)

    if not user:
        if message.from_user.id in ADMIN_USER_IDS:
            # Создаем главного тренера
            user_id = await db.create_user(
                message.from_user.id,
                message.from_user.username or "",
                message.from_user.first_name or "",
                message.from_user.last_name or "",
                ROLE_MAIN_TRAINER
            )
            await message.answer(
                f"Добро пожаловать, главный тренер!\n"
                f"Система управления футбольной академией готова к работе.",
                reply_markup=get_main_trainer_menu()
            )
        else:
            await message.answer(
                "Добро пожаловать в систему футбольной академии!\n"
                "Для регистрации используйте команду /register"
            )
        return

    # Пользователь уже зарегистрирован
    if user['role'] == ROLE_MAIN_TRAINER:
        await message.answer(
            f"Добро пожаловать, {user['first_name']}!\n"
            f"Главное меню тренера:",
            reply_markup=get_main_trainer_menu()
        )
    elif user['role'] == ROLE_TRAINER:
        await message.answer(
            f"Добро пожаловать, {user['first_name']}!\n"
            f"Меню тренера:",
            reply_markup=get_trainer_menu()
        )
    elif user['role'] == ROLE_PARENT:
        await message.answer(
            f"Добро пожаловать, {user['first_name']}!\n"
            f"Меню родителя:",
            reply_markup=get_parent_menu()
        )
    elif user['role'] == ROLE_CASHIER:
        await message.answer(
            f"Добро пожаловать, {user['first_name']}!\n"
            f"Меню кассира:",
            reply_markup=get_cashier_menu()
        )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()

    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден")
        return

    if user['role'] == ROLE_MAIN_TRAINER:
        await callback.message.edit_text(
            "Главное меню:",
            reply_markup=get_main_trainer_menu()
        )
    elif user['role'] == ROLE_TRAINER:
        await callback.message.edit_text(
            "Меню тренера:",
            reply_markup=get_trainer_menu()
        )
    elif user['role'] == ROLE_PARENT:
        await callback.message.edit_text(
            "Меню родителя:",
            reply_markup=get_parent_menu()
        )
    elif user['role'] == ROLE_CASHIER:
        await callback.message.edit_text(
            "Меню кассира:",
            reply_markup=get_cashier_menu()
        )


# ОБРАБОТЧИКИ ДЛЯ ТРЕНЕРА

@router.callback_query(F.data.in_(["start_training", "start_game"]))
async def start_session_handler(callback: CallbackQuery, state: FSMContext):
    """Начало тренировки или игры"""
    session_type = "training" if callback.data == "start_training" else "game"

    # Проверяем пользователя и тренера
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден", reply_markup=get_back_button())
        return

    trainer = await db.get_trainer_by_user_id(user['id'])
    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    # Проверяем активные сессии
    active_session = await db.get_active_session(trainer['id'])
    if active_session:
        await callback.message.edit_text(
            "У вас уже есть активное занятие! Сначала завершите его.",
            reply_markup=get_back_button()
        )
        return

    await state.update_data(session_type=session_type, trainer_id=trainer['id'])
    await state.set_state(SessionStates.waiting_for_location)

    session_name = "тренировку" if session_type == "training" else "игру"

    # Создаем inline-кнопки для запроса геолокации
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"Для начала занятия отправьте вашу геолокацию.\n\n"
        f"Это необходимо для подтверждения того, что вы проводите {session_name}.\n\n"
        f"Используйте скрепку в поле ввода сообщения и выберите 'Геопозиция'",
        reply_markup=keyboard.as_markup()
    )


@router.message(F.location, StateFilter(SessionStates.waiting_for_location))
async def process_location(message: Message, state: FSMContext):
    """Обработка геолокации"""
    data = await state.get_data()
    location = message.location

    # Получаем группы тренера
    trainer_id = data['trainer_id']
    groups = await db.get_groups_by_trainer(trainer_id)

    if not groups:
        await message.answer(
            "У вас нет закреплённых групп. Обратитесь к администратору.",
            reply_markup=get_trainer_menu()
        )
        await state.clear()
        return

    # Если группа одна, сразу создаём сессию
    if len(groups) == 1:
        group = groups[0]
        session_id = await db.create_session(
            data['session_type'], trainer_id, group['id'],
            location.latitude, location.longitude
        )

        session_name = "Тренировка" if data['session_type'] == "training" else "Игра"
        await message.answer(
            f"✅ {session_name} началась!\n"
            f"Группа: {group['name']}\n"
            f"Время: {datetime.now().strftime('%H:%M')}\n\n"
            f"Теперь проведите перекличку.",
            reply_markup=get_trainer_menu()
        )

        # Отправляем уведомления
        if notification_service:
            await notification_service.notify_session_started(session_id, data['session_type'])

        await state.clear()
    else:
        # Если групп несколько, даём выбрать
        keyboard = InlineKeyboardBuilder()
        for group in groups:
            keyboard.row(
                InlineKeyboardButton(
                    text=f"👥 {group['name']}",
                    callback_data=f"select_group_{group['id']}"
                )
            )
        keyboard.row(InlineKeyboardButton(text="Отмена", callback_data="back_to_menu"))

        await message.answer(
            "Выберите группу для занятия:",
            reply_markup=keyboard.as_markup()
        )
        await state.update_data(location_lat=location.latitude, location_lon=location.longitude)


@router.callback_query(F.data.startswith("select_group_"), StateFilter(SessionStates.waiting_for_location))
async def select_group(callback: CallbackQuery, state: FSMContext):
    """Выбор группы для занятия"""
    group_id = int(callback.data.split("_")[2])
    data = await state.get_data()

    session_id = await db.create_session(
        data['session_type'], data['trainer_id'], group_id,
        data['location_lat'], data['location_lon']
    )

    group = await db.get_group_by_id(group_id)
    session_name = "Тренировка" if data['session_type'] == "training" else "Игра"

    await callback.message.edit_text(
        f"✅ {session_name} началась!\n"
        f"Группа: {group['name']}\n"
        f"Время: {datetime.now().strftime('%H:%M')}\n\n"
        f"Теперь проведите перекличку.",
        reply_markup=get_trainer_menu()
    )

    # Отправляем уведомления
    if notification_service:
        await notification_service.notify_session_started(session_id, data['session_type'])

    await state.clear()


@router.callback_query(F.data == "attendance")
async def attendance_handler(callback: CallbackQuery):
    """Перекличка"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден", reply_markup=get_back_button())
        return

    trainer = await db.get_trainer_by_user_id(user['id'])
    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    active_session = await db.get_active_session(trainer['id'])
    if not active_session:
        await callback.message.edit_text(
            "Нет активного занятия для переклички.",
            reply_markup=get_back_button()
        )
        return

    # Получаем детей группы
    children = await db.get_children_by_group(active_session['group_id'])

    if not children:
        await callback.message.edit_text(
            "В группе нет детей.",
            reply_markup=get_back_button()
        )
        return

    await callback.message.edit_text(
        f"👥 Перекличка группы\n"
        f"Отметьте присутствие каждого ребёнка:",
        reply_markup=get_attendance_keyboard(children, active_session['id'])
    )


@router.callback_query(F.data.startswith("present_") | F.data.startswith("absent_"))
async def mark_attendance_handler(callback: CallbackQuery):
    """Отметка посещаемости"""
    parts = callback.data.split("_")
    status = parts[0]  # present или absent
    session_id = int(parts[1])
    child_id = int(parts[2])

    # Отмечаем посещаемость
    await db.mark_attendance(session_id, child_id, status)

    # Отправляем уведомление родителю
    if notification_service:
        await notification_service.notify_attendance(child_id, status, session_id)

    await callback.answer(f"✅ Отмечено: {'Присутствует' if status == 'present' else 'Отсутствует'}")


@router.callback_query(F.data == "finish_attendance")
async def finish_attendance(callback: CallbackQuery):
    """Завершение переклички"""
    await callback.message.edit_text(
        "✅ Перекличка завершена!",
        reply_markup=get_back_button()
    )


@router.callback_query(F.data == "end_session")
async def end_session_handler(callback: CallbackQuery):
    """Завершение занятия"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден", reply_markup=get_back_button())
        return

    trainer = await db.get_trainer_by_user_id(user['id'])
    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    active_session = await db.get_active_session(trainer['id'])
    if not active_session:
        await callback.message.edit_text(
            "Нет активного занятия для завершения.",
            reply_markup=get_back_button()
        )
        return

    # Завершаем сессию
    await db.end_session(active_session['id'])

    session_name = "Тренировка" if active_session['type'] == "training" else "Игра"
    await callback.message.edit_text(
        f"✅ {session_name} завершена!\n"
        f"Время завершения: {datetime.now().strftime('%H:%M')}",
        reply_markup=get_back_button()
    )

    # Отправляем уведомления
    if notification_service:
        await notification_service.notify_session_ended(active_session['id'])


@router.callback_query(F.data == "trainer_stats")
async def trainer_statistics(callback: CallbackQuery):
    """Статистика тренера"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Пользователь не найден", reply_markup=get_back_button())
        return

    trainer = await db.get_trainer_by_user_id(user['id'])
    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    from datetime import date, timedelta
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Статистика занятий тренера
        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE trainer_id = ? AND DATE(start_time) = ?",
                (trainer['id'], today.isoformat())
        ) as cursor:
            today_sessions = (await cursor.fetchone())[0]

        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE trainer_id = ? AND DATE(start_time) >= ?",
                (trainer['id'], week_ago.isoformat())
        ) as cursor:
            week_sessions = (await cursor.fetchone())[0]

        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE trainer_id = ? AND DATE(start_time) >= ?",
                (trainer['id'], month_ago.isoformat())
        ) as cursor:
            month_sessions = (await cursor.fetchone())[0]

        # Получаем оплаты у тренера
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE trainer_id = ? AND status = 'with_trainer'",
                (trainer['id'],)
        ) as cursor:
            money_with_trainer = (await cursor.fetchone())[0]

        # Всего собранных денег за месяц
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE trainer_id = ? AND payment_date >= ?",
                (trainer['id'], month_ago.isoformat())
        ) as cursor:
            month_income = (await cursor.fetchone())[0]

        # Количество детей в группах тренера
        async with conn.execute(
                """SELECT COUNT(DISTINCT c.id) 
                   FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   WHERE g.trainer_id = ?""",
                (trainer['id'],)
        ) as cursor:
            total_children = (await cursor.fetchone())[0]

        # Средняя посещаемость за месяц
        async with conn.execute(
                """SELECT ROUND(AVG(CASE WHEN a.status = 'present' THEN 100.0 ELSE 0.0 END), 1)
                   FROM attendance a 
                   JOIN sessions s ON a.session_id = s.id 
                   WHERE s.trainer_id = ? AND DATE(s.start_time) >= ?""",
                (trainer['id'], month_ago.isoformat())
        ) as cursor:
            result = await cursor.fetchone()
            avg_attendance = result[0] if result[0] is not None else 0

    text = (
        f"📊 Моя статистика\n\n"
        f"📅 Занятия сегодня: {today_sessions}\n"
        f"📅 Занятия за неделю: {week_sessions}\n"
        f"📅 Занятия за месяц: {month_sessions}\n\n"
        f"👶 Всего детей: {total_children}\n"
        f"📈 Средняя посещаемость: {avg_attendance}%\n\n"
        f"💰 Финансы:\n"
        f"   У меня: {money_with_trainer:.0f} руб.\n"
        f"   Собрано за месяц: {month_income:.0f} руб."
    )

    await callback.message.edit_text(text, reply_markup=get_back_button())


# ОБРАБОТЧИКИ ДЛЯ ГЛАВНОГО ТРЕНЕРА (основные)

@router.callback_query(F.data == "mt_statistics")
async def main_trainer_statistics(callback: CallbackQuery):
    """Статистика для главного тренера"""
    from datetime import date, timedelta

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Статистика за сегодня
        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE DATE(start_time) = ?", (today.isoformat(),)
        ) as cursor:
            today_sessions = (await cursor.fetchone())[0]

        # Статистика за неделю
        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE DATE(start_time) >= ?", (week_ago.isoformat(),)
        ) as cursor:
            week_sessions = (await cursor.fetchone())[0]

        # Статистика за месяц
        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE DATE(start_time) >= ?", (month_ago.isoformat(),)
        ) as cursor:
            month_sessions = (await cursor.fetchone())[0]

        # Активные тренеры
        async with conn.execute(
                "SELECT COUNT(*) FROM trainers t JOIN users u ON t.user_id = u.id WHERE u.is_active = TRUE"
        ) as cursor:
            active_trainers = (await cursor.fetchone())[0]

        # Всего детей
        async with conn.execute("SELECT COUNT(*) FROM children") as cursor:
            total_children = (await cursor.fetchone())[0]

        # Средняя посещаемость за месяц
        async with conn.execute(
                """SELECT ROUND(AVG(CASE WHEN a.status = 'present' THEN 100.0 ELSE 0.0 END), 1)
                   FROM attendance a 
                   JOIN sessions s ON a.session_id = s.id 
                   WHERE DATE(s.start_time) >= ?""", (month_ago.isoformat(),)
        ) as cursor:
            result = await cursor.fetchone()
            avg_attendance = result[0] if result[0] is not None else 0

    text = (
        f"📊 Статистика академии\n\n"
        f"📅 Занятия сегодня: {today_sessions}\n"
        f"📅 Занятия за неделю: {week_sessions}\n"
        f"📅 Занятия за месяц: {month_sessions}\n\n"
        f"👨‍🏫 Активные тренеры: {active_trainers}\n"
        f"👶 Всего детей: {total_children}\n"
        f"📈 Средняя посещаемость: {avg_attendance}%"
    )

    await callback.message.edit_text(text, reply_markup=get_back_button())


@router.callback_query(F.data == "mt_finance")
async def main_trainer_finance(callback: CallbackQuery):
    """Финансовая статистика"""
    from datetime import date, timedelta

    today = date.today()
    month_ago = today - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Деньги у тренеров
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'with_trainer'"
        ) as cursor:
            money_with_trainers = (await cursor.fetchone())[0]

        # Деньги в кассе
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'in_cashbox'"
        ) as cursor:
            money_in_cashbox = (await cursor.fetchone())[0]

        # Доходы за месяц
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date >= ?", (month_ago.isoformat(),)
        ) as cursor:
            month_income = (await cursor.fetchone())[0]

        # Количество платежей за месяц
        async with conn.execute(
                "SELECT COUNT(*) FROM payments WHERE payment_date >= ?", (month_ago.isoformat(),)
        ) as cursor:
            month_payments_count = (await cursor.fetchone())[0]

    text = (
        f"💰 Финансовая сводка\n\n"
        f"💵 У тренеров: {money_with_trainers:.0f} руб.\n"
        f"🏦 В кассе: {money_in_cashbox:.0f} руб.\n"
        f"💎 Общая сумма: {money_with_trainers + money_in_cashbox:.0f} руб.\n\n"
        f"📅 Доходы за месяц: {month_income:.0f} руб.\n"
        f"📋 Платежей за месяц: {month_payments_count}"
    )

    await callback.message.edit_text(text, reply_markup=get_back_button())


# ОБРАБОТЧИКИ ДЛЯ РОДИТЕЛЯ

@router.callback_query(F.data == "my_children")
async def my_children_handler(callback: CallbackQuery):
    """Мои дети"""
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    children = await db.get_children_by_parent(user['id'])

    if not children:
        await callback.message.edit_text(
            "У вас нет зарегистрированных детей.",
            reply_markup=get_back_button()
        )
        return

    text = "👶 Ваши дети:\n\n"
    for child in children:
        text += f"• {child['full_name']}\n"
        text += f"  📍 Группа: {child['group_name']}\n"
        text += f"  🏢 Филиал: {child['branch_name']}\n\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())