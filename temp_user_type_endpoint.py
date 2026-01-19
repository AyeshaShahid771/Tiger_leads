

@router.get("/user-type", response_model=schemas.SupplierUserType)
def get_supplier_user_type(
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    supplier = _get_supplier(effective_user, db)
    return {
        "user_type": supplier.user_type if supplier.user_type else [],
    }


@router.patch("/user-type", response_model=schemas.SupplierUserType)
def update_supplier_user_type(
    data: schemas.SupplierUserTypeUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    """
    PATCH endpoint - APPENDS new user types to existing array.
    Removes duplicates automatically.
    """
    supplier = _get_supplier(current_user, db)

    if data.user_type is not None:
        # Get existing user types
        existing_types = supplier.user_type or []
        
        # Append new types
        combined_types = existing_types + data.user_type
        
        # Remove duplicates while preserving order
        seen = set()
        unique_types = []
        for user_type in combined_types:
            if user_type not in seen:
                seen.add(user_type)
                unique_types.append(user_type)
        
        supplier.user_type = unique_types

    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return {
        "user_type": supplier.user_type if supplier.user_type else [],
    }
