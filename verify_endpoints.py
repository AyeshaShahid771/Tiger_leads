#!/usr/bin/env python
"""
Simple endpoint verification - checks if all handler functions exist
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

print("Starting endpoint verification...\n")

# Check all handler functions exist
handlers_to_check = [
    ("contractor", "update_contractor_location_info"),
    ("contractor", "update_contractor_trade_info"),
    ("supplier", "update_location_info"),
    ("supplier", "update_supplier_user_type"),
    ("profile", "get_profile_info"),
    ("admin_dashboard", "list_pending_jurisdictions"),
    ("admin_dashboard", "approve_pending_jurisdiction"),
    ("admin_dashboard", "reject_pending_jurisdiction"),
    ("admin_dashboard", "list_pending_user_types"),
    ("admin_dashboard", "approve_pending_user_type"),
    ("admin_dashboard", "reject_pending_user_type"),
    ("admin_dashboard", "decline_ingested_job"),
    ("jobs", "get_job_by_id"),
    ("jobs", "repost_declined_job"),
]

print("=" * 80)
print("ENDPOINT HANDLER VERIFICATION")
print("=" * 80 + "\n")

passed = 0
failed = 0

from src.app.api.endpoints import admin_dashboard, contractor, jobs, profile, supplier

module_map = {
    "contractor": contractor,
    "supplier": supplier,
    "profile": profile,
    "admin_dashboard": admin_dashboard,
    "jobs": jobs,
}

for module_name, handler_name in handlers_to_check:
    module = module_map[module_name]
    if hasattr(module, handler_name):
        print(f"✓ {module_name}.{handler_name}")
        passed += 1
    else:
        print(f"✗ {module_name}.{handler_name} - NOT FOUND")
        failed += 1

print("\n" + "=" * 80)
print(f"RESULT: {passed}/{len(handlers_to_check)} Handler functions found")
print("=" * 80 + "\n")

# Check compatibility_aliases router
from src.app.api.endpoints import compatibility_aliases

print("\nCompatibility Aliases Router Status:")
print(f"  Routes in router: {len(compatibility_aliases.router.routes)}")
print("  ✓ Compatibility aliases module loaded successfully\n")

sys.exit(0 if failed == 0 else 1)
