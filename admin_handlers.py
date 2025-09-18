from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite
from datetime import datetime

from config import ROLE_MAIN_TRAINER, ROLE_TRAINER, ROLE_PARENT, ROLE_CASHIER
from database import db
from keyboards import get_back_button, get_main_trainer_menu
from states import AdminStates

admin_router = Router()


# УПРАВЛЕНИЕ ФИЛИАЛАМИ

@admin_router.callback_query(F.data == "mt_branches")
async def manage_branches(callback: CallbackQuery):
    """Управление филиалами"""
    branches = await db.get_all_branches()

    keyboard = InlineKeyboardBuilder()

    for branch in branches:
        keyboard.row(
            InlineKeyboardButton(
                text=f"🏢 {branch['name']}",
                callback_data=f"branch_info_{branch['id']}"
            )
        )

    keyboard.row(
        InlineKeyboardButton(text="➕ Добавить филиал", callback_data="add_branch")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        "🏢 Управление филиалами:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data == "add_branch")
async def add_branch_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления филиала"""
    await state.set_state(AdminStates.creating_branch_name)
    await callback.message.edit_text(
        "🏢 Создание нового филиала\n\n"
        "Введите название филиала:",
        reply_markup=get_back_button()
    )


@admin_router.message(StateFilter(AdminStates.creating_branch_name))
async def process_branch_name(message: Message, state: FSMContext):
    """Обработка названия филиала"""
    branch_name = message.text.strip()

    await state.update_data(branch_name=branch_name)
    await state.set_state(AdminStates.creating_branch_address)

    await message.answer(
        f"🏢 Филиал: {branch_name}\n\n"
        f"Введите адрес филиала (или напишите 'пропустить'):",
        reply_markup=get_back_button()
    )


@admin_router.message(StateFilter(AdminStates.creating_branch_address))
async def process_branch_address(message: Message, state: FSMContext):
    """Обработка адреса филиала"""
    data = await state.get_data()
    address = message.text.strip() if message.text.strip().lower() != 'пропустить' else None

    # Создаём филиал
    branch_id = await db.create_branch(data['branch_name'], address)

    await message.answer(
        f"✅ Филиал создан!\n\n"
        f"🏢 Название: {data['branch_name']}\n"
        f"📍 Адрес: {address or 'Не указан'}\n"
        f"🆔 ID: {branch_id}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


# УПРАВЛЕНИЕ ТРЕНЕРАМИ

@admin_router.callback_query(F.data == "mt_trainers")
async def manage_trainers(callback: CallbackQuery):
    """Управление тренерами"""
    trainers = await db.get_all_trainers()

    keyboard = InlineKeyboardBuilder()

    for trainer in trainers:
        status = "🟢" if trainer['telegram_id'] else "🔴"
        keyboard.row(
            InlineKeyboardButton(
                text=f"{status} {trainer['full_name']} ({trainer['branch_name']})",
                callback_data=f"trainer_info_{trainer['id']}"
            )
        )

    keyboard.row(
        InlineKeyboardButton(text="➕ Добавить тренера", callback_data="add_trainer")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        "👨‍🏫 Управление тренерами:\n\n"
        "🟢 - есть Telegram аккаунт\n"
        "🔴 - нет Telegram аккаунта",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data == "add_trainer")
async def add_trainer_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления тренера"""
    await state.set_state(AdminStates.creating_trainer_name)
    await callback.message.edit_text(
        "👨‍🏫 Добавление нового тренера\n\n"
        "Введите полное имя тренера:",
        reply_markup=get_back_button()
    )


@admin_router.message(StateFilter(AdminStates.creating_trainer_name))
async def process_trainer_name(message: Message, state: FSMContext):
    """Обработка имени тренера"""
    trainer_name = message.text.strip()

    # Получаем список филиалов
    branches = await db.get_all_branches()

    if not branches:
        await message.answer(
            "❌ Сначала создайте хотя бы один филиал!",
            reply_markup=get_main_trainer_menu()
        )
        await state.clear()
        return

    await state.update_data(trainer_name=trainer_name)
    await state.set_state(AdminStates.selecting_trainer_branch)

    keyboard = InlineKeyboardBuilder()
    for branch in branches:
        keyboard.row(
            InlineKeyboardButton(
                text=f"🏢 {branch['name']}",
                callback_data=f"select_branch_{branch['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await message.answer(
        f"👨‍🏫 Тренер: {trainer_name}\n\n"
        f"Выберите филиал:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data.startswith("select_branch_"), StateFilter(AdminStates.selecting_trainer_branch))
async def select_trainer_branch(callback: CallbackQuery, state: FSMContext):
    """Выбор филиала для тренера"""
    branch_id = int(callback.data.split("_")[2])
    data = await state.get_data()

    # Создаём тренера без привязки к пользователю Telegram
    trainer_id = await db.create_trainer(None, branch_id, data['trainer_name'])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT name FROM branches WHERE id = ?", (branch_id,)) as cursor:
            branch = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Тренер добавлен!\n\n"
        f"👨‍🏫 Имя: {data['trainer_name']}\n"
        f"🏢 Филиал: {branch['name']}\n"
        f"🆔 ID: {trainer_id}\n\n"
        f"ℹ️ Тренер сможет зарегистрироваться в боте самостоятельно.",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


# УПРАВЛЕНИЕ ГРУППАМИ И ДЕТЬМИ

@admin_router.callback_query(F.data == "mt_groups")
async def manage_groups(callback: CallbackQuery):
    """Управление группами и детьми"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="👥 Просмотр групп", callback_data="view_groups"),
        InlineKeyboardButton(text="👶 Просмотр детей", callback_data="view_children")
    )
    keyboard.row(
        InlineKeyboardButton(text="➕ Создать группу", callback_data="add_group"),
        InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="add_child")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        "👥 Управление группами и детьми:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data == "add_group")
async def add_group_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления группы"""
    await state.set_state(AdminStates.creating_group_name)
    await callback.message.edit_text(
        "👥 Создание новой группы\n\n"
        "Введите название группы:",
        reply_markup=get_back_button()
    )


@admin_router.message(StateFilter(AdminStates.creating_group_name))
async def process_group_name(message: Message, state: FSMContext):
    """Обработка названия группы"""
    group_name = message.text.strip()

    branches = await db.get_all_branches()

    if not branches:
        await message.answer(
            "❌ Сначала создайте хотя бы один филиал!",
            reply_markup=get_main_trainer_menu()
        )
        await state.clear()
        return

    await state.update_data(group_name=group_name)
    await state.set_state(AdminStates.selecting_group_branch)

    keyboard = InlineKeyboardBuilder()
    for branch in branches:
        keyboard.row(
            InlineKeyboardButton(
                text=f"🏢 {branch['name']}",
                callback_data=f"select_group_branch_{branch['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await message.answer(
        f"👥 Группа: {group_name}\n\n"
        f"Выберите филиал:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data.startswith("select_group_branch_"), StateFilter(AdminStates.selecting_group_branch))
async def select_group_branch(callback: CallbackQuery, state: FSMContext):
    """Выбор филиала для группы"""
    branch_id = int(callback.data.split("_")[3])
    data = await state.get_data()

    # Получаем тренеров филиала
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT * FROM trainers WHERE branch_id = ? ORDER BY full_name", (branch_id,)
        ) as cursor:
            trainers = await cursor.fetchall()

    if not trainers:
        await callback.message.edit_text(
            "❌ В данном филиале нет тренеров! Сначала добавьте тренеров.",
            reply_markup=get_back_button()
        )
        await state.clear()
        return

    await state.update_data(branch_id=branch_id)
    await state.set_state(AdminStates.selecting_group_trainer)

    keyboard = InlineKeyboardBuilder()
    for trainer in trainers:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👨‍🏫 {trainer['full_name']}",
                callback_data=f"select_group_trainer_{trainer['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"👥 Группа: {data['group_name']}\n\n"
        f"Выберите тренера:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data.startswith("select_group_trainer_"),
                             StateFilter(AdminStates.selecting_group_trainer))
async def select_group_trainer(callback: CallbackQuery, state: FSMContext):
    """Выбор тренера для группы"""
    trainer_id = int(callback.data.split("_")[3])
    data = await state.get_data()

    # Создаём группу
    group_id = await db.create_group(data['group_name'], data['branch_id'], trainer_id)

    # Получаем информацию о созданной группе
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT g.*, b.name as branch_name, t.full_name as trainer_name
                   FROM groups_table g 
                   JOIN branches b ON g.branch_id = b.id
                   JOIN trainers t ON g.trainer_id = t.id
                   WHERE g.id = ?""", (group_id,)
        ) as cursor:
            group = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Группа создана!\n\n"
        f"👥 Название: {group['name']}\n"
        f"🏢 Филиал: {group['branch_name']}\n"
        f"👨‍🏫 Тренер: {group['trainer_name']}\n"
        f"🆔 ID: {group_id}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


@admin_router.callback_query(F.data == "add_child")
async def add_child_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления ребёнка"""
    await state.set_state(AdminStates.creating_child_name)
    await callback.message.edit_text(
        "👶 Добавление нового ребёнка\n\n"
        "Введите полное имя ребёнка:",
        reply_markup=get_back_button()
    )


@admin_router.message(StateFilter(AdminStates.creating_child_name))
async def process_child_name(message: Message, state: FSMContext):
    """Обработка имени ребёнка"""
    child_name = message.text.strip()

    # Получаем родителей
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT * FROM users WHERE role = 'parent' ORDER BY first_name, last_name",
        ) as cursor:
            parents = await cursor.fetchall()

    if not parents:
        await message.answer(
            "❌ В системе нет зарегистрированных родителей!",
            reply_markup=get_main_trainer_menu()
        )
        await state.clear()
        return

    await state.update_data(child_name=child_name)
    await state.set_state(AdminStates.selecting_child_parent)

    keyboard = InlineKeyboardBuilder()
    for parent in parents:
        parent_name = f"{parent['first_name']} {parent['last_name']}"
        if parent['username']:
            parent_name += f" (@{parent['username']})"
        keyboard.row(
            InlineKeyboardButton(
                text=f"👤 {parent_name}",
                callback_data=f"select_child_parent_{parent['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await message.answer(
        f"👶 Ребёнок: {child_name}\n\n"
        f"Выберите родителя:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data.startswith("select_child_parent_"), StateFilter(AdminStates.selecting_child_parent))
async def select_child_parent(callback: CallbackQuery, state: FSMContext):
    """Выбор родителя для ребёнка"""
    parent_id = int(callback.data.split("_")[3])
    data = await state.get_data()

    # Получаем группы
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT g.*, b.name as branch_name, t.full_name as trainer_name
                   FROM groups_table g 
                   JOIN branches b ON g.branch_id = b.id
                   JOIN trainers t ON g.trainer_id = t.id
                   ORDER BY b.name, g.name"""
        ) as cursor:
            groups = await cursor.fetchall()

    if not groups:
        await callback.message.edit_text(
            "❌ В системе нет групп! Сначала создайте группы.",
            reply_markup=get_back_button()
        )
        await state.clear()
        return

    await state.update_data(parent_id=parent_id)
    await state.set_state(AdminStates.selecting_child_group)

    keyboard = InlineKeyboardBuilder()
    for group in groups:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👥 {group['name']} ({group['branch_name']} - {group['trainer_name']})",
                callback_data=f"select_child_group_{group['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"👶 Ребёнок: {data['child_name']}\n\n"
        f"Выберите группу:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data.startswith("select_child_group_"), StateFilter(AdminStates.selecting_child_group))
async def select_child_group(callback: CallbackQuery, state: FSMContext):
    """Выбор группы для ребёнка"""
    group_id = int(callback.data.split("_")[3])
    data = await state.get_data()

    # Создаём ребёнка
    child_id = await db.create_child(data['child_name'], data['parent_id'], group_id)

    # Получаем информацию для отчёта
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT g.name as group_name, b.name as branch_name, t.full_name as trainer_name,
                          u.first_name || ' ' || u.last_name as parent_name
                   FROM groups_table g 
                   JOIN branches b ON g.branch_id = b.id
                   JOIN trainers t ON g.trainer_id = t.id
                   JOIN users u ON u.id = ?
                   WHERE g.id = ?""", (data['parent_id'], group_id)
        ) as cursor:
            info = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Ребёнок добавлен!\n\n"
        f"👶 Имя: {data['child_name']}\n"
        f"👤 Родитель: {info['parent_name']}\n"
        f"👥 Группа: {info['group_name']}\n"
        f"🏢 Филиал: {info['branch_name']}\n"
        f"👨‍🏫 Тренер: {info['trainer_name']}\n"
        f"🆔 ID: {child_id}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


# ОТЧЁТЫ

@admin_router.callback_query(F.data == "mt_reports")
async def reports_menu(callback: CallbackQuery):
    """Меню отчётов"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📅 Отчёт за сегодня", callback_data="report_today"),
        InlineKeyboardButton(text="📊 Отчёт за неделю", callback_data="report_week")
    )
    keyboard.row(
        InlineKeyboardButton(text="📈 Отчёт за месяц", callback_data="report_month"),
        InlineKeyboardButton(text="💰 Финансовый отчёт", callback_data="report_finance")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        "📋 Выберите тип отчёта:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data == "report_today")
async def report_today(callback: CallbackQuery):
    """Отчёт за сегодня"""
    from datetime import date
    today = date.today()

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        async with conn.execute(
                """SELECT s.*, g.name as group_name, b.name as branch_name, t.full_name as trainer_name
                   FROM sessions s 
                   JOIN groups_table g ON s.group_id = g.id 
                   JOIN branches b ON g.branch_id = b.id 
                   JOIN trainers t ON s.trainer_id = t.id 
                   WHERE DATE(s.start_time) = ? 
                   ORDER BY s.start_time""", (today.isoformat(),)
        ) as cursor:
            sessions = await cursor.fetchall()

        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE DATE(payment_date) = ?", (today.isoformat(),)
        ) as cursor:
            payments_today = (await cursor.fetchone())[0]

    if not sessions:
        await callback.message.edit_text(
            f"📅 Отчёт за {today.strftime('%d.%m.%Y')}\n\n"
            f"❌ Сегодня занятий не было.",
            reply_markup=get_back_button()
        )
        return

    text = f"📅 Отчёт за {today.strftime('%d.%m.%Y')}\n\n"
    text += f"📊 Всего занятий: {len(sessions)}\n"
    text += f"🏃 Тренировки: {sum(1 for s in sessions if s['type'] == 'training')}\n"
    text += f"⚽ Игры: {sum(1 for s in sessions if s['type'] == 'game')}\n"
    text += f"💰 Получено денег: {payments_today:.0f} руб.\n\n"

    text += "📋 Занятия:\n"
    for session in sessions:
        start_time = session['start_time']
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        start_time_str = start_time.strftime('%H:%M')
        session_type = "🏃" if session['type'] == 'training' else "⚽"
        text += f"{session_type} {start_time_str} - {session['group_name']} ({session['trainer_name']})\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())


# Добавьте эту функцию в admin_handlers.py

@admin_router.callback_query(F.data == "view_children")
async def view_children_with_edit(callback: CallbackQuery):
    """Просмотр всех детей с возможностью редактирования"""
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT c.*, g.name as group_name, b.name as branch_name, t.full_name as trainer_name,
                          u.first_name || ' ' || u.last_name as parent_name
                   FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   JOIN branches b ON g.branch_id = b.id 
                   JOIN trainers t ON g.trainer_id = t.id 
                   JOIN users u ON c.parent_id = u.id
                   ORDER BY b.name, g.name, c.full_name"""
        ) as cursor:
            children = await cursor.fetchall()

    if not children:
        await callback.message.edit_text(
            "❌ Детей пока нет.",
            reply_markup=get_back_button()
        )
        return

    keyboard = InlineKeyboardBuilder()
    for child in children:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👶 {child['full_name']} ({child['group_name']}, {child['branch_name']})",
                callback_data=f"child_info_{child['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="mt_groups"))

    await callback.message.edit_text(
        "👶 Все дети (нажмите для просмотра/редактирования):",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data.startswith("child_info_"))
async def child_info_with_actions(callback: CallbackQuery):
    """Информация о ребёнке с кнопками редактирования"""
    child_id = int(callback.data.split("_")[2])

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
        f"   Всего: {total_amount:.0f} руб. ({total_payments} платежей)\n"
        f"   Сдано в кассу: {paid_amount:.0f} руб."
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_child_{child_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_child_{child_id}")
    )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="view_children"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


# НАЙДИТЕ в admin_handlers.py функцию edit_child_start и ЗАМЕНИТЕ её на эту:

# НАЙДИТЕ в admin_handlers.py функцию edit_child_start и ЗАМЕНИТЕ её на эту:

# НАЙДИТЕ в admin_handlers.py функцию edit_child_start и ЗАМЕНИТЕ её на эту:

@admin_router.callback_query(F.data.startswith("edit_child_") & ~F.data.contains("parent") & ~F.data.contains("group"))
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


# ДОБАВЬТЕ эти две новые функции ПОСЛЕ функции edit_child_start:

@admin_router.callback_query(F.data == "edit_child_parent_only", StateFilter(AdminStates.editing_child_name))
async def edit_child_parent_only(callback: CallbackQuery, state: FSMContext):
    """Редактирование только родителя ребёнка"""
    # Получаем всех родителей
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT * FROM users WHERE role = 'parent' ORDER BY first_name, last_name",
        ) as cursor:
            parents = await cursor.fetchall()

    if not parents:
        await callback.message.edit_text(
            "❌ В системе нет зарегистрированных родителей!",
            reply_markup=get_back_button()
        )
        return

    await state.set_state(AdminStates.editing_child_parent)

    keyboard = InlineKeyboardBuilder()
    for parent in parents:
        parent_name = f"{parent['first_name']} {parent['last_name']}"
        if parent['username']:
            parent_name += f" (@{parent['username']})"
        keyboard.row(
            InlineKeyboardButton(
                text=f"👤 {parent_name}",
                callback_data=f"select_edit_child_parent_{parent['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"✏️ Изменение родителя ребёнка\n\n"
        f"Выберите нового родителя:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data == "edit_child_group_only", StateFilter(AdminStates.editing_child_name))
async def edit_child_group_only(callback: CallbackQuery, state: FSMContext):
    """Редактирование только группы ребёнка"""
    # Получаем все группы
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT g.*, b.name as branch_name, t.full_name as trainer_name
                   FROM groups_table g 
                   JOIN branches b ON g.branch_id = b.id
                   JOIN trainers t ON g.trainer_id = t.id
                   ORDER BY b.name, g.name"""
        ) as cursor:
            groups = await cursor.fetchall()

    if not groups:
        await callback.message.edit_text(
            "❌ В системе нет групп!",
            reply_markup=get_back_button()
        )
        return

    await state.set_state(AdminStates.editing_child_group)

    keyboard = InlineKeyboardBuilder()
    for group in groups:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👥 {group['name']} ({group['branch_name']} - {group['trainer_name']})",
                callback_data=f"select_edit_child_group_{group['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"✏️ Изменение группы ребёнка\n\n"
        f"Выберите новую группу:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.message(StateFilter(AdminStates.editing_child_name))
async def process_edit_child_name(message: Message, state: FSMContext):
    """Обработка нового имени ребёнка"""
    new_name = message.text.strip()
    data = await state.get_data()

    # Обновляем только имя ребёнка
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            "UPDATE children SET full_name = ? WHERE id = ?",
            (new_name, data['editing_child_id'])
        )
        await conn.commit()

    await message.answer(
        f"✅ Имя ребёнка обновлено!\n\n"
        f"👶 Новое имя: {new_name}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


@admin_router.callback_query(F.data.startswith("delete_child_"))
async def delete_child_confirm(callback: CallbackQuery):
    """Подтверждение удаления ребёнка"""
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

@admin_router.callback_query(F.data.startswith("confirm_delete_child_"))
async def confirm_delete_child(callback: CallbackQuery):
    """Подтверждённое удаление ребёнка"""
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

# ДОБАВЬТЕ эти функции в КОНЕЦ файла admin_handlers.py:

@admin_router.callback_query(F.data.startswith("select_edit_child_parent_"), StateFilter(AdminStates.editing_child_parent))
async def select_edit_child_parent(callback: CallbackQuery, state: FSMContext):
    """Выбор нового родителя для ребёнка"""
    parent_id = int(callback.data.split("_")[4])
    data = await state.get_data()

    # Определяем имя: новое или старое
    final_name = data.get('new_name', data['current_name'])

    # Обновляем ребёнка
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "UPDATE children SET full_name = ?, parent_id = ? WHERE id = ?",
            (final_name, parent_id, data['editing_child_id'])
        )
        await conn.commit()

        async with conn.execute(
                "SELECT first_name || ' ' || last_name as parent_name FROM users WHERE id = ?",
                (parent_id,)
        ) as cursor:
            parent = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Ребёнок обновлен!\n\n"
        f"👶 Имя: {final_name}\n"
        f"👤 Новый родитель: {parent['parent_name']}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


@admin_router.callback_query(F.data.startswith("select_edit_child_group_"), StateFilter(AdminStates.editing_child_group))
async def select_edit_child_group(callback: CallbackQuery, state: FSMContext):
    """Выбор новой группы для ребёнка"""
    group_id = int(callback.data.split("_")[4])
    data = await state.get_data()

    # Определяем имя: новое или старое
    final_name = data.get('new_name', data['current_name'])

    # Обновляем ребёнка
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "UPDATE children SET full_name = ?, group_id = ? WHERE id = ?",
            (final_name, group_id, data['editing_child_id'])
        )
        await conn.commit()

        async with conn.execute("SELECT name FROM groups_table WHERE id = ?", (group_id,)) as cursor:
            group = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Ребёнок обновлен!\n\n"
        f"👶 Имя: {final_name}\n"
        f"👥 Новая группа: {group['name']}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()