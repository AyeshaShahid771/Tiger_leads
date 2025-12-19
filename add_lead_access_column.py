"""
Script: add_lead_access_column.py

Adds a `lead_access` column ?
(TEXT) to the `subscriptions` table if it doesn't
exist, and populates the three standard tiers with the requested descriptions.

Run:
    python add_lead_access_column.py

This script uses the application SQLAlchemy `engine` (from
`src.app.core.database`) so it will use the same `DATABASE_URL` configuration.
"""

from sqlalchemy import text

from src.app.core.database import engine

MAPPING = {
    "Starter": "Upto 40% of all available leads",
    "Professional": "Upto 75% of all available leads",
    "Enterprise": "100% of all available leads",
}

PCT_MAP = {
    "Starter": 40,
    "Professional": 75,
    "Enterprise": 100,
}


def main():
    print("Connecting to database via engine from src.app.core.database...")
    with engine.begin() as conn:
        # Check if table exists
        has_table = conn.execute(
            text("SELECT to_regclass('public.subscriptions')"),
        ).scalar()
        if not has_table:
            print(
                "Error: `subscriptions` table does not exist in the connected database."
            )
            return

        # Check whether `lead_access` column exists
        col_exists = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='subscriptions' AND column_name='lead_access'"
            )
        ).fetchone()

        if col_exists:
            print("Column `lead_access` already exists — skipping ALTER TABLE.")
        else:
            print("Adding column `lead_access` to `subscriptions` table...")
            conn.execute(text("ALTER TABLE subscriptions ADD COLUMN lead_access TEXT;"))
            print("Column created.")

            # In some deployments the lead_access_pct column may not exist yet.
        pct_col = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='subscriptions' AND column_name='lead_access_pct'"
            )
        ).fetchone()

        if not pct_col:
            print("Column `lead_access_pct` does not exist — creating it now...")
            conn.execute(
                text("ALTER TABLE subscriptions ADD COLUMN lead_access_pct integer;")
            )
            print("Column `lead_access_pct` created.")

        # Populate lead_access descriptions for the standard tiers (case-insensitive matching)
        print(
            "Updating lead_access values for Starter / Professional (Pro) / Enterprise plans..."
        )
        name_patterns = {
            "Starter": ["%starter%", "%tier 1%"],
            "Professional": ["%professional%", "%tier 2%"],
            "Enterprise": ["%enterprise%", "%tier 3%", "%elite%"],
        }

        for logical_name, patterns in name_patterns.items():
            desc = MAPPING.get(logical_name) or MAPPING.get(logical_name.capitalize())
            total = 0
            for pat in patterns:
                result = conn.execute(
                    text(
                        "UPDATE subscriptions SET lead_access = :desc WHERE LOWER(name) LIKE :pat"
                    ),
                    {"desc": desc, "pat": pat},
                )
                total += result.rowcount
            print(f"Plan {logical_name}: updated {total} rows")

        # Optionally set lead_access_pct if missing (will only update NULL values)
        print("Ensuring lead_access_pct values are set (when NULL)...")
        for name, pct in PCT_MAP.items():
            result = conn.execute(
                text(
                    "UPDATE subscriptions SET lead_access_pct = :pct WHERE name = :name AND (lead_access_pct IS NULL)"
                ),
                {"pct": pct, "name": name},
            )
            print(
                f"Plan {name}: set lead_access_pct for {result.rowcount} rows (if were null)"
            )

    print(
        "Done. If you use an ORM metadata autogeneration or migrations tool, consider creating a formal migration for this change."
    )


if __name__ == "__main__":
    main()
