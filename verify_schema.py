#!/usr/bin/env python
"""Quick verification that rejection_note column exists"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import inspect
from src.app.core.database import engine

inspector = inspect(engine)
columns = inspector.get_columns("pending_jurisdictions")
print("Columns in pending_jurisdictions table:")
for col in columns:
    print(f'  - {col["name"]}: {col["type"]}')

# Check if rejection_note exists
col_names = [col["name"] for col in columns]
if "rejection_note" in col_names:
    print("\n✓ rejection_note column exists - Migration successful!")
    sys.exit(0)
else:
    print("\n✗ rejection_note column NOT found - Migration failed!")
    sys.exit(1)
