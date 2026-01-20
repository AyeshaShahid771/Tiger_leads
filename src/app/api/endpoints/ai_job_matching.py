"""
AI-powered job matching endpoints using GROQ API.
Suggests which contractors and suppliers should see a job based on project details.
"""

import json
import logging
import os
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.app.api.deps import get_current_user
from src.app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-matching", tags=["AI Job Matching"])


# Request Models
class JobMatchingRequest(BaseModel):
    """Request model for AI job matching."""
    permit_number: Optional[str] = Field(None, max_length=100)
    permit_status: Optional[str] = Field(None, max_length=50)
    project_type: Optional[str] = Field(None, max_length=200)
    property_type: Optional[str] = Field(None, max_length=100)
    job_address: Optional[str] = Field(None, max_length=500)
    cost: Optional[str] = Field(None, max_length=50)
    job_description: Optional[str] = Field(None, max_length=2000)
    contractor_name: Optional[str] = Field(None, max_length=200)
    company_name: Optional[str] = Field(None, max_length=200)
    email_address: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    state: Optional[str] = Field(None, max_length=100)
    county_city: Optional[str] = Field(None, max_length=100)


# Response Models
class UserTypeMatch(BaseModel):
    """Individual user type match with offset days."""
    user_type: str
    offset_days: int


class ContractorMatchingResponse(BaseModel):
    """Response model for contractor matching."""
    matches: List[UserTypeMatch]


class SupplierMatchingResponse(BaseModel):
    """Response model for supplier matching."""
    matches: List[UserTypeMatch]


class GroqMatchingService:
    """Service class for GROQ API job matching."""

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

    def _build_contractor_prompt(self, data: dict) -> str:
        """Build prompt for contractor matching."""
        
        # Extract data
        project_type = data.get('project_type') or 'construction project'
        property_type = data.get('property_type') or 'property'
        description = data.get('job_description') or 'construction work'
        cost = data.get('cost') or 'not specified'
        permit_status = data.get('permit_status') or 'unknown'
        
        prompt = f"""You are an expert construction project analyst. Analyze this job and determine ALL contractor types needed to complete this project, with REALISTIC timing based on actual construction schedules (projects take MONTHS, not days).

JOB DETAILS:
- Project Type: {project_type}
- Property Type: {property_type}
- Description: {description}
- Budget: {cost}
- Permit Status: {permit_status}

AVAILABLE CONTRACTOR TYPES:
Acoustical Contractor, Arborist, Backflow Tester/Installer, Balancing / TAB contractor, Boiler/Pressure Vessel, Cabinet Installer, Commercial kitchen hood installer fabricator, Concrete Contractor, Controls / BAS integrator, Controls / BMS integrator, Conveyance/Lift/Hoist Installer, Countertop Fabricator, Directional boring / jack & bore contractor, Door hardware / access control contractor, Dry chemical / foam / special hazard contractor, Drywall / Sheetrock Contractor, Electrical Contractor, Erosion Control Contractor, Escalator/Elevator, Event/Assembly Installer, Excavation / Trenching Contractor, Fence/Railing Contractor, Fire Alarm Contractor, Fire pump testing & service company, Fire Sprinkler Contractor, Flooring / Carpet Installers, Flooring/Epoxy Installer, Foundation / Pier Installer, Framing Contractor, Fuel Gas Contractor, Garage Door Contractor, Gas Contractor, Gas Equipment Appliance Installer, Gate Operator, General Contractor, Graywater/Rainwater System Installer, Grease duct fabricator / installer, Gunite/shotcrete subcontractor, Gutter Installer, Hood (Mechanical) Contractor, Hood Suppression Contractor, Hydronic Piping Contractor, Insulation Contractor, Irrigation Contractor, Kitchen equipment installer, Land Clearing Contractor, Landscape Contractor, Low Voltage Contractor, Masonry Contractor, Mechanical / HVAC Contractor, Medical equipment installer, Medical Gas Contractor, Painting Contractor, Paver / Flatwork Contractors, Pipe Insulation Contractor, Plumbing Contractor, Pool service & maintenance company, Racking/shelving installer, Refrigeration, Retaining Wall Contractor, Roofing Contractor, Scaffolding Contractor, Septic/On Site Waste Water Installer, Shoring/Underpinning Contractor, Siding / Trim Contractor, Site Work/Grading Contractor, Spray Booth Installer, Structural steel / equipment support fabricator, Stucco Contractor, Test & Balance / commissioning agent, Tile Contractor, Traffic Control Company, Trim Carpenter, underground utility contractor, Vacuum pump & medical air system installer, Walk-in cooler/freezer builder, Water treatment contractor, Water Well Driller/Pump Installer, Waterproofing / Air Barrier Contractor, Welding Contractor, Window / Door Contractor

REALISTIC OFFSET DAYS LOGIC (Construction takes MONTHS):
- Day 0: Immediate notification (General Contractor, project manager)
- Week 1 (Days 1-7): Pre-construction (permits, site prep, surveys)
- Week 2-3 (Days 8-21): Site work (excavation, grading, utilities, erosion control)
- Month 1 (Days 22-30): Foundation work (concrete, waterproofing, structural)
- Month 2 (Days 31-60): Framing and structural (framing, steel, masonry, roofing)
- Month 3 (Days 61-90): Rough-in trades (plumbing, electrical, HVAC, fire protection)
- Month 4 (Days 91-120): Insulation, drywall, interior framing
- Month 5 (Days 121-150): Finish trades (painting, flooring, tile, trim, cabinets)
- Month 6 (Days 151-180): Final fixtures, appliances, specialty systems
- Month 7+ (Days 181+): Landscaping, final inspections, punch list, commissioning

CRITICAL INSTRUCTIONS:
1. Include ALL contractor types needed to COMPLETE this project from start to finish
2. Do NOT limit to 3-8 trades - include EVERY trade required
3. Use REALISTIC timelines (months, not days)
4. Consider the full construction sequence
5. Include specialty trades specific to this project type
6. Use EXACT display names from the list above
7. Order by offset_days (earliest first)

EXAMPLES OF COMPREHENSIVE MATCHING:

New Home Construction (15-25 trades):
- General Contractor (day 0)
- Site Work/Grading Contractor (day 7)
- Excavation / Trenching Contractor (day 14)
- Concrete Contractor (day 30)
- Foundation / Pier Installer (day 30)
- Waterproofing / Air Barrier Contractor (day 45)
- Framing Contractor (day 60)
- Roofing Contractor (day 75)
- Window / Door Contractor (day 80)
- Plumbing Contractor (day 90)
- Electrical Contractor (day 90)
- Mechanical / HVAC Contractor (day 90)
- Insulation Contractor (day 105)
- Drywall / Sheetrock Contractor (day 120)
- Painting Contractor (day 135)
- Flooring / Carpet Installers (day 145)
- Tile Contractor (day 145)
- Cabinet Installer (day 150)
- Countertop Fabricator (day 155)
- Trim Carpenter (day 155)
- Garage Door Contractor (day 160)
- Landscape Contractor (day 170)
- Irrigation Contractor (day 175)

Commercial Building (20-30 trades):
Include all structural, MEP, fire protection, accessibility, specialty systems, finishes, and site work trades.

CRITICAL: Return ONLY valid JSON in this exact format:
{{
  "matches": [
    {{"user_type": "General Contractor", "offset_days": 0}},
    {{"user_type": "Site Work/Grading Contractor", "offset_days": 7}},
    {{"user_type": "Concrete Contractor", "offset_days": 30}}
  ]
}}

Analyze the job thoroughly and return ALL necessary contractors with realistic timing."""

        return prompt

    def _build_supplier_prompt(self, data: dict) -> str:
        """Build prompt for supplier matching."""
        
        # Extract data
        project_type = data.get('project_type') or 'construction project'
        property_type = data.get('property_type') or 'property'
        description = data.get('job_description') or 'construction work'
        cost = data.get('cost') or 'not specified'
        
        prompt = f"""You are an expert construction supply chain analyst. Analyze this job and determine ALL supplier types needed to complete this project, with REALISTIC timing based on actual material procurement schedules (projects take MONTHS).

JOB DETAILS:
- Project Type: {project_type}
- Property Type: {property_type}
- Description: {description}
- Budget: {cost}

AVAILABLE SUPPLIER TYPES:
Access control Door hardware supplier, Acoustical Supplier, Annunciator & graphic panel supplier, Appliance Suppliers, Awning/canopy materials suppliers, Backflow preventer supplier, Battery + exit sign component suppliers, Boiler / furnace equipment supplier, Bulk gas supplier (O₂, N₂O, N₂, CO₂, etc.), Cabinet Supplier, Chiller manufacturer / distributor, Closet System Vendor, CMU block Supplier, Composite/PVC decking distributor, Concrete Supplier, Condensate pump & neutralizer supplier, Conduit & raceway supplier, Construction Trailer, Controls hardware supplier, Cooling tower / fluid cooler supplier, Countertop Suppliers, Crane Service, Drainage suppliers, Drywall / Sheetrock Supplier, Dumpster / Roll Off Supplier, Electrical gear supplier, Electrical / Low Voltage Distributor, Electrical Supply House, Equipment Rental, Erosion control supplier, Erosion materials, ESS / Battery System Supplier, Evaporator / coil supplier, Exhaust fan supplier, Explosives Storage Operator, Extrusion / framing system suppliers, Fasteners / anchoring suppliers, Fence material suppliers/distributors, Finish carpentry suppliers (Interior Doors & Trim), Fire alarm cable supplier, Fire alarm equipment supplier, Fire alarm panel manufacturer / distributor, Fire Protection Material Supplier, Fire pump controller suppliers, Fire pump manufacturers / authorized distributors, Fire sprinkler material house, Flooring Distributor (Tile, LVP, Wood & Carpet), Fuel shutoff valve supplier, Garage Door Supplier, Gas Appliance Supplier, Gas Pipe & Fittings Supplier, Gas Regulator & Meter Set Supplier, Gate/door operator & barrier supplier, Glass fabricator, Grease duct & fittings supplier, Gutter Supplier, Headwall & boom manufacturer / dealer, Hood suppression equipment distributor, HVAC Distributor, Hydronic components supplier, Instrument air system supplier, Instrumentation & controls supplier, Insulation Suppliers, Interface module supplier, Inverter + BOS Supplier, Irrigation Suppliers, kitchen hood manufacturer / dealer, Landscape Suppliers, Leak Detection & Testing Equipment Supplier, Lighting distributors / commercial, Lighting/LED module suppliers, Low-voltage cable & device supplier, Lumber Supplier, Makeup air unit (MAU) supplier, Manifold & cylinder system supplier, Masonry Supplier, Material Hoist/Manlift, Medical air compressor system supplier, medical Gas and equipment Suppliers, Medical gas copper tube supplier, Medical gas fittings & brazing materials supplier, Medical gas outlet / inlet terminal supplier, Medical vacuum system supplier, Monitoring company / central station integrator, NFPA 99 medical gas verification agency / verifier, Notification appliance supplier, Paint / Coatings Suppliers, Paver / Flatwork Suppliers, Pipe/fittings suppliers, Pipe insulation supplier, Plumbing Supplier, Pool equipment supplier / distributor, Portable Sanitation Rental, Pressure regulator & line regulator supplier, Rack & condensing unit supplier, Racking and Mounting Supplier (solar), Railing system suppliers, Rebar/Fabrication Shop, Rebar & structural hardware, Refrigerant & specialty gas supplier, Refrigeration valves & fittings supplier., Riser assembly supplier, Roofing Materials Distributor, Safety compliance suppliers, Safety/fall protection vendor, Scaffolding Vendor, Sealant /adhesive suppliers, Security system supplier, Seismic bracing & hanger hardware supplier, Seismic Gas Shutoff Valve Supplier, shoring/trench safety rental suppliers, Shotcrete/gunite materials supplier, Shower Glass Supplier, Siding / Trim Supplier, Sign component suppliers, Smart Gas Control Supplier, Sod / grass Suppliers, Solar Module Supplier, Solar/PV Equipment Supplier, Sprinkler head manufacturer / distributor, Steel supplier / structural metals distributor, Stone / Aggregate Supplier, Stone/Quartz Slab Supplier, Storefront/curtain wall system manufacturers / distributors, structural connector & hardware Suppliers, Temporary Fencing Supplier, Thermostat & controls supplier, Third-party verifier / certifier, Tile Suppliers, Tool Supplier, Tower Crane Erector, Tracer Wire & Marking Materials Supplier, Tree Removal Service, Truss Company, Underground piping & fittings supplier, Valves & specialty fittings supplier, Vapor barrier & under-slab suppliers, Venting system supplier, Vinyl fence suppliers, Waste/Roll-Off Service, Waterproofing / Air Barrier Suppliers, Window / Door / Glass Distributors, Zone valve box supplier

REALISTIC OFFSET DAYS LOGIC (Material Procurement takes TIME):
- Day 0: Immediate (site setup, safety, waste management, equipment rental)
- Week 1 (Days 1-7): Early procurement (temporary facilities, site materials)
- Week 2-3 (Days 8-21): Site work materials (erosion control, drainage, excavation supplies)
- Month 1 (Days 22-30): Foundation materials (concrete, rebar, waterproofing, forms)
- Month 1.5 (Days 31-45): Long lead structural items (steel, trusses, engineered lumber)
- Month 2 (Days 46-60): Framing materials (lumber, fasteners, sheathing, windows/doors)
- Month 2.5 (Days 61-75): Roofing, siding, exterior finishes
- Month 3 (Days 76-90): MEP rough-in materials (plumbing, electrical, HVAC supplies)
- Month 3.5 (Days 91-105): Fire protection, low voltage, specialty systems
- Month 4 (Days 106-120): Insulation, drywall, interior framing materials
- Month 5 (Days 121-150): Finish materials (paint, flooring, tile, trim, doors)
- Month 5.5 (Days 151-165): Cabinets, countertops, fixtures, appliances
- Month 6+ (Days 166+): Landscaping materials, final finishes, specialty items

CRITICAL INSTRUCTIONS:
1. Include ALL supplier types needed to COMPLETE this project from start to finish
2. Do NOT limit to 3-8 suppliers - include EVERY supplier required
3. Use REALISTIC timelines considering material lead times (some items take weeks to order)
4. Consider the full material procurement sequence
5. Include specialty suppliers specific to this project type
6. Account for long lead-time items (equipment, custom fabrication, specialty systems)
7. Use EXACT display names from the list above
8. Order by offset_days (earliest first)

EXAMPLES OF COMPREHENSIVE MATCHING:

New Home Construction (20-30 suppliers):
- Dumpster / Roll Off Supplier (day 0)
- Equipment Rental (day 0)
- Portable Sanitation Rental (day 0)
- Temporary Fencing Supplier (day 3)
- Erosion control supplier (day 7)
- Concrete Supplier (day 25)
- Rebar & structural hardware (day 25)
- Lumber Supplier (day 50)
- Truss Company (day 50)
- Fasteners / anchoring suppliers (day 55)
- Window / Door / Glass Distributors (day 60)
- Roofing Materials Distributor (day 70)
- Siding / Trim Supplier (day 75)
- Plumbing Supplier (day 85)
- Electrical Supply House (day 85)
- HVAC Distributor (day 85)
- Insulation Suppliers (day 100)
- Drywall / Sheetrock Supplier (day 115)
- Paint / Coatings Suppliers (day 130)
- Flooring Distributor (Tile, LVP, Wood & Carpet) (day 140)
- Tile Suppliers (day 140)
- Cabinet Supplier (day 145)
- Countertop Suppliers (day 150)
- Finish carpentry suppliers (Interior Doors & Trim) (day 150)
- Appliance Suppliers (day 155)
- Garage Door Supplier (day 155)
- Landscape Suppliers (day 165)
- Irrigation Suppliers (day 170)
- Sod / grass Suppliers (day 175)

Commercial Building (25-40 suppliers):
Include all structural materials, MEP supplies, fire protection equipment, specialty systems, finishes, and site materials.

CRITICAL: Return ONLY valid JSON in this exact format:
{{
  "matches": [
    {{"user_type": "Dumpster / Roll Off Supplier", "offset_days": 0}},
    {{"user_type": "Concrete Supplier", "offset_days": 25}},
    {{"user_type": "Electrical Supply House", "offset_days": 85}}
  ]
}}

Analyze the job thoroughly and return ALL necessary suppliers with realistic procurement timing."""

        return prompt

    def match_contractors(self, job_data: dict) -> List[dict]:
        """Use GROQ AI to match contractors to a job."""
        prompt = self._build_contractor_prompt(job_data)
        return self._call_groq_api(prompt)

    def match_suppliers(self, job_data: dict) -> List[dict]:
        """Use GROQ AI to match suppliers to a job."""
        prompt = self._build_supplier_prompt(job_data)
        return self._call_groq_api(prompt)

    def _call_groq_api(self, prompt: str) -> List[dict]:
        """Call GROQ API and parse response."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert construction project analyst. Analyze jobs and match them with appropriate contractor or supplier types based on project requirements and construction sequencing. Always return valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.3,  # Lower for more consistent, logical matching
            "max_tokens": 1000,
            "response_format": {"type": "json_object"},
        }

        try:
            logger.info("Calling Groq API for job matching")
            
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
                    detail=f"Groq API error (status {response.status_code})",
                )
            
            response_json = response.json()
            
            if "choices" not in response_json or not response_json["choices"]:
                logger.error("Groq response missing 'choices' field")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid response structure from Groq API",
                )
            
            content = response_json["choices"][0]["message"]["content"]
            
            # Parse the JSON response
            result = json.loads(content)
            matches = result.get("matches", [])
            
            logger.info("Successfully matched %d user types", len(matches))
            return matches

        except requests.exceptions.RequestException as e:
            logger.error("Groq API request failed: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to contact Groq service: {str(e)}",
            )
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Groq response: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid JSON response from AI service",
            )
        except Exception as e:
            logger.error("Unexpected error during job matching: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
            )


@router.post("/suggest-contractors", response_model=ContractorMatchingResponse)
def suggest_contractors(
    payload: JobMatchingRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suggest which contractor types should see this job and when.
    
    Uses AI to analyze the job details and recommend:
    - Which contractor types are relevant
    - When they should be notified (offset_days) based on construction sequencing
    
    Returns a list of contractor types with offset days for timing.
    """
    
    logger.info("Suggesting contractors for job")
    
    job_data = {
        "permit_number": payload.permit_number,
        "permit_status": payload.permit_status,
        "project_type": payload.project_type,
        "property_type": payload.property_type,
        "job_address": payload.job_address,
        "cost": payload.cost,
        "job_description": payload.job_description,
        "contractor_name": payload.contractor_name,
        "company_name": payload.company_name,
        "state": payload.state,
        "county_city": payload.county_city,
    }
    
    service = GroqMatchingService()
    matches = service.match_contractors(job_data)
    
    return ContractorMatchingResponse(matches=matches)


@router.post("/suggest-suppliers", response_model=SupplierMatchingResponse)
def suggest_suppliers(
    payload: JobMatchingRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suggest which supplier types should see this job and when.
    
    Uses AI to analyze the job details and recommend:
    - Which supplier types are relevant
    - When they should be notified (offset_days) based on material procurement timing
    
    Returns a list of supplier types with offset days for timing.
    """
    
    logger.info("Suggesting suppliers for job")
    
    job_data = {
        "permit_number": payload.permit_number,
        "permit_status": payload.permit_status,
        "project_type": payload.project_type,
        "property_type": payload.property_type,
        "job_address": payload.job_address,
        "cost": payload.cost,
        "job_description": payload.job_description,
        "contractor_name": payload.contractor_name,
        "company_name": payload.company_name,
        "state": payload.state,
        "county_city": payload.county_city,
    }
    
    service = GroqMatchingService()
    matches = service.match_suppliers(job_data)
    
    return SupplierMatchingResponse(matches=matches)
