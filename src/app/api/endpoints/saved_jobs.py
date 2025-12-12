import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app import models
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

# Configure logging
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/saved-jobs", tags=["Saved Jobs"])


@router.delete("/{job_id}")
def unsave_job(
    job_id: int,
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a job from user's saved jobs list.
    
    Requires authentication token in header.
    Returns success message if job is removed or was not saved.
    """
    logger.info(f"Unsave job request from user {current_user.email} for job_id: {job_id}")
    
    # Find and delete the saved job entry
    saved_job = (
        db.query(models.user.SavedJob)
        .filter(
            models.user.SavedJob.user_id == current_user.id,
            models.user.SavedJob.job_id == job_id
        )
        .first()
    )
    
    if not saved_job:
        return {
            "message": "Job was not in saved list",
            "job_id": job_id
        }
    
    db.delete(saved_job)
    db.commit()
    
    logger.info(f"Job {job_id} unsaved by user {current_user.id}")
    
    return {
        "message": "Job removed from saved list",
        "job_id": job_id
    }


@router.get("")
def get_saved_jobs(
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all saved jobs for the authenticated user.
    
    Returns list of saved jobs with basic job details.
    """
    logger.info(f"Get saved jobs request from user {current_user.email}")
    
    # Get all saved job IDs for the user
    saved_jobs = (
        db.query(models.user.SavedJob, models.user.Job)
        .join(models.user.Job, models.user.SavedJob.job_id == models.user.Job.id)
        .filter(models.user.SavedJob.user_id == current_user.id)
        .order_by(models.user.SavedJob.saved_at.desc())
        .all()
    )
    
    # Format response
    jobs_list = []
    for saved_job, job in saved_jobs:
        jobs_list.append({
            "id": job.id,
            "permit_type": job.permit_type,
            "country_city": job.country_city,
            "state": job.state,
            "trs_score": job.trs_score,
            "saved_at": saved_job.saved_at
        })
    
    return {
        "total_saved": len(jobs_list),
        "saved_jobs": jobs_list
    }
