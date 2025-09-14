import asyncio
import aiosqlite
from datetime import datetime, date
from aiogram import Bot
from database import db


class DailyReportService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_daily_report(self):
        """Отправка ежедневного отчёта в 21:00"""
        try:
            today = date.today().isoformat()

            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row

                # Получаем все сессии за сегодня
                async with conn.execute(
                        """SELECT s.*, g.name as group_name, b.name as branch_name, 
                                  t.full_name as trainer_name, t.id as trainer_id
                           FROM sessions s 
                           JOIN groups_table g ON s.group_id = g.id 
                           JOIN branches b ON g.branch_id = b.id 
                           JOIN trainers t ON s.trainer_id = t.id 
                           WHERE DATE(s.start_time) = ?
                           ORDER BY s.start_time""", (today,)
                ) as cursor:
                    sessions = await cursor.fetchall()

                # Получаем статистику по филиалам
                async with conn.execute(
                        """SELECT b.name as branch_name, 
                                  COUNT(DISTINCT s.id) as sessions_count,
                                  COUNT(DISTINCT CASE WHEN a.status = 'present' THEN a.child_id END) as present_count,
                                  COUNT(DISTINCT a.child_id) as total_children,
                                  COALESCE(SUM(CASE WHEN DATE(p.payment_date) = ? THEN p.amount ELSE 0 END), 0) as received_money,
                                  COALESCE(SUM(CASE WHEN DATE(p.cashbox_date) = ? THEN p.amount ELSE 0 END), 0) as cashbox_money
                           FROM branches b 
                           LEFT JOIN groups_table g ON b.id = g.branch_id 
                           LEFT JOIN sessions s ON g.id = s.group_id AND DATE(s.start_time) = ?
                           LEFT JOIN attendance a ON s.id = a.session_id 
                           LEFT JOIN children c ON g.id = c.group_id 
                           LEFT JOIN payments p ON c.id = p.child_id
                           GROUP BY b.id, b.name 
                           ORDER BY b.name""", (today, today, today)
                ) as cursor:
                    branch_stats = await cursor.fetchall()

                # Получаем незакрытые тренировки
                async with conn.execute(
                        """SELECT s.*, t.full_name as trainer_name, g.name as group_name
                           FROM sessions s 
                           JOIN trainers t ON s.trainer_id = t.id 
                           JOIN groups_table g ON s.group_id = g.id 
                           WHERE DATE(s.start_time) = ? AND s.status = 'started'""", (today,)
                ) as cursor:
                    unclosed_sessions = await cursor.fetchall()

                async with conn.execute(
                        "SELECT telegram_id FROM users WHERE role = 'main_trainer' AND is_active = TRUE"
                ) as cursor:
                    main_trainers = await cursor.fetchall()

            # Формируем отчёт
            today_date = date.today()
            report = f"📊 Ежедневный отчёт за {today_date.strftime('%d.%m.%Y')}\n\n"

            if sessions:
                report += f"📅 Всего занятий: {len(sessions)}\n"
                training_count = sum(1 for s in sessions if s['type'] == 'training')
                game_count = sum(1 for s in sessions if s['type'] == 'game')
                report += f"🏃 Тренировки: {training_count}\n"
                report += f"⚽ Игры: {game_count}\n\n"

                report += "🏢 Статистика по филиалам:\n"
                for branch in branch_stats:
                    if branch['sessions_count'] > 0:
                        report += (
                            f"📍 {branch['branch_name']}\n"
                            f"   Занятий: {branch['sessions_count']}\n"
                            f"   Присутствовало: {branch['present_count']}/{branch['total_children']}\n"
                            f"   Получено: {branch['received_money']:.0f} руб.\n"
                            f"   Сдано в кассу: {branch['cashbox_money']:.0f} руб.\n\n"
                        )

                if unclosed_sessions:
                    report += "⚠️ Незакрытые занятия:\n"
                    for session in unclosed_sessions:
                        start_time = session['start_time']
                        if isinstance(start_time, str):
                            start_time = datetime.fromisoformat(start_time)
                        report += f"• {session['trainer_name']} - {session['group_name']} (с {start_time.strftime('%H:%M')})\n"
            else:
                report += "Сегодня занятий не было."

            # Отправляем главному тренеру
            for trainer in main_trainers:
                try:
                    await self.bot.send_message(trainer['telegram_id'], report)
                except Exception as e:
                    print(f"Ошибка отправки ежедневного отчёта: {e}")

        except Exception as e:
            print(f"Ошибка в send_daily_report: {e}")


# Функция для планировщика ежедневных отчётов
async def schedule_daily_reports(bot: Bot):
    """Планировщик ежедневных отчётов"""
    import schedule
    import time

    daily_report_service = DailyReportService(bot)

    def job():
        asyncio.create_task(daily_report_service.send_daily_report())

    schedule.every().day.at("21:00").do(job)

    while True:
        schedule.run_pending()
        await asyncio.sleep(60)  # Проверяем каждую минуту