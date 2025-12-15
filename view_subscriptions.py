"""
Script to view all subscription tiers with their pricing information.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(DATABASE_URL)

# Query subscriptions
with engine.connect() as conn:
    result = conn.execute(
        text(
            "SELECT id, name, price, credits, max_seats, credit_price, seat_price, stripe_price_id "
            "FROM subscriptions ORDER BY id"
        )
    )

    print("\n" + "=" * 130)
    print("SUBSCRIPTION TIERS")
    print("=" * 130)
    print(
        f"{'ID':<4} | {'Name':<12} | {'Price':<15} | {'Credits':<8} | {'Seats':<6} | {'Credit_Price':<13} | {'Seat_Price':<11} | {'Stripe_Price_ID':<20}"
    )
    print("-" * 130)

    for row in result:
        print(
            f"{row[0]:<4} | {row[1]:<12} | {row[2]:<15} | {row[3]:<8} | {row[4]:<6} | {row[5] or 'NULL':<13} | {row[6] or 'NULL':<11} | {row[7] or 'NULL':<20}"
        )

    print("=" * 130 + "\n")
    print("=" * 130 + "\n")
