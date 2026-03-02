import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='jobs' AND column_name='user_id'"
    )).fetchone()
    if result:
        conn.execute(text("ALTER TABLE jobs DROP COLUMN user_id"))
        conn.commit()
        print("SUCCESS: user_id column dropped from jobs table")
    else:
        print("SKIP: user_id column does not exist in jobs table")
