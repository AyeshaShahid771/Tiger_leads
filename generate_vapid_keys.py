r"""
Generate VAPID keys for web push notifications.
"""

from py_vapid import Vapid01 as Vapid
from cryptography.hazmat.primitives import serialization

print("Generating VAPID keys for web push notifications...\n")

# Generate keys
vapid_key = Vapid()
vapid_key.generate_keys()

# Get private key as PEM
private_pem = vapid_key.private_pem().decode('utf-8').strip()

# Get public key in uncompressed format (raw bytes)
public_key_bytes = vapid_key.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)
public_key_hex = public_key_bytes.hex()

print("✅ VAPID keys generated successfully!\n")
print("=" * 80)
print("Add these to your .env file:")
print("=" * 80)
print()
print(f"VAPID_PRIVATE_KEY={private_pem}")
print(f"VAPID_PUBLIC_KEY={public_key_hex}")
print("VAPID_CLAIM_EMAIL=mailto:admin@tigerleads.ai")
print()
print("=" * 80)
print()
print("⚠️  IMPORTANT:")
print("  - Keep the private key SECRET and never commit it to version control")
print("  - The public key will be shared with the frontend")
print("  - Update VAPID_CLAIM_EMAIL with your actual email")
print()
