from src.app.core.database import SessionLocal
from sqlalchemy import text

try:
    db = SessionLocal()
    result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs' ORDER BY ordinal_position"))
    print("Jobs table columns:")
    columns = []
    for row in result:
        columns.append(row[0])
        print(f"  - {row[0]}")
    db.close()
    print(f"\nTotal columns: {len(columns)}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
