from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_main_trainer_menu():
    """Главное меню для главного тренера"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="mt_statistics"),
        InlineKeyboardButton(text="💰 Финансы", callback_data="mt_finance")
    )
    keyboard.row(
        InlineKeyboardButton(text="🏢 Филиалы", callback_data="mt_branches"),
        InlineKeyboardButton(text="👥 Тренеры", callback_data="mt_trainers")
    )
    keyboard.row(
        InlineKeyboardButton(text="👶 Группы и дети", callback_data="mt_groups"),
        InlineKeyboardButton(text="📋 Отчёты", callback_data="mt_reports")
    )
    return keyboard.as_markup()


def get_trainer_menu():
    """Главное меню для тренера"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🏃 Начать тренировку", callback_data="start_training"),
        InlineKeyboardButton(text="⚽ Начать игру", callback_data="start_game")
    )
    keyboard.row(
        InlineKeyboardButton(text="✅ Завершить занятие", callback_data="end_session"),
        InlineKeyboardButton(text="👥 Перекличка", callback_data="attendance")
    )
    keyboard.row(
        InlineKeyboardButton(text="💰 Оплата", callback_data="payment"),
        InlineKeyboardButton(text="💵 Сдать в кассу", callback_data="to_cashbox")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="trainer_stats")
    )
    return keyboard.as_markup()


def get_parent_menu():
    """Главное меню для родителя"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="👶 Мои дети", callback_data="my_children"),
        InlineKeyboardButton(text="📊 Посещаемость", callback_data="attendance_history")
    )
    keyboard.row(
        InlineKeyboardButton(text="💰 История оплат", callback_data="payment_history")
    )
    return keyboard.as_markup()


def get_cashier_menu():
    """Главное меню для кассира"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="💰 Принять деньги", callback_data="accept_money"),
        InlineKeyboardButton(text="📋 Список сумм", callback_data="pending_payments")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 Финансовый отчёт", callback_data="financial_report")
    )
    return keyboard.as_markup()


def get_back_button():
    """Кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")]
    ])


def get_location_request():
    """Кнопка для запроса геолокации"""
    keyboard = ReplyKeyboardBuilder()
    keyboard.row(KeyboardButton(text="📍 Отправить геолокацию", request_location=True))
    keyboard.row(KeyboardButton(text="❌ Отмена"))
    return keyboard.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_children_keyboard(children):
    """Клавиатура со списком детей"""
    keyboard = InlineKeyboardBuilder()
    for child in children:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👶 {child['full_name']}",
                callback_data=f"child_{child['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))
    return keyboard.as_markup()


def get_attendance_keyboard(children, session_id):
    """Клавиатура для переклички"""
    keyboard = InlineKeyboardBuilder()
    for child in children:
        keyboard.row(
            InlineKeyboardButton(
                text=f"✅ {child['full_name']}",
                callback_data=f"present_{session_id}_{child['id']}"
            ),
            InlineKeyboardButton(
                text=f"❌ {child['full_name']}",
                callback_data=f"absent_{session_id}_{child['id']}"
            )
        )
    keyboard.row(
        InlineKeyboardButton(text="✅ Завершить перекличку", callback_data="finish_attendance"),
        InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu")
    )
    return keyboard.as_markup()


def get_payment_keyboard(children):
    """Клавиатура для отметки оплат"""
    keyboard = InlineKeyboardBuilder()
    for child in children:
        keyboard.row(
            InlineKeyboardButton(
                text=f"💰 {child['full_name']}",
                callback_data=f"payment_{child['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))
    return keyboard.as_markup()


def get_confirm_keyboard(action_data):
    """Клавиатура подтверждения действия"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action_data}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")
    )
    return keyboard.as_markup()


def get_trainers_keyboard(trainers):
    """Клавиатура со списком тренеров для кассира"""
    keyboard = InlineKeyboardBuilder()
    for trainer in trainers:
        keyboard.row(
            InlineKeyboardButton(
                text=f"👨‍🏫 {trainer['full_name']}",
                callback_data=f"trainer_payments_{trainer['id']}"
            )
        )
    keyboard.row(InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_menu"))
    return keyboard.as_markup()


def get_amount_keyboard():
    """Клавиатура для ввода суммы"""
    keyboard = InlineKeyboardBuilder()
    amounts = [100000, 150000, 200000, 250000]  # Новые суммы
    for amount in amounts:
        keyboard.row(
            InlineKeyboardButton(text=f"{amount:,} руб".replace(',', ' '), callback_data=f"amount_{amount}")
        )
    keyboard.row(
        InlineKeyboardButton(text="✏️ Другая сумма", callback_data="custom_amount"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")
    )
    return keyboard.as_markup()


def get_month_keyboard():
    """Клавиатура для выбора месяца оплаты"""
    keyboard = InlineKeyboardBuilder()
    months = [
        ("Январь", "2025-01"), ("Февраль", "2025-02"), ("Март", "2025-03"),
        ("Апрель", "2025-04"), ("Май", "2025-05"), ("Июнь", "2025-06"),
        ("Июль", "2025-07"), ("Август", "2025-08"), ("Сентябрь", "2025-09"),
        ("Октябрь", "2025-10"), ("Ноябрь", "2025-11"), ("Декабрь", "2025-12")
    ]

    for month_name, month_code in months:
        keyboard.row(
            InlineKeyboardButton(text=month_name, callback_data=f"month_{month_code}")
        )

    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu"))
    return keyboard.as_markup()


def get_session_type_keyboard():
    """Клавиатура выбора типа занятия"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🏃 Тренировка", callback_data="session_training"),
        InlineKeyboardButton(text="⚽ Игра", callback_data="session_game")
    )
    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu"))
    return keyboard.as_markup()

def get_parent_menu():
    """Главное меню для родителя"""
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="👶 Мои дети", callback_data="my_children"),
        InlineKeyboardButton(text="📊 Посещаемость", callback_data="attendance_history")
    )
    keyboard.row(
        InlineKeyboardButton(text="💰 История оплат", callback_data="payment_history"),
        InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="add_child_request")
    )
    return keyboard.as_markup()