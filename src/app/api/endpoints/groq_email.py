import json
import logging
import os
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy.orm import Session

from src.app import models
from src.app.api.deps import get_current_user
from src.app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/groq", tags=["GROQ"])


class GroqEmailRequest(BaseModel):
    """Request model for generating personalized email templates via Groq LLM."""

    permit: Optional[str] = Field(None, max_length=100)
    cost: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    email_address: EmailStr
    phone_number: Optional[str] = Field(None, max_length=20)
    city_country: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    job_description: Optional[str] = Field(None, max_length=2000)

    @validator("phone_number")
    def validate_phone(cls, v):
        if (
            v
            and not v.replace("+", "")
            .replace("-", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .isdigit()
        ):
            raise ValueError("Invalid phone number format")
        return v


class GroqEmailResponse(BaseModel):
    """Response model containing generated email template."""

    subject: str
    body: str


class GroqService:
    """Service class for Groq API interactions using HTTP requests."""

    DEFAULT_TIMEOUT = 30

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.api_endpoint = "https://api.groq.com/openai/v1/chat/completions"

        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Groq service is not configured. GROQ_API_KEY is required.",
            )

    def _build_prompt(self, data: dict) -> str:
        """Build the prompt for email generation with placeholders and variation."""
        user_role = data.get('user_role', 'Contractor')
        permit_type = data.get('permit') or 'Construction'  # This is permit TYPE not number
        project_type = 'construction project'
        description = data.get('job_description') or 'your upcoming project'
        # Build location from city_country and state if available, otherwise fall back to address
        city_country = data.get('city_country')
        state = data.get('state')
        if city_country and state:
            location = f"{city_country}, {state}"
        elif city_country:
            location = city_country
        elif state:
            location = state
        else:
            location = data.get('address') or 'your area'
        cost = data.get('cost')
        # Sender/contact details (may be provided when enriching payload)
        sender_name = data.get('sender_name') or ''
        company_name = data.get('company_name') or ''
        phone_contact = data.get('phone_number') or data.get('phone_contact') or ''
        sender_email = data.get('email_address') or data.get('sender_email') or ''
        
        # Role-specific expertise areas
        if user_role.lower() in ['supplier', 'vendor']:
            expertise_focus = "material quality, inventory availability, bulk pricing, delivery reliability, technical specifications"
        else:  # Contractor
            expertise_focus = "project execution, code compliance, quality craftsmanship, timeline management, warranty support"
        
        prompt_template = f"""Generate a professional sales email for a {user_role} reaching out about a construction project. This email should demonstrate expertise and build trust to close the deal.

PROJECT DATA:
- Permit Type: {permit_type} (this is the TYPE of permit like "Plumbing", "Electrical", "Building", etc. - NOT a permit number)
- Project Type: {project_type}
- Description: {description}
- Location: {location}
- Budget: {cost if cost and cost != 'N/A' else 'Not specified'}
- Role: {user_role}

CRITICAL VARIATION REQUIREMENT:
Generate a UNIQUE email that differs from typical templates. Vary:
- Opening hook style (question, statement, observation, compliment)
- Sentence structure and flow
- Phrasing and word choices
- Expertise demonstration approach
- Tone (friendly, professional, consultative, direct)

Do NOT generate repetitive or formulaic emails. Each email should feel fresh and personalized.

EXACT FORMAT (NO PLACEHOLDERS):

If concrete sender contact information is available in the provided data, embed it in the email signature and DO NOT use placeholder tokens. Use these fields when present:
- Sender name: {sender_name}
- Company name: {company_name}
- Phone: {phone_contact}
- Email: {sender_email}

If sender contact information is NOT provided, produce a clear signature section using the authenticated user's email and any available payload phone number. Do NOT output placeholder tokens like {{{{Your Name}}}}.

Project Overview
• Location: {location}
• Budget: {cost if cost and cost != 'N/A' else '[Budget to be confirmed]'}
• Scope: [Restate the project scope from description in a professional way]
• Timeline: [Mention you'd like to discuss their preferred timeline]

Next Steps
I'd love to discuss this project in more detail. We can:
• Set up a 15-minute call to review your specific requirements
• Exchange information here via message
• Schedule an on-site assessment to provide an accurate quote

[Closing: 1-2 sentences. VARY between: asking what they need most, offering to answer specific questions, mentioning availability, or inviting them to share concerns. Keep it conversational and focused on THEIR needs, not your sales pitch.]

Best regards,
{sender_name or ''}
{company_name or ''}
{phone_contact or ''}
{sender_email or ''}

STYLE REQUIREMENTS:
1. Total length: 200-250 words (concise but comprehensive)
2. Use bullet points (•) ONLY for Project Overview and Next Steps sections
3. DO NOT create a "What We Bring to This Project" section with bullets
4. NO false urgency or pressure tactics
5. Be confident and consultative, positioning yourself as an expert advisor
6. Focus on SOLVING THEIR PROBLEMS and meeting their needs
7. Generate DIFFERENT wording/structure from previous emails
8. Avoid clichés like "I hope this email finds you well"
9. Be specific - avoid vague claims like "we're the best" or "quality work"
10. Use numbers and concrete examples where possible
11. Reference permit TYPE naturally (e.g., "your Plumbing permit", "the Electrical work"), NOT permit numbers
12. Keep the format clean - only 2 bulleted sections maximum

EXPERTISE DEMONSTRATION TIPS:
- For Contractors: emphasize licensing, insurance, years of experience, specialty areas, quality guarantees
- For Suppliers: emphasize inventory depth, delivery speed, technical support, pricing structure, brand partnerships
- Always include at least ONE specific capability or past success
- Show you understand the challenges of THIS type of project

SUBJECT LINE RULES:
Create a 7-12 word subject line that:
- Includes permit TYPE OR location OR project description
- Feels specific and relevant
- Can include expertise angle (e.g., "Licensed", "Certified", "Specialized")
- VARIES in structure (don't always use the same pattern)
- Examples of different patterns:
  * "{permit_type} Permit: Licensed {user_role} Ready to Start"
  * "Specialized {permit_type} Services | {location}"
  * "RE: {location} Project - Certified {user_role} Available"
  * "Your {permit_type} Expert | {location} Remodel"
  * "Licensed {permit_type} Contractor for {location}"

DO NOT include permit numbers in subject lines as we don't have that information.

OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure:
{{
  "subject": "your subject line here",
  "body": "your email body here"
}}"""

        return prompt_template

    def generate_email(self, payload_data: dict, user_role: str) -> tuple[str, str]:
        """Generate email template using Groq API via HTTP requests."""
        data = {**payload_data, "user_role": user_role}
        prompt = self._build_prompt(data)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Allow prompt to request concrete sender info instead of placeholders.
        no_placeholders = bool(data.get("no_placeholders"))
        if no_placeholders:
            system_content = (
                "You are a professional business email writer. Generate UNIQUE, VARIED content and DO NOT output placeholder tokens. "
                "If sender contact info is provided in the prompt, embed it directly in the signature. "
                "Follow the user's prompt and always return valid JSON with 'subject' and 'body' keys."
            )
        else:
            system_content = (
                "You are a professional business email writer who creates UNIQUE, VARIED content. "
                "CRITICAL: Generate different emails each time - vary your opening, structure, and phrasing. "
                "Use {{{{double curly braces}}}} for ALL placeholders like {{{{Your Name}}}}, {{{{Company Name}}}}, {{{{Phone Number}}}}, {{{{Email Address}}}}. "
                "NEVER use actual names, companies, or contact info unless the prompt provides them. "
                "Follow the format template but make each email feel fresh and personalized. "
                "Always respond with valid JSON containing 'subject' and 'body' keys."
            )

        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.7,  # Increased for more variation
            "max_tokens": 800,  # Adjusted for 200-250 word emails
            "top_p": 0.9,  # Add nucleus sampling for more diversity
            "response_format": {"type": "json_object"},
        }

        try:
            logger.info("Calling Groq API endpoint: %s with model: %s", self.api_endpoint, self.model)
            
            response = requests.post(
                self.api_endpoint,
                json=request_body,
                headers=headers,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            if not response.ok:
                error_text = response.text
                logger.error("Groq API returned status %s: %s", response.status_code, error_text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Groq API error (status {response.status_code}): {error_text[:200]}",
                )
            
            try:
                response_json = response.json()
            except json.JSONDecodeError as e:
                logger.error("Failed to decode Groq JSON response: %s", str(e))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid JSON response from Groq service",
                )
            
            logger.info("Groq API response received successfully")

            if "choices" not in response_json or not response_json["choices"]:
                logger.error("Groq response missing 'choices' field: %s", response_json)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid response structure from Groq API",
                )
            
            first_choice = response_json["choices"][0]
            message = first_choice.get("message", {})
            content = message.get("content", "")
            
            if not content:
                logger.error("Groq response missing content: %s", response_json)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Empty content in Groq API response",
                )

            try:
                email_data = json.loads(content)
                subject = email_data.get("subject", "Regarding Construction Permit {permit_num}")
                body = email_data.get("body", "")

                if not body:
                    logger.error("Groq response missing body content: %s", email_data)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to generate email body from Groq API",
                    )

                logger.info("Successfully generated email template with placeholders")
                return subject, body

            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse Groq content as JSON: %s. Content: %s",
                    str(e),
                    content[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON format in Groq response content",
                )

        except requests.exceptions.RequestException as e:
            logger.error("Groq API request failed: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to contact Groq service: {str(e)}",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected error during Groq API call: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            )


def check_user_role(current_user, allowed_roles: list[str]) -> None:
    """Check if user has required role."""
    user_role = getattr(current_user, "role", None)
    if user_role not in allowed_roles:
        logger.warning("User role '%s' not permitted to use GROQ endpoint", user_role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}",
        )


@router.post("/generate-send", response_model=GroqEmailResponse)
def generate_email_template(
    payload: GroqEmailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate a personalized email template using Groq LLM with placeholders.

    This endpoint:
    1. Verifies the user has appropriate role permissions
    2. Fetches the user's role from current_user
    3. Calls Groq API to generate personalized email content with placeholders
    4. Returns the email template with {{Placeholder}} format for user to fill in

    The generated email will contain placeholders like:
    - {{Your Name}}
    - {{Company Name}}
    - {{Phone Number}}
    - {{Email Address}}

    Each generation produces a varied email to avoid repetitive content.

    Required environment variables:
    - GROQ_API_KEY: API key for Groq service
    - GROQ_ALLOWED_ROLES: Comma-separated list of allowed roles (default: Contractor,Supplier,Admin)

    Optional environment variables:
    - GROQ_MODEL: Model to use (default: llama-3.3-70b-versatile)
    """

    allowed_roles_env = os.getenv("GROQ_ALLOWED_ROLES", "Contractor,Supplier,Admin")
    allowed_roles = [r.strip() for r in allowed_roles_env.split(",") if r.strip()]
    check_user_role(current_user, allowed_roles)

    user_role = getattr(current_user, "role", None)
    
    if not user_role:
        logger.error("User role not found for user: %s", getattr(current_user, 'email', 'unknown'))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User role not found. Please ensure your profile is complete.",
        )

    logger.info("Generating email template for user role: %s", user_role)

    payload_data = {
        "permit": payload.permit,
        "cost": payload.cost,
        "address": payload.address,
        "email_address": str(payload.email_address),
        "phone_number": payload.phone_number,
        "city_country": payload.city_country,
        "state": payload.state,
        "job_description": payload.job_description,
    }

    # If the current user is a contractor, attempt to enrich the payload with
    # contractor profile data from the `contractors` table so the LLM receives
    # concrete sender information instead of placeholders.
    try:
        if user_role and user_role.lower() == "contractor":
            contractor = (
                db.query(models.user.Contractor)
                .filter(models.user.Contractor.user_id == current_user.id)
                .first()
            )
            if contractor:
                # Prefer explicit contractor fields, fall back to payload values
                payload_data["sender_name"] = (
                    contractor.primary_contact_name or getattr(current_user, "name", None)
                )
                payload_data["company_name"] = contractor.company_name
                # Use contractor phone if available
                payload_data["phone_number"] = contractor.phone_number or payload_data.get("phone_number")
                # Use the authenticated user's email as the sender email
                payload_data["email_address"] = getattr(current_user, "email", payload_data.get("email_address"))
                # Signal to prompt builder to avoid placeholders
                payload_data["no_placeholders"] = True
    except Exception:
        # If enrichment fails, continue with original payload (do not block generation)
        logger.exception("Failed to enrich payload with contractor profile; continuing with provided data")

    groq_service = GroqService()
    subject, body = groq_service.generate_email(payload_data, user_role)

    return GroqEmailResponse(subject=subject, body=body)