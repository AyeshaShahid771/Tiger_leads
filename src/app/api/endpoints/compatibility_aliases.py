from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from src.app import models, schemas
from src.app.api.deps import (
    get_current_user,
    get_db,
    get_effective_user,
    require_admin_or_ops,
    require_admin_token,
    require_main_or_editor,
)
from src.app.api.endpoints import admin_dashboard, contractor, jobs, profile, supplier

router = APIRouter(tags=["Compatibility Aliases"])


@router.patch(
    "/contractors/location-info", response_model=schemas.ContractorLocationInfo
)
def update_contractor_location_info_alias(
    data: schemas.ContractorLocationInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    return contractor.update_contractor_location_info(
        data=data,
        current_user=current_user,
        effective_user=effective_user,
        db=db,
    )


@router.patch("/suppliers/location-info", response_model=schemas.SupplierLocationInfo)
def update_supplier_location_info_alias(
    data: schemas.SupplierLocationInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    return supplier.update_location_info(
        data=data,
        current_user=current_user,
        effective_user=effective_user,
        db=db,
    )


@router.patch("/contractors/trade-info", response_model=schemas.ContractorTradeInfo)
def update_contractor_trade_info_alias(
    data: schemas.ContractorTradeInfoUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    return contractor.update_contractor_trade_info(
        data=data,
        current_user=current_user,
        db=db,
    )


@router.patch("/suppliers/user-type", response_model=schemas.SupplierUserType)
def update_supplier_user_type_alias(
    data: schemas.SupplierUserTypeUpdate,
    current_user: models.user.User = Depends(require_main_or_editor),
    db: Session = Depends(get_db),
):
    return supplier.update_supplier_user_type(
        data=data,
        current_user=current_user,
        db=db,
    )


@router.get("/profile/info")
def get_profile_info_alias(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return profile.get_profile_info(current_user=current_user, db=db)


@router.get(
    "/admin/dashboard/pending-jurisdictions",
    dependencies=[Depends(require_admin_token)],
)
def list_pending_jurisdictions_alias(
    user_type: Optional[str] = None,
    status: str = "pending",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
):
    return admin_dashboard.list_pending_jurisdictions(
        user_type=user_type,
        status=status,
        page=page,
        per_page=per_page,
        db=db,
    )


@router.patch(
    "/admin/dashboard/pending-jurisdictions/{pending_id}/approve",
    dependencies=[Depends(require_admin_or_ops)],
)
def approve_pending_jurisdiction_alias(
    pending_id: int,
    db: Session = Depends(get_db),
    admin: models.user.AdminUser = Depends(require_admin_or_ops),
):
    return admin_dashboard.approve_pending_jurisdiction(
        pending_id=pending_id,
        db=db,
        admin=admin,
    )


@router.patch(
    "/admin/dashboard/pending-jurisdictions/{pending_id}/reject",
    dependencies=[Depends(require_admin_or_ops)],
)
def reject_pending_jurisdiction_alias(
    pending_id: int,
    body: admin_dashboard.GenericRejectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: models.user.AdminUser = Depends(require_admin_or_ops),
):
    return admin_dashboard.reject_pending_jurisdiction(
        pending_id=pending_id,
        body=body,
        background_tasks=background_tasks,
        db=db,
        admin=admin,
    )


@router.get(
    "/admin/dashboard/pending-user-types",
    dependencies=[Depends(require_admin_token)],
)
def list_pending_user_types_alias(
    user_role: Optional[str] = None,
    status: str = "pending",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
):
    return admin_dashboard.list_pending_user_types(
        user_role=user_role,
        status=status,
        page=page,
        per_page=per_page,
        db=db,
    )


@router.patch(
    "/admin/pending-user-types/{pending_id}/approve",
    dependencies=[Depends(require_admin_or_ops)],
)
def approve_pending_user_type_alias(
    pending_id: int,
    db: Session = Depends(get_db),
    admin: models.user.AdminUser = Depends(require_admin_or_ops),
):
    return admin_dashboard.approve_pending_user_type(
        pending_id=pending_id,
        db=db,
        admin=admin,
    )


@router.patch(
    "/admin/pending-user-types/{pending_id}/reject",
    dependencies=[Depends(require_admin_or_ops)],
)
def reject_pending_user_type_alias(
    pending_id: int,
    body: admin_dashboard.GenericRejectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: models.user.AdminUser = Depends(require_admin_or_ops),
):
    return admin_dashboard.reject_pending_user_type(
        pending_id=pending_id,
        body=body,
        background_tasks=background_tasks,
        db=db,
        admin=admin,
    )


@router.patch(
    "/admin/ingested-jobs/{job_id}/decline",
    dependencies=[Depends(require_admin_or_ops)],
)
def decline_ingested_job_alias(
    job_id: int,
    body: admin_dashboard.DeclineJobRequest,
    db: Session = Depends(get_db),
    admin: models.user.AdminUser = Depends(require_admin_or_ops),
):
    return admin_dashboard.decline_ingested_job(
        job_id=job_id,
        body=body,
        db=db,
        admin=admin,
    )


@router.get("/job/{job_id}")
def get_job_by_id_alias(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    return jobs.get_job_by_id(
        job_id=job_id,
        current_user=current_user,
        effective_user=effective_user,
        db=db,
    )


@router.patch("/job/{job_id}/repost")
def repost_declined_job_alias(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    effective_user: models.user.User = Depends(get_effective_user),
    db: Session = Depends(get_db),
):
    return jobs.repost_declined_job(
        job_id=job_id,
        current_user=current_user,
        effective_user=effective_user,
        db=db,
    )
