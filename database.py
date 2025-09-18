import aiosqlite
import asyncio
from datetime import datetime
from config import DB_PATH, get_current_time


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init_db(self):
        """Инициализация базы данных"""
        await self.create_tables()

    async def create_tables(self):
        """Создание таблиц"""
        async with aiosqlite.connect(self.db_path) as conn:
            # Включаем поддержку foreign keys
            await conn.execute("PRAGMA foreign_keys = ON")

            queries = [
                """
                CREATE TABLE IF NOT EXISTS branches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    role TEXT NOT NULL CHECK (role IN ('main_trainer', 'trainer', 'parent', 'cashier')),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS trainers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    branch_id INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS groups_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    branch_id INTEGER NOT NULL,
                    trainer_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE CASCADE,
                    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS children (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    parent_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK (type IN ('training', 'game')),
                    trainer_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    location_lat REAL,
                    location_lon REAL,
                    status TEXT DEFAULT 'started' CHECK (status IN ('started', 'completed')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    child_id INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('present', 'absent')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE,
                    UNIQUE(session_id, child_id)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id INTEGER NOT NULL,
                    trainer_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'with_trainer' CHECK (status IN ('with_trainer', 'in_cashbox')),
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cashbox_date TIMESTAMP,
                    month_year TEXT NOT NULL,
                    FOREIGN KEY (child_id) REFERENCES children(id) ON DELETE CASCADE,
                    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                );
                """
            ]

            for query in queries:
                await conn.execute(query)

            await conn.commit()

    async def close(self):
        """Закрытие соединения (для SQLite не требуется)"""
        pass

    # User methods
    async def create_user(self, telegram_id: int, username: str, first_name: str, last_name: str, role: str):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "INSERT INTO users (telegram_id, username, first_name, last_name, role) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, username, first_name, last_name, role)
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_user_by_telegram_id(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ? AND is_active = TRUE",
                    (telegram_id,)
            ) as cursor:
                return await cursor.fetchone()

    async def get_user_role(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                    "SELECT role FROM users WHERE telegram_id = ? AND is_active = TRUE",
                    (telegram_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    # Branch methods
    async def create_branch(self, name: str, address: str = None):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "INSERT INTO branches (name, address) VALUES (?, ?)",
                (name, address)
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_all_branches(self):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT * FROM branches ORDER BY name") as cursor:
                return await cursor.fetchall()

    # Trainer methods
    async def create_trainer(self, user_id: int, branch_id: int, full_name: str):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "INSERT INTO trainers (user_id, branch_id, full_name) VALUES (?, ?, ?)",
                (user_id, branch_id, full_name)
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_trainer_by_user_id(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    """SELECT t.*, b.name as branch_name 
                       FROM trainers t 
                       JOIN branches b ON t.branch_id = b.id 
                       WHERE t.user_id = ?""",
                    (user_id,)
            ) as cursor:
                return await cursor.fetchone()

    async def get_all_trainers(self):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    """SELECT t.*, u.telegram_id, b.name as branch_name 
                       FROM trainers t 
                       LEFT JOIN users u ON t.user_id = u.id 
                       JOIN branches b ON t.branch_id = b.id 
                       ORDER BY t.full_name"""
            ) as cursor:
                return await cursor.fetchall()

    # Group methods
    async def create_group(self, name: str, branch_id: int, trainer_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "INSERT INTO groups_table (name, branch_id, trainer_id) VALUES (?, ?, ?)",
                (name, branch_id, trainer_id)
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_groups_by_trainer(self, trainer_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    "SELECT * FROM groups_table WHERE trainer_id = ? ORDER BY name",
                    (trainer_id,)
            ) as cursor:
                return await cursor.fetchall()

    async def get_group_by_id(self, group_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                    """SELECT g.*, b.name as branch_name, t.full_name as trainer_name 
                       FROM groups_table g 
                       JOIN branches b ON g.branch_id = b.id 
                       JOIN trainers t ON g.trainer_id = t.id 
                       WHERE g.id = ?""",
                    (group_id,)
            ) as cursor:
                return await cursor.fetchone()

    # Дополнительные методы для детей и сессий
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
            current_time = get_current_time()
            cursor = await conn.execute(
                """INSERT INTO sessions (type, trainer_id, group_id, start_time, location_lat, location_lon) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_type, trainer_id, group_id, current_time.isoformat(), location_lat, location_lon)
            )
            await conn.commit()
            return cursor.lastrowid

    async def end_session(self, session_id: int):
        """Завершение сессии"""
        async with aiosqlite.connect(self.db_path) as conn:
            current_time = get_current_time()
            await conn.execute(
                "UPDATE sessions SET end_time = ?, status = 'completed' WHERE id = ?",
                (current_time.isoformat(), session_id)
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
            current_time = get_current_time()
            cursor = await conn.execute(
                "INSERT INTO payments (child_id, trainer_id, amount, month_year, payment_date) VALUES (?, ?, ?, ?, ?)",
                (child_id, trainer_id, amount, month_year, current_time.isoformat())
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_payments_with_trainer(self, trainer_id: int):
        """Получить платежи у тренера"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                """SELECT p.*, c.full_name as child_name, t.full_name as trainer_name 
                   FROM payments p 
                   JOIN children c ON p.child_id = c.id 
                   JOIN trainers t ON p.trainer_id = t.id
                   WHERE p.trainer_id = ? AND p.status = 'with_trainer' 
                   ORDER BY p.payment_date DESC""",
                (trainer_id,)
            ) as cursor:
                return await cursor.fetchall()

    async def move_payments_to_cashbox(self, trainer_id: int):
        """Перевод платежей в кассу"""
        async with aiosqlite.connect(self.db_path) as conn:
            current_time = get_current_time()
            await conn.execute(
                "UPDATE payments SET status = 'in_cashbox', cashbox_date = ? WHERE trainer_id = ? AND status = 'with_trainer'",
                (current_time.isoformat(), trainer_id)
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
            current_time = get_current_time()
            await conn.execute(
                "INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
                (user_id, action, details, current_time.isoformat())
            )
            await conn.commit()


# Global database instance
db = Database()