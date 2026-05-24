from app.models.db import get_connection
conn = get_connection()
conn.execute("UPDATE functions SET sort_order=3 WHERE code='base_roles'")
conn.execute("UPDATE functions SET sort_order=4 WHERE code='base_functions'")
conn.commit()
print("Updated sort order")
conn.close()
