import sqlite3

conn = sqlite3.connect("data.db")  # 数据库文件名，不存在会自动创建
cursor = conn.cursor()

cursor.execute(
    "CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY, path TEXT, viewed BOOLEAN)"
)


def database_empty():
    cursor.execute("SELECT COUNT(*) FROM images")
    count = cursor.fetchone()[0]
    return count == 0


def delete_image(image_id):
    cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
    conn.commit()


def mark_viewed(image_id):
    cursor.execute("UPDATE images SET viewed = ? WHERE id = ?", (True, image_id))
    conn.commit()


def get_random_unviewed_image():
    cursor.execute(
        "SELECT * FROM images WHERE viewed = ? ORDER BY RANDOM() LIMIT 1", (False,)
    )
    return cursor.fetchone()


def reset_viewed():
    cursor.execute("UPDATE images SET viewed = ?", (False,))
    conn.commit()


def clear_images():
    cursor.execute("DELETE FROM images")
    conn.commit()


def close_database():
    conn.close()
