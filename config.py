import os
from dotenv import load_dotenv

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