from sqlalchemy.orm import Session
from src.app.core.database import SessionLocal
from src.app.models.user import User

# If credit are tracked in the Subscriber table, import Subscriber as well:
from src.app.models.user import Subscriber

def add_credits_to_user(email: str, credits_to_add: int):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"User with email {email} not found.")
            return
        # Find the subscriber record for this user
        subscriber = db.query(Subscriber).filter(Subscriber.user_id == user.id).first()
        if not subscriber:
            print(f"Subscriber record for user {email} not found.")
            return
        print(f"Current credits: {subscriber.current_credits}")
        subscriber.current_credits += credits_to_add
        db.commit()
        print(f"Added {credits_to_add} credits to {email}. New credits: {subscriber.current_credits}")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Example usage: add 100 credits
    add_credits_to_user("wasay.ahmad123@gmail.com", 100)
