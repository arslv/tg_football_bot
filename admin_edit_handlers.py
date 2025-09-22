from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite

from config import ROLE_MAIN_TRAINER
from database import db
from keyboards import get_back_button, get_main_trainer_menu
from states import AdminStates

admin_edit_router = Router()


# Функция для проверки прав главного тренера
async def is_main_trainer(telegram_id: int) -> bool:
    """Проверка, является ли пользователь главным тренером"""
    user = await db.get_user_by_telegram_id(telegram_id)
    return user and user['role'] == ROLE_MAIN_TRAINER


# РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ФИЛИАЛОВ

@admin_edit_router.callback_query(F.data.startswith("branch_info_"))
async def branch_info_with_actions(callback: CallbackQuery):
    """Информация о филиале с кнопками редактирования"""
    branch_id = int(callback.data.split("_")[2])
    is_main = await is_main_trainer(callback.from_user.id)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        async with conn.execute("SELECT * FROM branches WHERE id = ?", (branch_id,)) as cursor:
            branch = await cursor.fetchone()

        async with conn.execute("SELECT full_name FROM trainers WHERE branch_id = ?", (branch_id,)) as cursor:
            trainers = await cursor.fetchall()

        async with conn.execute("SELECT COUNT(*) FROM groups_table WHERE branch_id = ?", (branch_id,)) as cursor:
            groups_count = (await cursor.fetchone())[0]

        async with conn.execute(
                """SELECT COUNT(*) FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   WHERE g.branch_id = ?""", (branch_id,)
        ) as cursor:
            children_count = (await cursor.fetchone())[0]

    if not branch:
        await callback.message.edit_text("Филиал не найден", reply_markup=get_back_button())
        return

    trainers_text = "\n".join([f"• {t['full_name']}" for t in trainers]) or "Нет тренеров"

    text = (
        f"🏢 {branch['name']}\n\n"
        f"📍 Адрес: {branch['address'] or 'Не указан'}\n"
        f"👨‍🏫 Тренеры ({len(trainers)}):\n{trainers_text}\n\n"
        f"👥 Групп: {groups_count}\n"
        f"👶 Детей: {children_count}"
    )

    keyboard = InlineKeyboardBuilder()

    # Кнопка редактирования доступна всем
    keyboard.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_branch_{branch_id}"))

    # Кнопка удаления только для главного тренера
    if is_main:
        keyboard.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_branch_{branch_id}"))

    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="mt_branches"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


# РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ТРЕНЕРОВ

@admin_edit_router.callback_query(F.data.startswith("trainer_info_"))
async def trainer_info_with_actions(callback: CallbackQuery):
    """Информация о тренере с кнопками редактирования"""
    trainer_id = int(callback.data.split("_")[2])
    is_main = await is_main_trainer(callback.from_user.id)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        async with conn.execute(
                """SELECT t.*, b.name as branch_name, u.first_name, u.last_name, u.username
                   FROM trainers t 
                   JOIN branches b ON t.branch_id = b.id 
                   LEFT JOIN users u ON t.user_id = u.id 
                   WHERE t.id = ?""", (trainer_id,)
        ) as cursor:
            trainer = await cursor.fetchone()

        async with conn.execute("SELECT name FROM groups_table WHERE trainer_id = ?", (trainer_id,)) as cursor:
            groups = await cursor.fetchall()

        async with conn.execute(
                """SELECT COUNT(*) FROM children c 
                   JOIN groups_table g ON c.group_id = g.id 
                   WHERE g.trainer_id = ?""", (trainer_id,)
        ) as cursor:
            children_count = (await cursor.fetchone())[0]

    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    groups_text = "\n".join([f"• {g['name']}" for g in groups]) or "Нет групп"
    telegram_info = "✅ Подключён" if trainer['user_id'] else "❌ Не подключён"

    text = (
        f"👨‍🏫 {trainer['full_name']}\n\n"
        f"🏢 Филиал: {trainer['branch_name']}\n"
        f"📱 Telegram: {telegram_info}\n"
        f"👥 Групп: {len(groups)}\n"
        f"👶 Детей: {children_count}\n\n"
        f"📋 Группы:\n{groups_text}"
    )

    keyboard = InlineKeyboardBuilder()

    # Кнопка редактирования доступна всем
    keyboard.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_trainer_{trainer_id}"))

    # Кнопка удаления только для главного тренера
    if is_main:
        keyboard.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_trainer_{trainer_id}"))

    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="mt_trainers"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


# РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ГРУПП

@admin_edit_router.callback_query(F.data.startswith("group_info_"))
async def group_info_with_actions(callback: CallbackQuery):
    """Информация о группе с кнопками редактирования"""
    group_id = int(callback.data.split("_")[2])
    is_main = await is_main_trainer(callback.from_user.id)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT g.*, b.name as branch_name, t.full_name as trainer_name,
                          COUNT(c.id) as children_count
                   FROM groups_table g 
                   JOIN branches b ON g.branch_id = b.id 
                   JOIN trainers t ON g.trainer_id = t.id 
                   LEFT JOIN children c ON g.id = c.group_id
                   WHERE g.id = ?
                   GROUP BY g.id""", (group_id,)
        ) as cursor:
            group = await cursor.fetchone()

        async with conn.execute(
                "SELECT full_name FROM children WHERE group_id = ? ORDER BY full_name", (group_id,)
        ) as cursor:
            children = await cursor.fetchall()

    if not group:
        await callback.message.edit_text("Группа не найдена", reply_markup=get_back_button())
        return

    children_text = "\n".join([f"• {c['full_name']}" for c in children]) or "Нет детей"

    text = (
        f"👥 {group['name']}\n\n"
        f"🏢 Филиал: {group['branch_name']}\n"
        f"👨‍🏫 Тренер: {group['trainer_name']}\n"
        f"👶 Детей: {group['children_count']}\n\n"
        f"📋 Список детей:\n{children_text}"
    )

    keyboard = InlineKeyboardBuilder()

    # Кнопка редактирования доступна всем
    keyboard.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_group_{group_id}"))

    # Кнопка удаления только для главного тренера
    if is_main:
        keyboard.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_group_{group_id}"))

    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="view_groups"))

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


# Добавляем обработчик для просмотра групп с возможностью редактирования
@admin_edit_router.callback_query(F.data == "view_groups")
async def view_groups_with_edit(callback: CallbackQuery):
    """Просмотр всех групп с возможностью редактирования"""
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT g.*, b.name as branch_name, t.full_name as trainer_name,
                          COUNT(c.id) as children_count
                   FROM groups_table g 
                   JOIN branches b ON g.branch_id = b.id 
                   JOIN trainers t ON g.trainer_id = t.id 
                   LEFT JOIN children c ON g.id = c.group_id
                   GROUP BY g.id, b.name, t.full_name
                   ORDER BY b.name, g.name"""
        ) as cursor:
            groups = await cursor.fetchall()

    if not groups:
        await callback.message.edit_text(
            "❌ Групп пока нет.",
            reply_markup=get_back_button()
        )
        return

    keyboard = InlineKeyboardBuilder()
    for group in groups:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👥 {group['name']} ({group['branch_name']}, {group['children_count']} детей)",
                callback_data=f"group_info_{group['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="mt_groups"))

    await callback.message.edit_text(
        "👥 Все группы (нажмите для редактирования):",
        reply_markup=keyboard.as_markup()
    )


# РЕДАКТИРОВАНИЕ ФИЛИАЛОВ
@admin_edit_router.callback_query(F.data.startswith("edit_branch_"))
async def edit_branch_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования филиала"""
    branch_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM branches WHERE id = ?", (branch_id,)) as cursor:
            branch = await cursor.fetchone()

    if not branch:
        await callback.message.edit_text("Филиал не найден", reply_markup=get_back_button())
        return

    await state.update_data(editing_branch_id=branch_id, current_name=branch['name'], current_address=branch['address'])
    await state.set_state(AdminStates.editing_branch_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="📍 Изменить адрес", callback_data="edit_branch_address_only"))
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data=f"branch_info_{branch_id}"))

    await callback.message.edit_text(
        f"✏️ Редактирование филиала\n\n"
        f"Текущее название: {branch['name']}\n"
        f"Текущий адрес: {branch['address'] or 'Не указан'}\n\n"
        f"Введите новое название филиала или нажмите кнопку для изменения только адреса:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.message(StateFilter(AdminStates.editing_branch_name))
async def process_edit_branch_name(message: Message, state: FSMContext):
    """Обработка нового названия филиала"""
    new_name = message.text.strip()
    data = await state.get_data()

    await state.update_data(new_name=new_name)
    await state.set_state(AdminStates.editing_branch_address)

    await message.answer(
        f"✏️ Филиал: {new_name}\n\n"
        f"Старый адрес: {data['current_address'] or 'Не указан'}\n"
        f"Введите новый адрес (или 'пропустить' чтобы оставить как есть):",
        reply_markup=get_back_button()
    )


@admin_edit_router.callback_query(F.data == "edit_branch_address_only", StateFilter(AdminStates.editing_branch_name))
async def edit_branch_address_only(callback: CallbackQuery, state: FSMContext):
    """Редактирование только адреса филиала"""
    data = await state.get_data()
    await state.set_state(AdminStates.editing_branch_address)

    await callback.message.edit_text(
        f"✏️ Изменение адреса филиала\n\n"
        f"Название: {data['current_name']}\n"
        f"Старый адрес: {data['current_address'] or 'Не указан'}\n\n"
        f"Введите новый адрес:",
        reply_markup=get_back_button()
    )


@admin_edit_router.message(StateFilter(AdminStates.editing_branch_address))
async def process_edit_branch_address(message: Message, state: FSMContext):
    """Обработка нового адреса филиала"""
    data = await state.get_data()
    new_address = message.text.strip() if message.text.strip().lower() != 'пропустить' else data['current_address']

    # Определяем название: новое или старое
    final_name = data.get('new_name', data['current_name'])

    # Обновляем филиал
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            "UPDATE branches SET name = ?, address = ? WHERE id = ?",
            (final_name, new_address, data['editing_branch_id'])
        )
        await conn.commit()

    await message.answer(
        f"✅ Филиал обновлен!\n\n"
        f"🏢 Название: {final_name}\n"
        f"📍 Адрес: {new_address or 'Не указан'}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


# РЕДАКТИРОВАНИЕ ТРЕНЕРОВ
@admin_edit_router.callback_query(F.data.startswith("edit_trainer_"))
async def edit_trainer_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования тренера"""
    trainer_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                """SELECT t.*, b.name as branch_name 
                   FROM trainers t 
                   JOIN branches b ON t.branch_id = b.id 
                   WHERE t.id = ?""", (trainer_id,)
        ) as cursor:
            trainer = await cursor.fetchone()

    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    await state.update_data(
        editing_trainer_id=trainer_id,
        current_name=trainer['full_name'],
        current_branch_id=trainer['branch_id']
    )
    await state.set_state(AdminStates.editing_trainer_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🏢 Изменить филиал", callback_data="edit_trainer_branch_only"))
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data=f"trainer_info_{trainer_id}"))

    await callback.message.edit_text(
        f"✏️ Редактирование тренера\n\n"
        f"Текущее имя: {trainer['full_name']}\n"
        f"Текущий филиал: {trainer['branch_name']}\n\n"
        f"Введите новое имя тренера или нажмите кнопку для изменения только филиала:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.message(StateFilter(AdminStates.editing_trainer_name))
async def process_edit_trainer_name(message: Message, state: FSMContext):
    """Обработка нового имени тренера"""
    new_name = message.text.strip()
    data = await state.get_data()

    await state.update_data(new_name=new_name)
    await state.set_state(AdminStates.editing_trainer_branch)

    # Получаем все филиалы
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT id, name FROM branches ORDER BY name") as cursor:
            branches = await cursor.fetchall()

    keyboard = InlineKeyboardBuilder()
    for branch in branches:
        keyboard.row(
            InlineKeyboardButton(
                text=f"🏢 {branch['name']}",
                callback_data=f"select_edit_branch_{branch['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await message.answer(
        f"✏️ Тренер: {new_name}\n\n"
        f"Выберите новый филиал:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data == "edit_trainer_branch_only", StateFilter(AdminStates.editing_trainer_name))
async def edit_trainer_branch_only(callback: CallbackQuery, state: FSMContext):
    """Редактирование только филиала тренера"""
    await state.set_state(AdminStates.editing_trainer_branch)

    # Получаем все филиалы
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT id, name FROM branches ORDER BY name") as cursor:
            branches = await cursor.fetchall()

    keyboard = InlineKeyboardBuilder()
    for branch in branches:
        keyboard.row(
            InlineKeyboardButton(
                text=f"🏢 {branch['name']}",
                callback_data=f"select_edit_branch_{branch['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"✏️ Изменение филиала тренера\n\n"
        f"Выберите новый филиал:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data.startswith("select_edit_branch_"),
                                  StateFilter(AdminStates.editing_trainer_branch))
async def select_edit_trainer_branch(callback: CallbackQuery, state: FSMContext):
    """Выбор нового филиала для тренера"""
    branch_id = int(callback.data.split("_")[3])
    data = await state.get_data()

    # Определяем имя: новое или старое
    final_name = data.get('new_name', data['current_name'])

    # Обновляем тренера
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "UPDATE trainers SET full_name = ?, branch_id = ? WHERE id = ?",
            (final_name, branch_id, data['editing_trainer_id'])
        )
        await conn.commit()

        async with conn.execute("SELECT name FROM branches WHERE id = ?", (branch_id,)) as cursor:
            branch = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Тренер обновлен!\n\n"
        f"👨‍🏫 Имя: {final_name}\n"
        f"🏢 Филиал: {branch['name']}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


# РЕДАКТИРОВАНИЕ ГРУПП
@admin_edit_router.callback_query(F.data.startswith("edit_group_"))
async def edit_group_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования группы"""
    group_id = int(callback.data.split("_")[2])

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

    if not group:
        await callback.message.edit_text("Группа не найдена", reply_markup=get_back_button())
        return

    await state.update_data(
        editing_group_id=group_id,
        current_name=group['name'],
        current_trainer_id=group['trainer_id'],
        current_branch_id=group['branch_id']
    )
    await state.set_state(AdminStates.editing_group_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="👨‍🏫 Изменить тренера", callback_data="edit_group_trainer_only"))
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data=f"group_info_{group_id}"))

    await callback.message.edit_text(
        f"✏️ Редактирование группы\n\n"
        f"Текущее название: {group['name']}\n"
        f"Текущий тренер: {group['trainer_name']}\n"
        f"Филиал: {group['branch_name']}\n\n"
        f"Введите новое название группы или нажмите кнопку для изменения только тренера:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.message(StateFilter(AdminStates.editing_group_name))
async def process_edit_group_name(message: Message, state: FSMContext):
    """Обработка нового названия группы"""
    new_name = message.text.strip()
    data = await state.get_data()

    await state.update_data(new_name=new_name)
    await state.set_state(AdminStates.editing_group_trainer)

    # Получаем тренеров текущего филиала
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT id, full_name FROM trainers WHERE branch_id = ? ORDER BY full_name",
                (data['current_branch_id'],)
        ) as cursor:
            trainers = await cursor.fetchall()

    keyboard = InlineKeyboardBuilder()
    for trainer in trainers:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👨‍🏫 {trainer['full_name']}",
                callback_data=f"select_edit_group_trainer_{trainer['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await message.answer(
        f"✏️ Группа: {new_name}\n\n"
        f"Выберите нового тренера:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data == "edit_group_trainer_only", StateFilter(AdminStates.editing_group_name))
async def edit_group_trainer_only(callback: CallbackQuery, state: FSMContext):
    """Редактирование только тренера группы"""
    data = await state.get_data()
    await state.set_state(AdminStates.editing_group_trainer)

    # Получаем тренеров текущего филиала
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
                "SELECT id, full_name FROM trainers WHERE branch_id = ? ORDER BY full_name",
                (data['current_branch_id'],)
        ) as cursor:
            trainers = await cursor.fetchall()

    keyboard = InlineKeyboardBuilder()
    for trainer in trainers:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👨‍🏫 {trainer['full_name']}",
                callback_data=f"select_edit_group_trainer_{trainer['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))

    await callback.message.edit_text(
        f"✏️ Изменение тренера группы\n\n"
        f"Выберите нового тренера:",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data.startswith("select_edit_group_trainer_"),
                                  StateFilter(AdminStates.editing_group_trainer))
async def select_edit_group_trainer(callback: CallbackQuery, state: FSMContext):
    """Выбор нового тренера для группы"""
    trainer_id = int(callback.data.split("_")[4])
    data = await state.get_data()

    # Определяем название: новое или старое
    final_name = data.get('new_name', data['current_name'])

    # Обновляем группу
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "UPDATE groups_table SET name = ?, trainer_id = ? WHERE id = ?",
            (final_name, trainer_id, data['editing_group_id'])
        )
        await conn.commit()

        async with conn.execute("SELECT full_name FROM trainers WHERE id = ?", (trainer_id,)) as cursor:
            trainer = await cursor.fetchone()

    await callback.message.edit_text(
        f"✅ Группа обновлена!\n\n"
        f"👥 Название: {final_name}\n"
        f"👨‍🏫 Тренер: {trainer['full_name']}",
        reply_markup=get_main_trainer_menu()
    )

    await state.clear()


# ФУНКЦИИ УДАЛЕНИЯ (ТОЛЬКО ДЛЯ ГЛАВНОГО ТРЕНЕРА)

# Удаление филиала
@admin_edit_router.callback_query(F.data.startswith("delete_branch_"))
async def delete_branch_confirm(callback: CallbackQuery):
    """Подтверждение удаления филиала (только для главного тренера)"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    branch_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT name FROM branches WHERE id = ?", (branch_id,)) as cursor:
            branch = await cursor.fetchone()

        async with conn.execute("SELECT COUNT(*) FROM trainers WHERE branch_id = ?", (branch_id,)) as cursor:
            trainers_count = (await cursor.fetchone())[0]

        async with conn.execute("SELECT COUNT(*) FROM groups_table WHERE branch_id = ?", (branch_id,)) as cursor:
            groups_count = (await cursor.fetchone())[0]

    if not branch:
        await callback.message.edit_text("Филиал не найден", reply_markup=get_back_button())
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_branch_{branch_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"branch_info_{branch_id}")
    )

    warning = ""
    if trainers_count > 0 or groups_count > 0:
        warning = f"\n\n⚠️ ВНИМАНИЕ! Это также удалит:\n• Тренеров: {trainers_count}\n• Групп: {groups_count}\n• Всех детей в этих группах"

    await callback.message.edit_text(
        f"🗑 Удаление филиала\n\n"
        f"Вы уверены, что хотите удалить филиал '{branch['name']}'?{warning}",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data.startswith("confirm_delete_branch_"))
async def confirm_delete_branch(callback: CallbackQuery):
    """Подтверждённое удаление филиала"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    branch_id = int(callback.data.split("_")[3])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT name FROM branches WHERE id = ?", (branch_id,)) as cursor:
            branch = await cursor.fetchone()

        if branch:
            await conn.execute("DELETE FROM branches WHERE id = ?", (branch_id,))
            await conn.commit()

    await callback.message.edit_text(
        f"✅ Филиал '{branch['name']}' успешно удален!",
        reply_markup=get_main_trainer_menu()
    )


# Удаление тренера
@admin_edit_router.callback_query(F.data.startswith("delete_trainer_"))
async def delete_trainer_confirm(callback: CallbackQuery):
    """Подтверждение удаления тренера (только для главного тренера)"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    trainer_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT full_name FROM trainers WHERE id = ?", (trainer_id,)) as cursor:
            trainer = await cursor.fetchone()

        async with conn.execute("SELECT COUNT(*) FROM groups_table WHERE trainer_id = ?", (trainer_id,)) as cursor:
            groups_count = (await cursor.fetchone())[0]

    if not trainer:
        await callback.message.edit_text("Тренер не найден", reply_markup=get_back_button())
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_trainer_{trainer_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"trainer_info_{trainer_id}")
    )

    warning = ""
    if groups_count > 0:
        warning = f"\n\n⚠️ ВНИМАНИЕ! Это также удалит:\n• Групп: {groups_count}\n• Всех детей в этих группах"

    await callback.message.edit_text(
        f"🗑 Удаление тренера\n\n"
        f"Вы уверены, что хотите удалить тренера '{trainer['full_name']}'?{warning}",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data.startswith("confirm_delete_trainer_"))
async def confirm_delete_trainer(callback: CallbackQuery):
    """Подтверждённое удаление тренера"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    trainer_id = int(callback.data.split("_")[3])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT full_name FROM trainers WHERE id = ?", (trainer_id,)) as cursor:
            trainer = await cursor.fetchone()

        if trainer:
            await conn.execute("DELETE FROM trainers WHERE id = ?", (trainer_id,))
            await conn.commit()

    await callback.message.edit_text(
        f"✅ Тренер '{trainer['full_name']}' успешно удален!",
        reply_markup=get_main_trainer_menu()
    )


# Удаление группы
@admin_edit_router.callback_query(F.data.startswith("delete_group_"))
async def delete_group_confirm(callback: CallbackQuery):
    """Подтверждение удаления группы (только для главного тренера)"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    group_id = int(callback.data.split("_")[2])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT name FROM groups_table WHERE id = ?", (group_id,)) as cursor:
            group = await cursor.fetchone()

        async with conn.execute("SELECT COUNT(*) FROM children WHERE group_id = ?", (group_id,)) as cursor:
            children_count = (await cursor.fetchone())[0]

        async with conn.execute("SELECT COUNT(*) FROM sessions WHERE group_id = ?", (group_id,)) as cursor:
            sessions_count = (await cursor.fetchone())[0]

    if not group:
        await callback.message.edit_text("Группа не найдена", reply_markup=get_back_button())
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_group_{group_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"group_info_{group_id}")
    )

    warning = ""
    if children_count > 0 or sessions_count > 0:
        warning = f"\n\n⚠️ ВНИМАНИЕ! Это также удалит:\n• Детей: {children_count}\n• Записей о сессиях: {sessions_count}"

    await callback.message.edit_text(
        f"🗑 Удаление группы\n\n"
        f"Вы уверены, что хотите удалить группу '{group['name']}'?{warning}\n\n"
        f"❗ Это действие нельзя отменить!",
        reply_markup=keyboard.as_markup()
    )


@admin_edit_router.callback_query(F.data.startswith("confirm_delete_group_"))
async def confirm_delete_group(callback: CallbackQuery):
    """Подтверждённое удаление группы"""
    if not await is_main_trainer(callback.from_user.id):
        await callback.answer("❌ Нет прав на удаление", show_alert=True)
        return

    group_id = int(callback.data.split("_")[3])

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT name FROM groups_table WHERE id = ?", (group_id,)) as cursor:
            group = await cursor.fetchone()

        if group:
            await conn.execute("DELETE FROM groups_table WHERE id = ?", (group_id,))
            await conn.commit()

    await callback.message.edit_text(
        f"✅ Группа '{group['name']}' успешно удалена!",
        reply_markup=get_main_trainer_menu()
    )