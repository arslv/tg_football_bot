import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot
from database import db


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def notify_session_started(self, session_id: int, session_type: str):
        """Уведомление о начале тренировки/игры"""
        try:
            # Получаем информацию о сессии
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                        """SELECT s.*, g.name as group_name, b.name as branch_name, t.full_name as trainer_name
                           FROM sessions s 
                           JOIN groups_table g ON s.group_id = g.id 
                           JOIN branches b ON g.branch_id = b.id 
                           JOIN trainers t ON s.trainer_id = t.id 
                           WHERE s.id = ?""", (session_id,)
                ) as cursor:
                    session_info = await cursor.fetchone()

                if not session_info:
                    return

                # Получаем всех детей группы и их родителей
                async with conn.execute(
                        """SELECT c.*, u.telegram_id as parent_telegram_id 
                           FROM children c 
                           JOIN users u ON c.parent_id = u.id 
                           WHERE c.group_id = ?""", (session_info['group_id'],)
                ) as cursor:
                    children = await cursor.fetchall()

                # Получаем главного тренера
                async with conn.execute(
                        "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
                ) as cursor:
                    main_trainers = await cursor.fetchall()

            # Формируем текст уведомления
            session_text = "Тренировка" if session_type == "training" else "Игра"
            start_time = session_info['start_time']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)

            message = (
                f"🏃 {session_text} началась!\n\n"
                f"📍 Группа: {session_info['group_name']}\n"
                f"🏢 Филиал: {session_info['branch_name']}\n"
                f"👨‍🏫 Тренер: {session_info['trainer_name']}\n"
                f"⏰ Время: {start_time.strftime('%H:%M')}"
            )

            # Отправляем родителям
            for child in children:
                try:
                    child_message = f"👶 Ребёнок: {child['full_name']}\n\n{message}"
                    await self.bot.send_message(child['parent_telegram_id'], child_message)
                except Exception as e:
                    print(f"Ошибка отправки родителю {child['parent_telegram_id']}: {e}")

            # Отправляем главному тренеру
            for trainer in main_trainers:
                try:
                    await self.bot.send_message(trainer['telegram_id'], message)
                except Exception as e:
                    print(f"Ошибка отправки главному тренеру {trainer['telegram_id']}: {e}")

        except Exception as e:
            print(f"Ошибка в notify_session_started: {e}")

    async def notify_session_ended(self, session_id: int):
        """Уведомление о завершении тренировки/игры"""
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                        """SELECT s.*, g.name as group_name, b.name as branch_name, t.full_name as trainer_name
                           FROM sessions s 
                           JOIN groups_table g ON s.group_id = g.id 
                           JOIN branches b ON g.branch_id = b.id 
                           JOIN trainers t ON s.trainer_id = t.id 
                           WHERE s.id = ?""", (session_id,)
                ) as cursor:
                    session_info = await cursor.fetchone()

                async with conn.execute(
                        """SELECT c.*, u.telegram_id as parent_telegram_id 
                           FROM children c 
                           JOIN users u ON c.parent_id = u.id 
                           WHERE c.group_id = ?""", (session_info['group_id'],)
                ) as cursor:
                    children = await cursor.fetchall()

                async with conn.execute(
                        "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
                ) as cursor:
                    main_trainers = await cursor.fetchall()

            session_text = "Тренировка" if session_info['type'] == "training" else "Игра"
            start_time = session_info['start_time']
            end_time = session_info['end_time']

            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)

            message = (
                f"✅ {session_text} завершена!\n\n"
                f"📍 Группа: {session_info['group_name']}\n"
                f"🏢 Филиал: {session_info['branch_name']}\n"
                f"👨‍🏫 Тренер: {session_info['trainer_name']}\n"
                f"⏰ Время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M') if end_time else 'Н/Д'}"
            )

            # Отправляем родителям
            for child in children:
                try:
                    child_message = f"👶 Ребёнок: {child['full_name']}\n\n{message}"
                    await self.bot.send_message(child['parent_telegram_id'], child_message)
                except Exception as e:
                    print(f"Ошибка отправки родителю: {e}")

            # Отправляем главному тренеру
            for trainer in main_trainers:
                try:
                    await self.bot.send_message(trainer['telegram_id'], message)
                except Exception as e:
                    print(f"Ошибка отправки главному тренеру: {e}")

        except Exception as e:
            print(f"Ошибка в notify_session_ended: {e}")

    async def notify_attendance(self, child_id: int, status: str, session_id: int):
        """Уведомление о посещаемости"""
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                        """SELECT c.*, u.telegram_id as parent_telegram_id, s.type as session_type
                           FROM children c 
                           JOIN users u ON c.parent_id = u.id 
                           JOIN sessions s ON s.id = ?
                           WHERE c.id = ?""", (session_id, child_id)
                ) as cursor:
                    child_info = await cursor.fetchone()

                if not child_info:
                    return

                session_text = "тренировке" if child_info['session_type'] == "training" else "игре"
                status_text = "присутствует" if status == "present" else "отсутствует"
                emoji = "✅" if status == "present" else "❌"

                message = f"{emoji} Ваш ребёнок {child_info['full_name']} {status_text} на {session_text}"

                await self.bot.send_message(child_info['parent_telegram_id'], message)

        except Exception as e:
            print(f"Ошибка в notify_attendance: {e}")

    async def notify_payment_received(self, child_id: int, amount: float, month_year: str):
        """Уведомление о получении оплаты"""
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                        """SELECT c.*, u.telegram_id as parent_telegram_id 
                           FROM children c 
                           JOIN users u ON c.parent_id = u.id 
                           WHERE c.id = ?""", (child_id,)
                ) as cursor:
                    child_info = await cursor.fetchone()

                async with conn.execute(
                        "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
                ) as cursor:
                    main_trainers = await cursor.fetchall()

                if not child_info:
                    return

                # Парсим месяц-год для читаемого формата
                year, month = month_year.split('-')
                months_ru = {
                    '01': 'Январь', '02': 'Февраль', '03': 'Март',
                    '04': 'Апрель', '05': 'Май', '06': 'Июнь',
                    '07': 'Июль', '08': 'Август', '09': 'Сентябрь',
                    '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
                }
                month_name = months_ru.get(month, month)

                # Уведомление родителю
                parent_message = (
                    f"💰 Оплата получена!\n\n"
                    f"👶 Ребёнок: {child_info['full_name']}\n"
                    f"💵 Сумма: {amount:.0f} руб.\n"
                    f"📅 За период: {month_name} {year}"
                )

                await self.bot.send_message(child_info['parent_telegram_id'], parent_message)

                # Уведомление главному тренеру
                trainer_message = (
                    f"💰 Тренер принял оплату\n\n"
                    f"👶 Ребёнок: {child_info['full_name']}\n"
                    f"💵 Сумма: {amount:.0f} руб.\n"
                    f"📅 За период: {month_name} {year}"
                )

                for trainer in main_trainers:
                    try:
                        await self.bot.send_message(trainer['telegram_id'], trainer_message)
                    except Exception as e:
                        print(f"Ошибка отправки главному тренеру: {e}")

        except Exception as e:
            print(f"Ошибка в notify_payment_received: {e}")

    async def notify_money_to_cashbox(self, trainer_id: int, total_amount: float):
        """Уведомление о сдаче денег в кассу"""
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                        "SELECT full_name FROM trainers WHERE id = ?", (trainer_id,)
                ) as cursor:
                    trainer_info = await cursor.fetchone()

                async with conn.execute(
                        "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
                ) as cursor:
                    main_trainers = await cursor.fetchall()

                if not trainer_info:
                    return

                message = (
                    f"💵 Деньги сданы в кассу\n\n"
                    f"👨‍🏫 Тренер: {trainer_info['full_name']}\n"
                    f"💰 Сумма: {total_amount:.0f} руб."
                )

                for trainer in main_trainers:
                    try:
                        await self.bot.send_message(trainer['telegram_id'], message)
                    except Exception as e:
                        print(f"Ошибка отправки главному тренеру: {e}")

        except Exception as e:
            print(f"Ошибка в notify_money_to_cashbox: {e}")