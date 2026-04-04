from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from src.app.utils.email_resend import send_email_resend
from src.app.api.deps import get_current_user
from src.app import models
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-requests", tags=["user-requests"])

class UserRequest(BaseModel):
    message: str

@router.post("/send-email")
async def send_user_request_email(
    request: UserRequest, 
    background_tasks: BackgroundTasks,
    current_user: models.user.User = Depends(get_current_user)
):
    """
    Send a user request message to accounts@tigerleads.ai.
    Requires authentication.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    subject = "Hey new user type is requested"
    recipient = "Accounts@tigerleads.ai"  # Match the sender email exactly
    year = datetime.utcnow().year
    
    # Get user details for the email
    user_email = current_user.email
    
    user_info_html = f"""
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; margin-top: 20px;">
        <p style="margin: 0 0 10px 0;"><strong>Requester Email:</strong> {user_email}</p>
        <p style="margin: 0 0 10px 0;"><strong>User ID:</strong> {current_user.id}</p>
        <p style="margin: 0;"><strong>User Role:</strong> {current_user.role}</p>
    </div>
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <div style="max-width: 600px; margin: 20px auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #f58220; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">New User Type Request</h2>
            </div>
            <div style="padding: 30px;">
                <p>Hello Team,</p>
                <p>A user has submitted a request for a <strong>new user type</strong> through the platform:</p>
                
                <div style="background-color: #fff4e5; border-left: 4px solid #f58220; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Description:</strong></p>
                    <p style="margin: 5px 0 0 0;">{request.message}</p>
                </div>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
                
                <div style="font-size: 14px; color: #555;">
                    <p><strong>Request Details:</strong></p>
                    {user_info_html}
                    <p><strong>Sent at:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                </div>
                
                <p>Best regards,<br><strong>Tiger Leads Bot</strong></p>
            </div>
            <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 12px; color: #777;">
                &copy; {year} Tiger Leads.ai | Automated Notification
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        # Use background tasks so the user doesn't wait for the email to send
        background_tasks.add_task(send_email_resend, recipient, subject, html_content, user_email)
        return {"message": "Request sent successfully"}
    except Exception as e:
        logger.error(f"Failed to queue user request email: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send request")
