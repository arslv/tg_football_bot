import os
from dotenv import load_dotenv
import pytz
from datetime import datetime

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Database configuration
DB_PATH = os.getenv("DB_PATH", "football_academy.db")

# User roles
ROLE_MAIN_TRAINER = "main_trainer"
ROLE_TRAINER = "trainer"
ROLE_PARENT = "parent"
ROLE_CASHIER = "cashier"

ADMIN_USER_IDS = [238658021]

# Timezone configuration
TIMEZONE = pytz.timezone('Asia/Tashkent')  # UTC+5

def get_current_time():
    """Получить текущее время в ташкентском часовом поясе"""
    return datetime.now(TIMEZONE)


def format_time(dt):
    """Форматировать время для отображения"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt).replace(tzinfo=pytz.UTC)
        dt = dt.astimezone(TIMEZONE)
    elif dt.tzinfo is None:
        dt = pytz.UTC.localize(dt).astimezone(TIMEZONE)
    return dt.strftime('%H:%M')

def format_date_time(dt):
    """Форматировать дату и время для отображения"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt).replace(tzinfo=pytz.UTC)
        dt = dt.astimezone(TIMEZONE)
    elif dt.tzinfo is None:
        dt = pytz.UTC.localize(dt).astimezone(TIMEZONE)
    return dt.strftime('%d.%m.%Y %H:%M')