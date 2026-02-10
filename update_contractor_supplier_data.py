"""
Update contractor and supplier data
Updates user_type, state, and country_city for specific users
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

print("="*80)
print("UPDATING CONTRACTOR AND SUPPLIER DATA")
print("="*80)

# Update contractors
print("\n" + "="*80)
print("UPDATING CONTRACTORS")
print("="*80 + "\n")

contractors_updates = [
    {
        'user_id': 67,
        'user_type': ['erosion_materials', 'erosion_control_contractor', 'land_clearing_contractor', 
                      'electrical_contractor', 'low_voltage_contractor', 'drywall_sheetrock_contractor', 
                      'hood_suppression_contractor'],
        'state': ['FL'],
        'country_city': ['Hillsborough County']
    },
    {
        'user_id': 80,
        'user_type': ['erosion_materials', 'erosion_control_contractor', 'land_clearing_contractor', 
                      'electrical_contractor', 'low_voltage_contractor', 'drywall_sheetrock_contractor', 
                      'hood_suppression_contractor'],
        'state': ['FL'],
        'country_city': ['Hillsborough County']
    },
    {
        'user_id': 75,
        'user_type': ['erosion_materials', 'erosion_control_contractor', 'land_clearing_contractor', 
                      'electrical_contractor', 'low_voltage_contractor', 'drywall_sheetrock_contractor', 
                      'hood_suppression_contractor'],
        'state': ['FL'],
        'country_city': ['Hillsborough County']
    },
    {
        'user_id': 88,
        'user_type': ['erosion_materials', 'erosion_control_contractor', 'land_clearing_contractor', 
                      'electrical_contractor', 'low_voltage_contractor', 'drywall_sheetrock_contractor', 
                      'hood_suppression_contractor'],
        'state': ['FL'],
        'country_city': ['Hillsborough County']
    }
]

with engine.connect() as conn:
    for update in contractors_updates:
        print(f"Updating contractor user_id {update['user_id']}...")
        
        # Show before
        result = conn.execute(text("""
            SELECT user_type, state, country_city
            FROM contractors
            WHERE user_id = :user_id
        """), {'user_id': update['user_id']})
        before = result.fetchone()
        print(f"  BEFORE: user_type={before[0]}, state={before[1]}, country_city={before[2]}")
        
        # Update
        conn.execute(text("""
            UPDATE contractors
            SET user_type = :user_type,
                state = :state,
                country_city = :country_city
            WHERE user_id = :user_id
        """), update)
        
        # Show after
        result = conn.execute(text("""
            SELECT user_type, state, country_city
            FROM contractors
            WHERE user_id = :user_id
        """), {'user_id': update['user_id']})
        after = result.fetchone()
        print(f"  AFTER:  user_type={after[0]}, state={after[1]}, country_city={after[2]}")
        print(f"  ✓ Updated\n")
    
    conn.commit()

# Update suppliers
print("\n" + "="*80)
print("UPDATING SUPPLIERS")
print("="*80 + "\n")

suppliers_updates = [
    {
        'user_id': 89,
        'user_type': ['window_door_glass_distributor', 'lumber_supplier', 'fasteners_anchoring_supplier', 
                      'dumpster_roll_off_supplier'],
        'country_city': ['Charlotte County']
    },
    {
        'user_id': 76,
        'user_type': ['window_door_glass_distributor', 'lumber_supplier', 'fasteners_anchoring_supplier', 
                      'dumpster_roll_off_supplier'],
        'country_city': ['Charlotte County']
    }
]

with engine.connect() as conn:
    for update in suppliers_updates:
        print(f"Updating supplier user_id {update['user_id']}...")
        
        # Show before
        result = conn.execute(text("""
            SELECT user_type, country_city
            FROM suppliers
            WHERE user_id = :user_id
        """), {'user_id': update['user_id']})
        before = result.fetchone()
        print(f"  BEFORE: user_type={before[0]}, country_city={before[1]}")
        
        # Update
        conn.execute(text("""
            UPDATE suppliers
            SET user_type = :user_type,
                country_city = :country_city
            WHERE user_id = :user_id
        """), update)
        
        # Show after
        result = conn.execute(text("""
            SELECT user_type, country_city
            FROM suppliers
            WHERE user_id = :user_id
        """), {'user_id': update['user_id']})
        after = result.fetchone()
        print(f"  AFTER:  user_type={after[0]}, country_city={after[1]}")
        print(f"  ✓ Updated\n")
    
    conn.commit()

print("="*80)
print("✓ ALL UPDATES COMPLETED SUCCESSFULLY")
print("="*80)

engine.dispose()
