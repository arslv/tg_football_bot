import aiosqlite
from datetime import datetime
from database import db

# Расширяем класс Database дополнительными методами

async def create_child(self, full_name: str, parent_id: int, group_id: int):
    """Создание ребёнка"""
    async with aiosqlite.connect(self.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO children (full_name, parent_id, group_id) VALUES (?, ?, ?)",
            (full_name, parent_id, group_id)
        )
        await conn.commit()
        return cursor.lastrowid

async def get_children_by_group(self, group_id: int):
    """Получить детей группы"""
    async with aiosqlite.connect(self.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT c.*, u.telegram_id as parent_telegram_id, u.first_name as parent_name 
               FROM children c 
               JOIN users u ON c.parent_id = u.id 
               WHERE c.group_id = ? ORDER BY c.full_name""",
            (group_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_children_by_parent(self, parent_id: int):
    """Получить детей родителя"""
    async with aiosqlite.connect(self.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT c.*, g.name as group_name, b.name as branch_name 
               FROM children c 
               JOIN groups_table g ON c.group_id = g.id 
               JOIN branches b ON g.branch_id = b.id 
               WHERE c.parent_id = ?""",
            (parent_id,)
        ) as cursor:
            return await cursor.fetchall()

async def create_session(self, session_type: str, trainer_id: int, group_id: int, location_lat: float, location_lon: float):
    """Создание сессии (тренировки/игры)"""
    async with aiosqlite.connect(self.db_path) as conn:
        cursor = await conn.execute(
            """INSERT INTO sessions (type, trainer_id, group_id, start_time, location_lat, location_lon) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_type, trainer_id, group_id, datetime.now().isoformat(), location_lat, location_lon)
        )
        await conn.commit()
        return cursor.lastrowid

async def end_session(self, session_id: int):
    """Завершение сессии"""
    async with aiosqlite.connect(self.db_path) as conn:
        await conn.execute(
            "UPDATE sessions SET end_time = ?, status = 'completed' WHERE id = ?",
            (datetime.now().isoformat(), session_id)
        )
        await conn.commit()

async def get_active_session(self, trainer_id: int):
    """Получить активную сессию тренера"""
    async with aiosqlite.connect(self.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM sessions WHERE trainer_id = ? AND status = 'started' ORDER BY start_time DESC LIMIT 1",
            (trainer_id,)
        ) as cursor:
            return await cursor.fetchone()

async def mark_attendance(self, session_id: int, child_id: int, status: str):
    """Отметка посещаемости"""
    async with aiosqlite.connect(self.db_path) as conn:
        await conn.execute(
            """INSERT OR REPLACE INTO attendance (session_id, child_id, status) 
               VALUES (?, ?, ?)""",
            (session_id, child_id, status)
        )
        await conn.commit()

async def get_attendance_by_session(self, session_id: int):
    """Получить посещаемость по сессии"""
    async with aiosqlite.connect(self.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT a.*, c.full_name as child_name, c.parent_id 
               FROM attendance a 
               JOIN children c ON a.child_id = c.id 
               WHERE a.session_id = ?""",
            (session_id,)
        ) as cursor:
            return await cursor.fetchall()

async def create_payment(self, child_id: int, trainer_id: int, amount: float, month_year: str):
    """Создание платежа"""
    async with aiosqlite.connect(self.db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO payments (child_id, trainer_id, amount, month_year) VALUES (?, ?, ?, ?)",
            (child_id, trainer_id, amount, month_year)
        )
        await conn.commit()
        return cursor.lastrowid

async def get_payments_with_trainer(self, trainer_id: int):
    """Получить платежи у тренера"""
    async with aiosqlite.connect(self.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT p.*, c.full_name as child_name 
               FROM payments p 
               JOIN children c ON p.child_id = c.id 
               WHERE p.trainer_id = ? AND p.status = 'with_trainer' 
               ORDER BY p.payment_date DESC""",
            (trainer_id,)
        ) as cursor:
            return await cursor.fetchall()

async def move_payments_to_cashbox(self, trainer_id: int):
    """Перевод платежей в кассу"""
    async with aiosqlite.connect(self.db_path) as conn:
        await conn.execute(
            "UPDATE payments SET status = 'in_cashbox', cashbox_date = ? WHERE trainer_id = ? AND status = 'with_trainer'",
            (datetime.now().isoformat(), trainer_id)
        )
        await conn.commit()

async def get_all_payments_with_trainer(self):
    """Получить все платежи у тренеров"""
    async with aiosqlite.connect(self.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT p.*, c.full_name as child_name, t.full_name as trainer_name 
               FROM payments p 
               JOIN children c ON p.child_id = c.id 
               JOIN trainers t ON p.trainer_id = t.id 
               WHERE p.status = 'with_trainer' 
               ORDER BY p.payment_date DESC"""
        ) as cursor:
            return await cursor.fetchall()

async def add_log(self, user_id: int, action: str, details: str = None):
    """Добавление лога"""
    async with aiosqlite.connect(self.db_path) as conn:
        await conn.execute(
            "INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details)
        )
        await conn.commit()

# Добавляем методы к классу Database
from database import Database

Database.create_child = create_child
Database.get_children_by_group = get_children_by_group
Database.get_children_by_parent = get_children_by_parent
Database.create_session = create_session
Database.end_session = end_session
Database.get_active_session = get_active_session
Database.mark_attendance = mark_attendance
Database.get_attendance_by_session = get_attendance_by_session
Database.create_payment = create_payment
Database.get_payments_with_trainer = get_payments_with_trainer
Database.move_payments_to_cashbox = move_payments_to_cashbox
Database.get_all_payments_with_trainer = get_all_payments_with_trainer
Database.add_log = add_log