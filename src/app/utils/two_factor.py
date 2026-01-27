"""
Two-Factor Authentication (2FA) Utility Functions

This module provides utility functions for:
- Generating TOTP secrets
- Creating QR codes
- Verifying TOTP codes
- Managing backup codes
"""

import secrets
from typing import List, Tuple

import bcrypt
import pyotp


def generate_2fa_secret() -> str:
    """
    Generate a new TOTP secret for 2FA.
    
    Returns:
        str: Base32 encoded secret (32 characters)
    """
    return pyotp.random_base32()


def generate_qr_code_url(email: str, secret: str, issuer: str = "TigerLeads") -> str:
    """
    Generate otpauth URL for QR code scanning.
    
    Args:
        email: User's email address
        secret: TOTP secret
        issuer: Application name (default: "TigerLeads")
    
    Returns:
        str: otpauth:// URL for QR code
    
    Example:
        otpauth://totp/TigerLeads:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=TigerLeads
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def format_secret_for_manual_entry(secret: str) -> str:
    """
    Format secret for manual entry (groups of 4 characters).
    
    Args:
        secret: Base32 encoded secret
    
    Returns:
        str: Formatted secret (e.g., "JBSW Y3DP EHPK 3PXP")
    """
    # Insert space every 4 characters
    return ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])


def verify_2fa_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """
    Verify a TOTP code.
    
    Args:
        secret: User's TOTP secret
        code: 6-digit code from authenticator app
        valid_window: Number of time windows to check (default: 1 = ±30 seconds)
    
    Returns:
        bool: True if code is valid, False otherwise
    """
    if not secret or not code:
        return False
    
    # Remove spaces and ensure code is 6 digits
    code = code.replace(' ', '').replace('-', '')
    if len(code) != 6 or not code.isdigit():
        return False
    
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=valid_window)


def generate_backup_codes(count: int = 5) -> List[str]:
    """
    Generate backup codes for 2FA recovery.
    
    Args:
        count: Number of backup codes to generate (default: 5)
    
    Returns:
        List[str]: List of backup codes in format "XXXX-XXXX-XXXX"
    """
    codes = []
    for _ in range(count):
        # Generate 3 groups of 4 hex characters
        code = '-'.join([
            secrets.token_hex(2).upper(),
            secrets.token_hex(2).upper(),
            secrets.token_hex(2).upper()
        ])
        codes.append(code)
    return codes


def hash_backup_code(code: str) -> str:
    """
    Hash a backup code for secure storage.
    
    Args:
        code: Backup code to hash
    
    Returns:
        str: Hashed backup code
    """
    # Remove dashes and convert to uppercase for consistency
    normalized_code = code.replace('-', '').upper()
    return bcrypt.hashpw(normalized_code.encode(), bcrypt.gensalt()).decode()


def verify_backup_code(code: str, hashed_codes: List[str]) -> Tuple[bool, int]:
    """
    Verify a backup code against a list of hashed codes.
    
    Args:
        code: Backup code to verify
        hashed_codes: List of hashed backup codes
    
    Returns:
        Tuple[bool, int]: (is_valid, index_of_matched_code)
                         Returns (False, -1) if no match found
    """
    if not code or not hashed_codes:
        return False, -1
    
    # Normalize the input code
    normalized_code = code.replace('-', '').replace(' ', '').upper()
    
    # Check against each hashed code
    for idx, hashed in enumerate(hashed_codes):
        try:
            if bcrypt.checkpw(normalized_code.encode(), hashed.encode()):
                return True, idx
        except Exception:
            continue
    
    return False, -1


def get_current_totp_code(secret: str) -> str:
    """
    Get the current TOTP code (useful for testing).
    
    Args:
        secret: TOTP secret
    
    Returns:
        str: Current 6-digit TOTP code
    """
    totp = pyotp.TOTP(secret)
    return totp.now()
