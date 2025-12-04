"""
Helper functions for team/multi-seat functionality.
"""

from src.app.models.user import User


def get_effective_user_id(current_user: User) -> int:
    """
    Get the effective user ID for data access.

    If the user is a sub-user (has parent_user_id), return the parent's ID.
    Otherwise, return the user's own ID.

    This ensures all sub-users share the same data pool as the main account owner.

    Args:
        current_user: The currently authenticated user

    Returns:
        The user ID to use for data filtering (either own ID or parent's ID)
    """
    if current_user.parent_user_id:
        return current_user.parent_user_id
    return current_user.id


def is_main_account(current_user: User) -> bool:
    """
    Check if the current user is a main account (not a sub-user).

    Args:
        current_user: The currently authenticated user

    Returns:
        True if this is a main account, False if it's a sub-user
    """
    return current_user.parent_user_id is None


def get_main_user_id(current_user: User) -> int:
    """
    Get the main account user ID.

    Alias for get_effective_user_id for clarity in some contexts.

    Args:
        current_user: The currently authenticated user

    Returns:
        The main account user ID
    """
    return get_effective_user_id(current_user)
