from aiogram import Router
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from states import AdminStates, RegistrationStates, SessionStates, PaymentStates

unknown_router = Router()


@unknown_router.message(~StateFilter(
    AdminStates, RegistrationStates, SessionStates, PaymentStates
))
async def unknown_message(message: Message, state: FSMContext):
    """Обработка неизвестных сообщений (только когда не в стейте)"""
    current_state = await state.get_state()

    # Если пользователь не в стейте, отправляем сообщение о неизвестной команде
    if current_state is None:
        await message.answer(
            "❓ Команда не распознана. Используйте /start для входа в меню."
        )