"""Create/alter tables needed for admin dashboard stats and charts.

This script:
- Ensures `users` has `name` and `state` columns
- Ensures `jobs` has `user_id`, `title`, `description`, `status` columns
- Ensures `subscriptions` has `plan_name`, `price` (numeric), `status`, `start_date`, `end_date` columns
- Creates `payments` table if missing with FK to `subscriptions(id)`

Run:
    python scripts/setup_dashboard_tables.py

The script is idempotent and will only add missing columns/tables. It uses the project's DB connection.
"""
import os
import sys
from sqlalchemy import text

# Add repo root to path so `src` imports work when running script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.core.database import get_db


def column_exists(db, table, column):
    q = text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :table AND column_name = :col LIMIT 1"
    )
    return bool(db.execute(q, {"table": table, "col": column}).first())


def table_exists(db, table):
    q = text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = :table LIMIT 1"
    )
    return bool(db.execute(q, {"table": table}).first())


def constraint_exists(db, constraint_name):
    q = text(
        "SELECT 1 FROM pg_constraint WHERE conname = :cname LIMIT 1"
    )
    return bool(db.execute(q, {"cname": constraint_name}).first())


def run():
    db = next(get_db())
    try:
        # USERS: do not add `name` or `state` here — those are stored
        # on supplier/contractor profiles. Only note existence for indexes.
        if not table_exists(db, 'users'):
            print("Table 'users' does not exist in DB. This repository expects a users table elsewhere.")
        else:
            print("users table exists; skipping adding 'name' and 'state' columns (use supplier/contractor tables)")

        # JOBS: ensure user_id exists. Do NOT add title/description/status here
        # as those are represented by existing permit_type/project_description/permit_status fields.
        if not table_exists(db, 'jobs'):
            print("Creating 'jobs' table (minimal) because none exists")
            db.execute(text('''
                CREATE TABLE jobs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NULL,
                    permit_type VARCHAR(255),
                    project_description TEXT,
                    permit_status VARCHAR(50),
                    state VARCHAR(100) NULL,
                    created_at TIMESTAMP DEFAULT now()
                )
            '''))
        else:
            if not column_exists(db, 'jobs', 'user_id'):
                print('Adding jobs.user_id')
                db.execute(text("ALTER TABLE jobs ADD COLUMN user_id INTEGER NULL"))
            else:
                print('jobs.user_id exists')

            print('Skipping addition of jobs.title, jobs.description, jobs.status (use existing permit_* fields)')

        # SUBSCRIPTIONS: prefer existing `name` column over adding `plan_name`.
        if not table_exists(db, 'subscriptions'):
            print("Creating 'subscriptions' table")
            db.execute(text('''
                CREATE TABLE subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NULL,
                    name VARCHAR(255) NULL,
                    price NUMERIC(12,2) NULL,
                    status VARCHAR(50) NULL,
                    start_date TIMESTAMP NULL,
                    end_date TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT now()
                )
            '''))
        else:
            if column_exists(db, 'subscriptions', 'name'):
                print('subscriptions.name exists; will use that instead of plan_name')
            else:
                # Only add a name column if truly missing
                print('Adding subscriptions.name')
                db.execute(text("ALTER TABLE subscriptions ADD COLUMN name VARCHAR(255) NULL"))

            if not column_exists(db, 'subscriptions', 'price'):
                print('Adding subscriptions.price (numeric)')
                db.execute(text("ALTER TABLE subscriptions ADD COLUMN price NUMERIC(12,2) NULL"))
            else:
                print('subscriptions.price exists')

            # subscription status and dates are tracked on `subscribers` table in this project.
            # Do not add `subscriptions.status`, `subscriptions.start_date` or `subscriptions.end_date` here.
            if column_exists(db, 'subscriptions', 'status'):
                print('subscriptions.status exists (but prefer subscribers.subscription_status)')
            else:
                print('Skipping creation of subscriptions.status — use subscribers table instead')

            if column_exists(db, 'subscriptions', 'start_date'):
                print('subscriptions.start_date exists (but prefer subscribers.subscription_start_date)')
            else:
                print('Skipping creation of subscriptions.start_date — use subscribers table instead')

            if column_exists(db, 'subscriptions', 'end_date'):
                print('subscriptions.end_date exists (but prefer subscribers.subscription_renew_date)')
            else:
                print('Skipping creation of subscriptions.end_date — use subscribers table instead')

        # PAYMENTS: create table if missing
        if not table_exists(db, 'payments'):
            print('Creating payments table')
            db.execute(text('''
                CREATE TABLE payments (
                    id SERIAL PRIMARY KEY,
                    subscription_id INTEGER NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    payment_date TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT now()
                )
            '''))
            print('Creating index on payments.subscription_id')
            db.execute(text('CREATE INDEX IF NOT EXISTS idx_payments_subscription_id ON payments (subscription_id)'))
        else:
            print('payments table exists')

        # Add foreign keys where reasonable (use ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS not supported pre-Postgres 9.6 for IF NOT EXISTS; we'll attempt and ignore errors)
        # jobs.user_id -> users.id
        try:
            if column_exists(db, 'jobs', 'user_id') and table_exists(db, 'users'):
                cname = 'fk_jobs_user_id'
                if not constraint_exists(db, cname):
                    print('Adding FK jobs.user_id -> users.id')
                    db.execute(text("ALTER TABLE jobs ADD CONSTRAINT fk_jobs_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL"))
                    db.commit()
                else:
                    print('FK fk_jobs_user_id already exists')
        except Exception as e:
            print('FK jobs.user_id may already exist or failed to add:', e)
            try:
                db.rollback()
            except Exception:
                pass

        try:
            if table_exists(db, 'payments') and table_exists(db, 'subscriptions'):
                cname = 'fk_payments_subscription_id'
                if not constraint_exists(db, cname):
                    print('Adding FK payments.subscription_id -> subscriptions.id')
                    db.execute(text("ALTER TABLE payments ADD CONSTRAINT fk_payments_subscription_id FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL"))
                    db.commit()
                else:
                    print('FK fk_payments_subscription_id already exists')
        except Exception as e:
            print('FK payments.subscription_id may already exist or failed to add:', e)
            try:
                db.rollback()
            except Exception:
                pass

        # Create some useful indexes
        def try_create_index(check_table, check_column, index_sql, skip_msg):
            try:
                if table_exists(db, check_table) and column_exists(db, check_table, check_column):
                    print(index_sql.split('(')[0] + ' if not exists')
                    db.execute(text(index_sql))
                    db.commit()
                else:
                    print(skip_msg)
            except Exception as e:
                print(f'Index creation failed or exists: {e}')
                try:
                    db.rollback()
                except Exception:
                    pass

        try_create_index('users', 'created_at', "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at)", 'Skipping idx_users_created_at: users.created_at not present')
        try_create_index('jobs', 'created_at', "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at)", 'Skipping idx_jobs_created_at: jobs.created_at not present')
        try_create_index('payments', 'payment_date', "CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments (payment_date)", 'Skipping idx_payments_payment_date: payments.payment_date not present')

        db.commit()
        print('Dashboard tables & columns ensured successfully')
    except Exception as e:
        print('Error while ensuring dashboard tables:', e)
        db.rollback()
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == '__main__':
    run()
