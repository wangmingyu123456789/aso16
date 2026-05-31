import sqlite3
import app.models.db  # noqa: F401
conn = sqlite3.connect(app.models.db.DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT id, assistant_name, assistant_code, prompt_template, sort_order FROM assistants ORDER BY sort_order').fetchall()
for r in rows:
    print(f'{r["id"]}: {r["assistant_name"]} (code={r["assistant_code"]}, sort={r["sort_order"]})')
    if r['assistant_code'] == 'poison_chicken_soup':
        print(f'  Prompt preview: {r["prompt_template"][:80]}...')
conn.close()
