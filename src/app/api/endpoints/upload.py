import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.app import models
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

router = APIRouter(prefix="/upload", tags=["File Upload"])

# Configure upload directory
# Note: On Vercel, the filesystem is read-only. 
# For production, use cloud storage (S3, Vercel Blob, Cloudinary, etc.)
UPLOAD_DIR = Path("uploads/licenses")
# Only create directory if not on Vercel (Vercel sets VERCEL env var)
if not os.getenv("VERCEL"):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_image(file: UploadFile) -> bool:
    """Validate that the uploaded file is an image"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False

    # Check content type
    if not file.content_type or not file.content_type.startswith("image/"):
        return False

    return True


@router.post("/license-picture")
async def upload_license_picture(
    file: UploadFile = File(...),
    current_user: models.user.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload contractor license picture (JPG/JPEG/PNG only, max 5MB).

    Returns the file URL to use in Step 2 of contractor registration.
    """
    # Check if running on Vercel (read-only filesystem)
    if os.getenv("VERCEL"):
        raise HTTPException(
            status_code=501,
            detail="File uploads are not supported on Vercel. Please configure cloud storage (S3, Vercel Blob, etc.)",
        )
    
    # Validate file
    if not validate_image(file):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only JPG, JPEG, and PNG images are allowed.",
        )

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()  # Get position (file size)
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.1f}MB.",
        )

    # Generate unique filename
    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{current_user.id}_{uuid.uuid4().hex}{file_ext}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        # Save file
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Return the URL path (relative to server)
        file_url = f"/uploads/licenses/{unique_filename}"

        return {
            "message": "License picture uploaded successfully",
            "file_url": file_url,
            "filename": unique_filename,
            "size_bytes": file_size,
        }

    except Exception as e:
        # Clean up file if it was created
        if file_path.exists():
            file_path.unlink()

        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.delete("/license-picture/{filename}")
async def delete_license_picture(
    filename: str,
    current_user: models.user.User = Depends(get_current_user),
):
    """
    Delete a previously uploaded license picture.

    Only the owner can delete their own files.
    """
    # Check if running on Vercel (read-only filesystem)
    if os.getenv("VERCEL"):
        raise HTTPException(
            status_code=501,
            detail="File operations are not supported on Vercel. Please configure cloud storage (S3, Vercel Blob, etc.)",
        )
    
    # Verify filename belongs to current user (starts with user_id)
    if not filename.startswith(f"{current_user.id}_"):
        raise HTTPException(
            status_code=403, detail="You can only delete your own files"
        )

    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.unlink()
        return {"message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
