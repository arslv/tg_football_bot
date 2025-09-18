from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_for_role = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_branch = State()
    waiting_for_group = State()


class SessionStates(StatesGroup):
    waiting_for_location = State()
    waiting_for_session_type = State()
    in_attendance = State()


class PaymentStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_custom_amount = State()
    waiting_for_month = State()
    confirming_payment = State()


class AdminStates(StatesGroup):
    # Создание филиала
    creating_branch_name = State()
    creating_branch_address = State()

    # Создание тренера
    creating_trainer_name = State()
    selecting_trainer_branch = State()

    # Создание группы
    creating_group_name = State()
    selecting_group_branch = State()
    selecting_group_trainer = State()

    # Создание ребенка
    creating_child_name = State()
    selecting_child_parent = State()
    selecting_child_group = State()

    # СОСТОЯНИЯ ДЛЯ РЕДАКТИРОВАНИЯ

    # Редактирование филиала
    editing_branch_name = State()
    editing_branch_address = State()

    # Редактирование тренера
    editing_trainer_name = State()
    editing_trainer_branch = State()

    # Редактирование группы  
    editing_group_name = State()
    editing_group_trainer = State()

    # Редактирование ребёнка
    editing_child_name = State()
    editing_child_parent = State()
    editing_child_group = State()


class CashierStates(StatesGroup):
    confirming_payment_receipt = State()


class ParentStates(StatesGroup):
    requesting_child_name = State()
    requesting_child_age = State()
    editing_child_name = State()  # СОСТОЯНИЕ ДЛЯ РЕДАКТИРОВАНИЯ ИМЕНИ РЕБЁНКА