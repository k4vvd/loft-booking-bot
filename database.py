import aiosqlite

DB_NAME = "loft.db"
db_connection = None  # глобальное соединение

# ----------------------
# Инициализация базы данных
# ----------------------
async def init_db():
    global db_connection
    db_connection = await aiosqlite.connect(DB_NAME)
    await db_connection.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            phone TEXT,
            date TEXT,
            time TEXT,
            hours INTEGER,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db_connection.commit()

# ----------------------
# Конвертация времени "HH:MM" в минуты
# ----------------------
def time_to_minutes(time_str):
    h, m = map(int, time_str.split(":"))
    return h * 60 + m

# ----------------------
# Проверка пересечения брони
# ----------------------
async def check_overlap(date: str, time: str, hours: int) -> bool:
    new_start = time_to_minutes(time)
    new_end = new_start + hours * 60

    async with db_connection.execute("SELECT time, hours FROM bookings WHERE date=?", (date,)) as cursor:
        rows = await cursor.fetchall()
        for existing_time, existing_hours in rows:
            exist_start = time_to_minutes(existing_time)
            exist_end = exist_start + existing_hours * 60
            if new_start < exist_end and new_end > exist_start:
                return True
    return False

# ----------------------
# Добавление брони
# ----------------------
async def add_booking(user_id, name, phone, date, time, hours):
    # Проверка пересечения ещё раз на всякий случай
    if await check_overlap(date, time, hours):
        return None
    async with db_connection.execute(
        "INSERT INTO bookings (user_id, name, phone, date, time, hours) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, phone, date, time, hours)
    ) as cursor:
        await db_connection.commit()
        return cursor.lastrowid