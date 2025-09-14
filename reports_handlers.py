from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite
from datetime import date, timedelta, datetime

from database import db
from keyboards import get_back_button

reports_router = Router()


@reports_router.callback_query(F.data == "report_week")
async def report_week(callback: CallbackQuery):
    """Отчёт за неделю"""
    today = date.today()
    week_ago = today - timedelta(days=7)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Занятия за неделю
        async with conn.execute(
                """SELECT s.*, g.name as group_name, b.name as branch_name, t.full_name as trainer_name
                   FROM sessions s 
                   JOIN groups_table g ON s.group_id = g.id 
                   JOIN branches b ON g.branch_id = b.id 
                   JOIN trainers t ON s.trainer_id = t.id 
                   WHERE DATE(s.start_time) >= ? 
                   ORDER BY s.start_time DESC
                   LIMIT 20""", (week_ago.isoformat(),)
        ) as cursor:
            sessions = await cursor.fetchall()

        # Статистика за неделю
        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE DATE(start_time) >= ?", (week_ago.isoformat(),)
        ) as cursor:
            total_sessions = (await cursor.fetchone())[0]

        # Оплаты за неделю
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE DATE(payment_date) >= ?", (week_ago.isoformat(),)
        ) as cursor:
            week_payments = (await cursor.fetchone())[0]

        # Средняя посещаемость за неделю
        async with conn.execute(
                """SELECT ROUND(AVG(CASE WHEN a.status = 'present' THEN 100.0 ELSE 0.0 END), 1)
                   FROM attendance a 
                   JOIN sessions s ON a.session_id = s.id 
                   WHERE DATE(s.start_time) >= ?""", (week_ago.isoformat(),)
        ) as cursor:
            result = await cursor.fetchone()
            avg_attendance = result[0] if result[0] is not None else 0

    text = f"📊 Отчёт за неделю ({week_ago.strftime('%d.%m')} - {today.strftime('%d.%m.%Y')})\n\n"

    if total_sessions == 0:
        text += "❌ За неделю занятий не было."
    else:
        training_count = sum(1 for s in sessions if s['type'] == 'training')
        game_count = sum(1 for s in sessions if s['type'] == 'game')

        text += f"📈 Общая статистика:\n"
        text += f"   Всего занятий: {total_sessions}\n"
        text += f"   🏃 Тренировки: {training_count}\n"
        text += f"   ⚽ Игры: {game_count}\n"
        text += f"   💰 Получено денег: {week_payments:.0f} руб.\n"
        text += f"   📈 Средняя посещаемость: {avg_attendance}%\n\n"

        text += "📋 Последние занятия:\n"
        for session in sessions[:10]:  # Показываем только последние 10
            start_time = session['start_time']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)

            session_type = "🏃" if session['type'] == 'training' else "⚽"
            text += f"{session_type} {start_time.strftime('%d.%m %H:%M')} - {session['group_name']} ({session['trainer_name']})\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())


@reports_router.callback_query(F.data == "report_month")
async def report_month(callback: CallbackQuery):
    """Отчёт за месяц"""
    today = date.today()
    month_ago = today - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Статистика за месяц
        async with conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE DATE(start_time) >= ?", (month_ago.isoformat(),)
        ) as cursor:
            total_sessions = (await cursor.fetchone())[0]

        # Статистика по типам занятий
        async with conn.execute(
                "SELECT type, COUNT(*) FROM sessions WHERE DATE(start_time) >= ? GROUP BY type",
                (month_ago.isoformat(),)
        ) as cursor:
            session_types = await cursor.fetchall()

        # Статистика по филиалам
        async with conn.execute(
                """SELECT b.name as branch_name, COUNT(s.id) as sessions_count,
                          COUNT(DISTINCT a.child_id) as unique_children,
                          ROUND(AVG(CASE WHEN a.status = 'present' THEN 100.0 ELSE 0.0 END), 1) as attendance_rate
                   FROM branches b
                   LEFT JOIN groups_table g ON b.id = g.branch_id
                   LEFT JOIN sessions s ON g.id = s.group_id AND DATE(s.start_time) >= ?
                   LEFT JOIN attendance a ON s.id = a.session_id
                   GROUP BY b.id, b.name
                   ORDER BY sessions_count DESC""", (month_ago.isoformat(),)
        ) as cursor:
            branch_stats = await cursor.fetchall()

        # Финансовая статистика за месяц
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE DATE(payment_date) >= ?", (month_ago.isoformat(),)
        ) as cursor:
            month_income = (await cursor.fetchone())[0]

        # Топ тренеры по количеству занятий
        async with conn.execute(
                """SELECT t.full_name, COUNT(s.id) as sessions_count
                   FROM trainers t
                   LEFT JOIN sessions s ON t.id = s.trainer_id AND DATE(s.start_time) >= ?
                   GROUP BY t.id, t.full_name
                   HAVING sessions_count > 0
                   ORDER BY sessions_count DESC
                   LIMIT 5""", (month_ago.isoformat(),)
        ) as cursor:
            top_trainers = await cursor.fetchall()

    text = f"📊 Отчёт за месяц ({month_ago.strftime('%d.%m')} - {today.strftime('%d.%m.%Y')})\n\n"

    if total_sessions == 0:
        text += "❌ За месяц занятий не было."
    else:
        text += f"📈 Общая статистика:\n"
        text += f"   Всего занятий: {total_sessions}\n"

        for session_type in session_types:
            type_name = "🏃 Тренировки" if session_type['type'] == 'training' else "⚽ Игры"
            text += f"   {type_name}: {session_type[1]}\n"

        text += f"   💰 Доходы: {month_income:.0f} руб.\n\n"

        text += "🏢 Статистика по филиалам:\n"
        for branch in branch_stats:
            if branch['sessions_count'] and branch['sessions_count'] > 0:
                attendance = branch['attendance_rate'] if branch['attendance_rate'] else 0
                text += f"   📍 {branch['branch_name']}: {branch['sessions_count']} занятий, посещаемость {attendance:.1f}%\n"

        text += "\n🏆 Топ тренеры по активности:\n"
        for i, trainer in enumerate(top_trainers, 1):
            text += f"   {i}. {trainer['full_name']}: {trainer['sessions_count']} занятий\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())


@reports_router.callback_query(F.data == "report_finance")
async def report_finance(callback: CallbackQuery):
    """Подробный финансовый отчёт"""
    today = date.today()
    month_ago = today - timedelta(days=30)

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Общие финансы
        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'with_trainer'"
        ) as cursor:
            money_with_trainers = (await cursor.fetchone())[0]

        async with conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'in_cashbox'"
        ) as cursor:
            money_in_cashbox = (await cursor.fetchone())[0]

        # Доходы по месяцам
        async with conn.execute(
                """SELECT month_year, COALESCE(SUM(amount), 0) as total
                   FROM payments 
                   GROUP BY month_year 
                   ORDER BY month_year DESC
                   LIMIT 6"""
        ) as cursor:
            monthly_income = await cursor.fetchall()

        # Топ плательщики
        async with conn.execute(
                """SELECT c.full_name, COALESCE(SUM(p.amount), 0) as total_paid
                   FROM children c
                   LEFT JOIN payments p ON c.id = p.child_id
                   GROUP BY c.id, c.full_name
                   HAVING total_paid > 0
                   ORDER BY total_paid DESC
                   LIMIT 10"""
        ) as cursor:
            top_payers = await cursor.fetchall()

        # Статистика по тренерам (сколько денег собрал каждый)
        async with conn.execute(
                """SELECT t.full_name, 
                          COALESCE(SUM(CASE WHEN p.status = 'with_trainer' THEN p.amount ELSE 0 END), 0) as with_trainer,
                          COALESCE(SUM(CASE WHEN p.status = 'in_cashbox' THEN p.amount ELSE 0 END), 0) as in_cashbox,
                          COALESCE(SUM(p.amount), 0) as total
                   FROM trainers t
                   LEFT JOIN payments p ON t.id = p.trainer_id
                   GROUP BY t.id, t.full_name
                   HAVING total > 0
                   ORDER BY total DESC"""
        ) as cursor:
            trainer_finance = await cursor.fetchall()

    # Парсим месяцы для читаемого формата
    months_ru = {
        '01': 'Янв', '02': 'Фев', '03': 'Мар', '04': 'Апр',
        '05': 'Май', '06': 'Июн', '07': 'Июл', '08': 'Авг',
        '09': 'Сен', '10': 'Окт', '11': 'Ноя', '12': 'Дек'
    }

    text = f"💰 Подробный финансовый отчёт\n\n"

    text += f"💎 Общий баланс:\n"
    text += f"   У тренеров: {money_with_trainers:.0f} руб.\n"
    text += f"   В кассе: {money_in_cashbox:.0f} руб.\n"
    text += f"   Всего: {money_with_trainers + money_in_cashbox:.0f} руб.\n\n"

    if monthly_income:
        text += "📅 Доходы по месяцам:\n"
        for month_data in monthly_income:
            year, month = month_data['month_year'].split('-')
            month_name = months_ru.get(month, month)
            text += f"   {month_name} {year}: {month_data['total']:.0f} руб.\n"
        text += "\n"

    if trainer_finance:
        text += "👨‍🏫 Статистика по тренерам:\n"
        for trainer in trainer_finance[:5]:  # Топ 5
            text += f"   {trainer['full_name']}: {trainer['total']:.0f} руб. "
            if trainer['with_trainer'] > 0:
                text += f"(у тренера: {trainer['with_trainer']:.0f})\n"
            else:
                text += "(сдано в кассу)\n"

    if top_payers:
        text += "\n🏆 Топ плательщики:\n"
        for i, payer in enumerate(top_payers[:5], 1):
            text += f"   {i}. {payer['full_name']}: {payer['total_paid']:.0f} руб.\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())