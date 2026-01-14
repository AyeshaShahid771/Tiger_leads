from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
conn = engine.connect()

result = conn.execute(text('SELECT id, name, has_stay_active_bonus, has_bonus_credits, has_boost_pack FROM subscriptions WHERE id=4'))
row = result.fetchone()
print(f'Enterprise (ID {row[0]}): name={row[1]}, Stay={row[2]}, Bonus={row[3]}, Boost={row[4]}')
