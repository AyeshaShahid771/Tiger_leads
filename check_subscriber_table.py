from src.app.core.database import SessionLocal
from sqlalchemy import text

try:
    db = SessionLocal()
    result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%subscri%' ORDER BY table_name"))
    print("Tables with 'subscri' in name:")
    for row in result:
        print(f"  - {row[0]}")
    db.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
