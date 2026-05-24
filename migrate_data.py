#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from app.models.db import get_connection
from datetime import datetime

conn = get_connection()

# Create a default task for existing data
count = conn.execute("SELECT COUNT(*) as c FROM outlook_data WHERE task_id=0").fetchone()['c']
if count > 0:
    cursor = conn.execute(
        "INSERT INTO outlook_tasks(keyword,source_ids,source_names,pages,page_size_step,ai_expand,ai_clean,total_count,status,create_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        ('历史数据迁移', '', '历史数据', 1, 10, 0, 0, count, 'completed', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    task_id = cursor.lastrowid
    conn.execute("UPDATE outlook_data SET task_id=? WHERE task_id=0", (task_id,))
    print(f"迁移了 {count} 条历史数据到任务 ID={task_id}")
else:
    print("没有需要迁移的历史数据")

conn.commit()
