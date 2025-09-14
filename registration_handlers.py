from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import aiosqlite

from config import ROLE_TRAINER, ROLE_PARENT, ROLE_CASHIER
from database import db
from keyboards import get_trainer_menu, get_parent_menu, get_cashier_menu, get_back_button
from states import RegistrationStates

registration_router = Router()


@registration_router.message(Command("register"))
async def register_start(message: Message, state: FSMContext):
    """Начало регистрации"""
    existing_user = await db.get_user_by_telegram_id(message.from_user.id)

    if existing_user:
        await message.answer("✅ Вы уже зарегистрированы в системе!")
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="👨‍🏫 Тренер", callback_data="role_trainer"),
        InlineKeyboardButton(text="👤 Родитель", callback_data="role_parent")
    )
    keyboard.row(
        InlineKeyboardButton(text="💰 Кассир", callback_data="role_cashier")
    )

    await message.answer(
        "👋 Добро пожаловать в систему футбольной академии!\n\n"
        "Выберите вашу роль:",
        reply_markup=keyboard.as_markup()
    )

    await state.set_state(RegistrationStates.waiting_for_role)


@registration_router.callback_query(F.data.startswith("role_"), StateFilter(RegistrationStates.waiting_for_role))
async def select_role(callback: CallbackQuery, state: FSMContext):
    """Выбор роли пользователя"""
    role = callback.data.split("_")[1]

    role_names = {
        "trainer": "Тренер",
        "parent": "Родитель",
        "cashier": "Кассир"
    }

    role_system = {
        "trainer": ROLE_TRAINER,
        "parent": ROLE_PARENT,
        "cashier": ROLE_CASHIER
    }

    await state.update_data(role=role_system[role], role_name=role_names[role])
    await state.set_state(RegistrationStates.waiting_for_name)

    await callback.message.edit_text(
        f"👤 Роль: {role_names[role]}\n\n"
        f"Введите ваше полное имя:",
        reply_markup=get_back_button()
    )


@registration_router.message(StateFilter(RegistrationStates.waiting_for_name))
async def process_name(message: Message, state: FSMContext):
    """Обработка имени пользователя"""
    full_name = message.text.strip()
    data = await state.get_data()

    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationStates.waiting_for_phone)

    await message.answer(
        f"👤 {data['role_name']}: {full_name}\n\n"
        f"Введите номер телефона (или напишите 'пропустить'):"
    )


@registration_router.message(StateFilter(RegistrationStates.waiting_for_phone))
async def process_phone(message: Message, state: FSMContext):
    """Обработка номера телефона"""
    phone = message.text.strip() if message.text.strip().lower() != 'пропустить' else None
    data = await state.get_data()

    # Создаём пользователя
    name_parts = data['full_name'].split()
    first_name = name_parts[0] if name_parts else data['full_name']
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    user_id = await db.create_user(
        message.from_user.id,
        message.from_user.username or "",
        first_name,
        last_name,
        data['role']
    )

    # Если роль тренера, нужно найти существующего тренера или создать нового
    if data['role'] == ROLE_TRAINER:
        # Ищем существующего тренера с таким именем
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    "SELECT t.*, b.name as branch_name FROM trainers t "
                    "JOIN branches b ON t.branch_id = b.id "
                    "WHERE t.full_name = ? AND t.user_id IS NULL",  # Точное совпадение имени
                    (data['full_name'],)
            ) as cursor:
                existing_trainer = await cursor.fetchone()

            if existing_trainer:
                # Привязываем к существующему тренеру
                await conn.execute(
                    "UPDATE trainers SET user_id = ? WHERE id = ?",
                    (user_id, existing_trainer['id'])
                )
                await conn.commit()

                await message.answer(
                    f"✅ Регистрация завершена!\n\n"
                    f"👤 Имя: {data['full_name']}\n"
                    f"📱 Телефон: {phone or 'Не указан'}\n"
                    f"👨‍🏫 Роль: Тренер\n"
                    f"🏢 Филиал: {existing_trainer['branch_name']}\n\n"
                    f"Теперь вы можете использовать бот для управления тренировками!",
                    reply_markup=get_trainer_menu()
                )
            else:
                # Удаляем пользователя если тренер не найден
                await conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                await conn.commit()

                await message.answer(
                    f"⚠️ Тренер с именем '{data['full_name']}' не найден в системе.\n\n"
                    f"❗ Важно: имя должно точно совпадать с тем, которое указал администратор.\n\n"
                    f"Обратитесь к главному тренеру для:\n"
                    f"• Добавления вас в систему как тренера\n"
                    f"• Уточнения правильного написания вашего имени\n\n"
                    f"После этого попробуйте зарегистрироваться снова."
                )

    elif data['role'] == ROLE_PARENT:
        await message.answer(
            f"✅ Регистрация завершена!\n\n"
            f"👤 Имя: {data['full_name']}\n"
            f"📱 Телефон: {phone or 'Не указан'}\n"
            f"👤 Роль: Родитель\n\n"
            f"Теперь администратор может добавить ваших детей в группы.",
            reply_markup=get_parent_menu()
        )

    elif data['role'] == ROLE_CASHIER:
        await message.answer(
            f"✅ Регистрация завершена!\n\n"
            f"👤 Имя: {data['full_name']}\n"
            f"📱 Телефон: {phone or 'Не указан'}\n"
            f"💰 Роль: Кассир\n\n"
            f"Теперь вы можете принимать деньги от тренеров.",
            reply_markup=get_cashier_menu()
        )

    # Логируем регистрацию
    await db.add_log(user_id, "user_registered", f"Role: {data['role']}, Name: {data['full_name']}")

    await state.clear()


@registration_router.callback_query(F.data == "back_to_registration", StateFilter(RegistrationStates))
async def back_to_registration(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору роли"""
    await state.set_state(RegistrationStates.waiting_for_role)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="👨‍🏫 Тренер", callback_data="role_trainer"),
        InlineKeyboardButton(text="👤 Родитель", callback_data="role_parent")
    )
    keyboard.row(
        InlineKeyboardButton(text="💰 Кассир", callback_data="role_cashier")
    )

    await callback.message.edit_text(
        "👋 Добро пожаловать в систему футбольной академии!\n\n"
        "Выберите вашу роль:",
        reply_markup=keyboard.as_markup()
    )