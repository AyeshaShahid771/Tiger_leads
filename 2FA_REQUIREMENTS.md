# 2FA Dependencies

## Required Python Packages

Add these to your `requirements.txt`:

```
pyotp==2.9.0
bcrypt==4.1.2
```

## Installation

```bash
pip install pyotp bcrypt
```

## What They Do

- **pyotp**: Generates and verifies TOTP (Time-based One-Time Password) codes
- **bcrypt**: Already installed, used for hashing backup codes

## Note

`bcrypt` is likely already in your requirements since it's used for password hashing.
Only `pyotp` is the new dependency needed for 2FA.
