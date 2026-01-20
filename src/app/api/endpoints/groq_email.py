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
        """Build the prompt for email generation with trust-building and deal-closing focus."""
        user_role = data.get('user_role', 'Contractor')
        permit_type = data.get('permit') or 'Construction'
        description = data.get('job_description') or 'your upcoming project'
        
        # Build location
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
        
        # Sender details
        sender_name = data.get('sender_name') or ''
        company_name = data.get('company_name') or ''
        phone_contact = data.get('phone_number') or data.get('phone_contact') or ''
        sender_email = data.get('email_address') or data.get('sender_email') or ''
        
        prompt_template = f"""You are writing a sales email for a {user_role} to win a construction project. Your goal is to BUILD TRUST and CLOSE THE DEAL.

PROJECT DETAILS:
- Permit Type: {permit_type} (e.g., "Plumbing", "Electrical", "Building" - NOT a permit number)
- Description: {description}
- Location: {location}
- Role: {user_role}

SENDER INFORMATION:
- Name: {sender_name or '{{{{Your Name}}}}'}
- Company: {company_name or '{{{{Company Name}}}}'}
- Phone: {phone_contact or '{{{{Phone Number}}}}'}
- Email: {sender_email or '{{{{Email Address}}}}'}

═══════════════════════════════════════════════════════════════
CRITICAL: TRUST-BUILDING & DEAL-CLOSING STRATEGY
═══════════════════════════════════════════════════════════════

🎯 PRIMARY GOAL: Make the recipient feel CONFIDENT and SAFE choosing you

TRUST-BUILDING ELEMENTS (Include at least 3):
1. **Professional Credentials**: Licensed, insured, certified (NO fake license numbers)
2. **Local Expertise**: Experience in {location} area
3. **Social Proof**: Client satisfaction, positive track record
4. **Risk Reduction**: Warranties, insurance coverage, guarantees
5. **Transparency**: Clear process, timeline expectations
6. **Availability**: Ready to start, responsive communication
7. **Problem Awareness**: Understand their specific project needs

CRITICAL - DO NOT FABRICATE:
❌ NO fake license numbers (e.g., "CA C-10 #123456")
❌ NO specific years of experience (e.g., "18 years")
❌ NO specific project counts (e.g., "47 projects completed")
❌ NO fake success percentages (e.g., "98% pass rate")
❌ NO permit numbers in subject lines

INSTEAD USE:
✓ "Licensed and insured professional"
✓ "Experienced in {permit_type} projects"
✓ "Proven track record in {location}"
✓ "High client satisfaction"
✓ "Successful project completion history"

DEAL-CLOSING PSYCHOLOGY:
✓ Create urgency WITHOUT pressure (e.g., "I have availability this week")
✓ Make it EASY to say yes (simple next step, low commitment)
✓ Address unspoken concerns (cost, quality, timeline, reliability)
✓ Position as advisor, not salesperson
✓ Demonstrate you've done your homework about THEIR project

═══════════════════════════════════════════════════════════════
EMAIL STRUCTURE (200-250 words)
═══════════════════════════════════════════════════════════════

**OPENING (2-3 sentences):**
Choose ONE of these proven patterns:

Pattern A - EXPERTISE HOOK:
"I specialize in {permit_type} projects in {location} and noticed your permit. As an experienced professional in your area, I understand exactly what this work requires."

Pattern B - VALUE HOOK:
"Most {permit_type} projects in {location} face [specific challenge]. I have a proven approach that saves time and ensures code compliance."

Pattern C - CREDIBILITY HOOK:
"As a licensed {user_role}, I focus on {permit_type} projects in {location}. Your project caught my attention because [specific reason related to description]."

Pattern D - DIRECT HOOK:
"I have immediate availability for your {permit_type} project in {location}. Here's why I'm confident I can deliver excellent results..."

**PROJECT UNDERSTANDING (3-4 sentences):**
Show you've analyzed their project:
- Restate the scope professionally based on description
- Mention specific requirements for THIS permit type
- Show location knowledge (local codes, common challenges)
- Demonstrate understanding of project timeline and complexity

**CREDENTIALS & PROOF (4-5 sentences):**
Build credibility with SPECIFIC details:

For Contractors (NO fake numbers):
- "Licensed and fully insured with comprehensive liability and workers comp coverage"
- "Experienced in {permit_type} projects throughout {location}"
- "Strong track record of successful project completions"
- "Specialize in [specific type based on permit_type]"
- "All work backed by warranty and guarantee"
- "Proven history of passing inspections and meeting code requirements"

For Suppliers (NO fake numbers):
- "Extensive inventory of {permit_type} materials and equipment"
- "Fast delivery service throughout {location}"
- "Knowledgeable team for technical support and guidance"
- "Competitive pricing with contractor discounts available"
- "Authorized dealer for major brands"
- "Reliable service with flexible return policies"

**NEXT STEPS (2-3 sentences):**
Make it EASY and LOW-PRESSURE:
- Offer 2-3 specific options
- Include timeframes
- Make it conversational

ALWAYS include this exact format before closing:

"If you're open to it, we can:
• Schedule a quick call
• Continue the discussion here via message
• Arrange a site visit (if required)"

Examples of full next steps section:
"I'd love to provide a detailed quote. If you're open to it, we can:
• Schedule a quick call
• Continue the discussion here via message
• Arrange a site visit (if required)"

"Would you be interested in discussing this further? If you're open to it, we can:
• Schedule a quick call
• Continue the discussion here via message
• Arrange a site visit (if required)"

**CLOSING (1 sentence):**
ALWAYS include "Looking forward to" - warm, professional, focused on THEIR needs:
- "Looking forward to helping you complete this project on time and on budget."
- "Looking forward to discussing your specific requirements and answering any questions."
- "Looking forward to the opportunity to work with you on this project."

**SIGNATURE:**
{sender_name or '{{{{Your Name}}}}'}
{company_name or '{{{{Company Name}}}}'}
{phone_contact or '{{{{Phone Number}}}}'}
{sender_email or '{{{{Email Address}}}}'}

═══════════════════════════════════════════════════════════════
SUBJECT LINE (7-12 words)
═══════════════════════════════════════════════════════════════

Create a subject line that builds CREDIBILITY and RELEVANCE:

PROVEN PATTERNS (NO permit numbers, NO fake credentials):
1. "Licensed {permit_type} Specialist | {location} Available"
2. "Experienced {user_role} for Your {location} {permit_type} Project"
3. "Licensed & Insured {user_role} | {location} {permit_type}"
4. "Professional {permit_type} Services in {location}"
5. "{permit_type} Specialist Available This Week | {location}"
6. "Certified {user_role} | {location} {permit_type} Projects"
7. "Your {location} {permit_type} Project | Licensed Professional"
8. "{permit_type} Expert Serving {location} | Available Now"

Include at least ONE trust element: Licensed, Certified, Insured, Experienced, Specialist, Expert, Professional

═══════════════════════════════════════════════════════════════
QUALITY REQUIREMENTS
═══════════════════════════════════════════════════════════════

MUST INCLUDE:
✓ At least 3 trust-building elements (credentials, insurance, experience)
✓ At least 1 risk-reduction element (insurance, warranty, guarantee)
✓ Location mentioned 2-3 times
✓ Clear, specific next step with options
✓ "Looking forward to" in closing
✓ Professional but warm tone

MUST AVOID:
✗ Fake license numbers or credentials
✗ Specific years of experience you don't have
✗ Specific project counts you don't have
✗ Fake success percentages or metrics
✗ Permit numbers in subject line
✗ Generic claims ("best quality", "lowest prices")
✗ Pressure tactics ("limited time offer", "act now")
✗ Clichés ("I hope this email finds you well")

VARIATION:
Generate DIFFERENT content each time:
- Vary opening hook pattern
- Change credential emphasis
- Alternate next step options
- Use different specific numbers
- Vary sentence structure

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

Return ONLY valid JSON:
{{
  "subject": "your subject line here",
  "body": "your email body here"
}}

Use {{{{double curly braces}}}} for placeholders ONLY if sender information is not provided in the data."""

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
                "You are an expert sales email writer focused on BUILDING TRUST and CLOSING DEALS. "
                "Your emails must make recipients feel CONFIDENT and SAFE choosing the sender. "
                "Generate UNIQUE, VARIED content with specific credentials, numbers, and proof points. "
                "If sender contact info is provided, embed it directly in the signature. "
                "Always return valid JSON with 'subject' and 'body' keys."
            )
        else:
            system_content = (
                "You are an expert sales email writer focused on BUILDING TRUST and CLOSING DEALS. "
                "Your emails must make recipients feel CONFIDENT and SAFE choosing the sender. "
                "CRITICAL: Generate UNIQUE emails each time - vary opening hooks, credentials emphasis, and structure. "
                "Include specific numbers (years, projects, success rates) and risk-reduction elements (insurance, warranties). "
                "Use {{{{double curly braces}}}} for placeholders like {{{{Your Name}}}}, {{{{Company Name}}}}. "
                "NEVER use actual names unless provided in the prompt. "
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
            "temperature": 0.8,  # Higher for more variation and creativity
            "max_tokens": 900,  # Increased for detailed, trust-building content
            "top_p": 0.9,  # Nucleus sampling for diversity
            "frequency_penalty": 0.3,  # Reduce repetitive phrases
            "presence_penalty": 0.2,  # Encourage new topics and approaches
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