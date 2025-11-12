# add_worker.py - скрипт для добавления воркеров
import sqlite3

def add_worker(worker_id, worker_name=None):
    conn = sqlite3.connect('gift_monitor.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT OR REPLACE INTO workers (worker_id, worker_name) VALUES (?, ?)',
        (worker_id, worker_name or f"Worker_{worker_id}")
    )
    
    conn.commit()
    conn.close()
    print(f"✅ Воркер {worker_id} добавлен")

# Добавляем админа как воркера
add_worker("6038457276", "KA_RL_WOrk")

# Можно добавить других воркеров
# add_worker("123456789", "Worker_Name")