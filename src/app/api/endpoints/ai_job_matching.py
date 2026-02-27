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
    """Individual user type match with offset days, slug, and display name."""

    display_name: str
    slug: str
    offset_days: int


class ContractorMatchingResponse(BaseModel):
    """Response model for contractor matching."""

    matches: List[UserTypeMatch]


class SupplierMatchingResponse(BaseModel):
    """Response model for supplier matching."""

    matches: List[UserTypeMatch]


class RelatedSuppliersRequest(BaseModel):
    """Request model for related supplier suggestions."""

    suppliers: List[str] = Field(
        ..., description="Array of supplier types to find related suppliers for"
    )


class RelatedSuppliersResponse(BaseModel):
    """Response model for related supplier suggestions."""

    suggested_suppliers: List[str]


class RelatedContractorsRequest(BaseModel):
    """Request model for related contractor suggestions."""

    contractors: List[str] = Field(
        ..., description="Array of contractor types to find related contractors for"
    )


class RelatedContractorsResponse(BaseModel):
    """Response model for related contractor suggestions."""

    suggested_contractors: List[str]


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
        project_type = data.get("project_type") or "construction project"
        property_type = data.get("property_type") or "property"
        description = data.get("job_description") or "construction work"
        cost = data.get("cost") or "not specified"
        permit_status = data.get("permit_status") or "unknown"

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
        project_type = data.get("project_type") or "construction project"
        property_type = data.get("property_type") or "property"
        description = data.get("job_description") or "construction work"
        cost = data.get("cost") or "not specified"

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
            "Content-Type": "application/json",
        }

        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert construction project analyst. Analyze jobs and match them with appropriate contractor or supplier types based on project requirements and construction sequencing. Always return valid JSON.",
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
                timeout=self.DEFAULT_TIMEOUT,
            )

            if not response.ok:
                error_text = response.text
                logger.error(
                    "Groq API returned status %s: %s", response.status_code, error_text
                )
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


def display_name_to_slug(display_name: str) -> str:
    """Convert display name to slug (e.g., 'Electrical Contractor' -> 'electrical_contractor')."""
    return (
        display_name.lower()
        .replace("/", "_")
        .replace("&", "and")
        .replace(",", "")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("__", "_")
        .replace("__", "_")
        .strip("_")
    )


# Exact contractor mapping (slug <-> display_name)
CONTRACTOR_SLUG_DISPLAY_MAP = {
    "Acoustical Contractor": "acoustical_contractor",
    "Arborist": "arborist",
    "Backflow Tester/Installer": "backflow_tester_installer",
    "Balancing / TAB contractor": "balancing_tab_contractor",
    "Boiler/Pressure Vessel": "boiler_pressure_vessel",
    "Cabinet Installer": "cabinet_installer",
    "Commercial kitchen hood installer fabricator": "commercial_kitchen_hood_installer_fabricator",
    "Concrete Contractor": "concrete_contractor",
    "Controls / BAS integrator": "controls_bas_integrator",
    "Controls / BMS integrator": "controls_bms_integrator",
    "Conveyance/Lift/Hoist Installer": "conveyance_lift_hoist_installer",
    "Countertop Fabricator": "countertop_fabricator",
    "Directional boring / jack & bore contractor": "directional_boring_jack_bore_contractor",
    "Door hardware / access control contractor": "door_hardware_access_control_contractor",
    "Dry chemical / foam / special hazard contractor": "dry_chemical_foam_special_hazard_contractor",
    "Drywall / Sheetrock Contractor": "drywall_sheetrock_contractor",
    "Electrical Contractor": "electrical_contractor",
    "Erosion Control Contractor": "erosion_control_contractor",
    "Escalator/Elevator": "escalator_elevator",
    "Event/Assembly Installer": "event_assembly_installer",
    "Excavation / Trenching Contractor": "excavation_trenching_contractor",
    "Fence/Railing Contractor": "fence_railing_contractor",
    "Fire Alarm Contractor": "fire_alarm_contractor",
    "Fire pump testing & service company": "fire_pump_testing_service_company",
    "Fire Sprinkler Contractor": "fire_sprinkler_contractor",
    "Flooring / Carpet Installers": "flooring_carpet_installers",
    "Flooring/Epoxy Installer": "flooring_epoxy_installer",
    "Foundation / Pier Installer": "foundation_pier_installer",
    "Framing Contractor": "framing_contractor",
    "Fuel Gas Contractor": "fuel_gas_contractor",
    "Garage Door Contractor": "garage_door_contractor",
    "Gas Contractor": "gas_contractor",
    "Gas Equipment Appliance Installer": "gas_equipment_appliance_installer",
    "Gate Operator": "gate_operator",
    "General Contractor": "general_contractor",
    "Graywater/Rainwater System Installer": "graywater_rainwater_system_installer",
    "Grease duct fabricator / installer": "grease_duct_fabricator_installer",
    "Gunite/shotcrete subcontractor": "gunite_shotcrete_subcontractor",
    "Gutter Installer": "gutter_installer",
    "Hood (Mechanical) Contractor": "hood_mechanical_contractor",
    "Hood Suppression Contractor": "hood_suppression_contractor",
    "Hydronic Piping Contractor": "hydronic_piping_contractor",
    "Insulation Contractor": "insulation_contractor",
    "Irrigation Contractor": "irrigation_contractor",
    "Irrigation Contractors": "irrigation_contractors",
    "Kitchen equipment installer": "kitchen_equipment_installer",
    "Land Clearing Contractor": "land_clearing_contractor",
    "Landscape Contractor": "landscape_contractor",
    "Low Voltage Contractor": "low_voltage_contractor",
    "Masonry Contractor": "masonry_contractor",
    "Mechanical / HVAC Contractor": "mechanical_hvac_contractor",
    "Medical equipment installer": "medical_equipment_installer",
    "Medical Gas Contractor": "medical_gas_contractor",
    "Painting Contractor": "painting_contractor",
    "Paver / Flatwork Contractors": "paver_flatwork_contractors",
    "Pipe Insulation Contractor": "pipe_insulation_contractor",
    "Plumbing Contractor": "plumbing_contractor",
    "Pool service & maintenance company": "pool_service_maintenance_company",
    "Racking/shelving installer": "racking_shelving_installer",
    "Refrigeration": "refrigeration",
    "Retaining Wall Contractor": "retaining_wall_contractor",
    "Roofing Contractor": "roofing_contractor",
    "Scaffolding Contractor": "scaffolding_contractor",
    "Septic/On Site Waste Water Installer": "septic_on_site_waste_water_installer",
    "Shoring/Underpinning Contractor": "shoring_underpinning_contractor",
    "Siding / Trim Contractor": "siding_trim_contractor",
    "Site Work/Grading Contractor": "site_work_grading_contractor",
    "Spray Booth Installer": "spray_booth_installer",
    "Structural steel / equipment support fabricator": "structural_steel_equipment_support_fabricator",
    "Stucco Contractor": "stucco_contractor",
    "Test & Balance / commissioning agent": "test_balance_commissioning_agent",
    "Tile Contractor": "tile_contractor",
    "Traffic Control Company": "traffic_control_company",
    "Trim Carpenter": "trim_carpenter",
    "underground utility contractor": "underground_utility_contractor",
    "Vacuum pump & medical air system installer": "vacuum_pump_medical_air_system_installer",
    "Walk-in cooler/freezer builder": "walk_in_cooler_freezer_builder",
    "Water treatment contractor": "water_treatment_contractor",
    "Water Well Driller/Pump Installer": "water_well_driller_pump_installer",
    "Waterproofing / Air Barrier Contractor": "waterproofing_air_barrier_contractor",
    "Welding Contractor": "welding_contractor",
    "Window / Door Contractor": "window_door_contractor",
}


@router.post("/suggest-contractors", response_model=ContractorMatchingResponse)
def suggest_contractors(
    payload: JobMatchingRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suggest which contractor types should see this job and when.
    Returns a list of contractor types with display name, slug, and offset days (using exact mapping).
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
    # matches: List[{"user_type": display_name, "offset_days": int}]
    enriched_matches = []
    for m in matches:
        display_name = m["user_type"]
        slug = CONTRACTOR_SLUG_DISPLAY_MAP.get(display_name)
        if slug is None:
            # If not found, skip or raise error (strict)
            continue
        enriched_matches.append(
            UserTypeMatch(
                display_name=display_name, slug=slug, offset_days=m["offset_days"]
            )
        )
    return ContractorMatchingResponse(matches=enriched_matches)


# Exact supplier mapping (display_name -> slug)
SUPPLIER_SLUG_DISPLAY_MAP = {
    "Access control Door hardware supplier": "access_control_door_hardware_supplier",
    "Acoustical Supplier": "acoustical_supplier",
    "Annunciator & graphic panel supplier": "annunciator_graphic_panel_supplier",
    "Appliance Suppliers": "appliance_suppliers",
    "Awning/canopy materials suppliers": "awning_canopy_materials_suppliers",
    "Backflow preventer supplier": "backflow_preventer_supplier",
    "Battery + exit sign component suppliers": "battery_exit_sign_component_suppliers",
    "Boiler / furnace equipment supplier": "boiler_furnace_equipment_supplier",
    "Bulk gas supplier (O\u2082, N\u2082O, N\u2082, CO\u2082, etc.)": "bulk_gas_supplier",
    "Cabinet Supplier": "cabinet_supplier",
    "Chiller manufacturer / distributor": "chiller_manufacturer_distributor",
    "Closet System Vendor": "closet_system_vendor",
    "CMU block Supplier": "cmu_block_supplier",
    "Composite/PVC decking distributor": "composite_pvc_decking_distributor",
    "Concrete Supplier": "concrete_supplier",
    "Condensate pump & neutralizer supplier": "condensate_pump_neutralizer_supplier",
    "Conduit & raceway supplier": "conduit_raceway_supplier",
    "Construction Trailer": "construction_trailer",
    "Controls hardware supplier": "controls_hardware_supplier",
    "Cooling tower / fluid cooler supplier": "cooling_tower_fluid_cooler_supplier",
    "Countertop Suppliers": "countertop_suppliers",
    "Crane Service": "crane_service",
    "Drainage suppliers": "drainage_suppliers",
    "Drywall / Sheetrock Supplier": "drywall_sheetrock_supplier",
    "Dumpster / Roll Off Supplier": "dumpster_roll_off_supplier",
    "Electrical gear supplier": "electrical_gear_supplier",
    "Electrical / Low Voltage Distributor": "electrical_low_voltage_distributor",
    "Electrical Supply House": "electrical_supply_house",
    "Equipment Rental": "equipment_rental",
    "Erosion control supplier": "erosion_control_supplier",
    "Erosion materials": "erosion_materials",
    "ESS / Battery System Supplier": "ess_battery_system_supplier",
    "Evaporator / coil supplier": "evaporator_coil_supplier",
    "Exhaust fan supplier": "exhaust_fan_supplier",
    "Explosives Storage Operator": "explosives_storage_operator",
    "Extrusion / framing system suppliers": "extrusion_framing_system_suppliers",
    "Fasteners / anchoring suppliers": "fasteners_anchoring_suppliers",
    "Fence material suppliers/distributors": "fence_material_suppliers_distributors",
    "Finish carpentry suppliers (Interior Doors & Trim)": "finish_carpentry_suppliers_interior_doors_trim",
    "Fire alarm cable supplier": "fire_alarm_cable_supplier",
    "Fire alarm equipment supplier": "fire_alarm_equipment_supplier",
    "Fire alarm panel manufacturer / distributor": "fire_alarm_panel_manufacturer_distributor",
    "Fire Protection Material Supplier": "fire_protection_material_supplier",
    "Fire pump controller suppliers": "fire_pump_controller_suppliers",
    "Fire pump manufacturers / authorized distributors": "fire_pump_manufacturers_authorized_distributors",
    "Fire sprinkler material house": "fire_sprinkler_material_house",
    "Flooring Distributor (Tile, LVP, Wood & Carpet)": "flooring_distributor",
    "Fuel shutoff valve supplier": "fuel_shutoff_valve_supplier",
    "Garage Door Supplier": "garage_door_supplier",
    "Gas Appliance Supplier": "gas_appliance_supplier",
    "Gas Pipe & Fittings Supplier": "gas_pipe_fittings_supplier",
    "Gas Regulator & Meter Set Supplier": "gas_regulator_meter_set_supplier",
    "Gate/door operator & barrier supplier": "gate_door_operator_barrier_supplier",
    "Glass fabricator": "glass_fabricator",
    "Grease duct & fittings supplier": "grease_duct_fittings_supplier",
    "Gutter Supplier": "gutter_supplier",
    "Headwall & boom manufacturer / dealer": "headwall_boom_manufacturer_dealer",
    "Hood suppression equipment distributor": "hood_suppression_equipment_distributor",
    "HVAC Distributor": "hvac_distributor",
    "Hydronic components supplier": "hydronic_components_supplier",
    "Instrument air system supplier": "instrument_air_system_supplier",
    "Instrumentation & controls supplier": "instrumentation_controls_supplier",
    "Insulation Suppliers": "insulation_suppliers",
    "Interface module supplier": "interface_module_supplier",
    "Inverter + BOS Supplier": "inverter_bos_supplier",
    "Irrigation Suppliers": "irrigation_suppliers",
    "kitchen hood manufacturer / dealer": "kitchen_hood_manufacturer_dealer",
    "Landscape Suppliers": "landscape_suppliers",
    "Leak Detection & Testing Equipment Supplier": "leak_detection_testing_equipment_supplier",
    "Lighting distributors / commercial": "lighting_distributors_commercial",
    "Lighting/LED module suppliers": "lighting_led_module_suppliers",
    "Low-voltage cable & device supplier": "low_voltage_cable_device_supplier",
    "Lumber Supplier": "lumber_supplier",
    "Makeup air unit (MAU) supplier": "makeup_air_unit_supplier",
    "Manifold & cylinder system supplier": "manifold_cylinder_system_supplier",
    "Masonry Supplier": "masonry_supplier",
    "Material Hoist/Manlift": "material_hoist_manlift",
    "Medical air compressor system supplier": "medical_air_compressor_system_supplier",
    "medical Gas and equipment Suppliers": "medical_gas_and_equipment_suppliers",
    "Medical gas copper tube supplier": "medical_gas_copper_tube_supplier",
    "Medical gas fittings & brazing materials supplier": "medical_gas_fittings_brazing_materials_supplier",
    "Medical gas outlet / inlet terminal supplier": "medical_gas_outlet_inlet_terminal_supplier",
    "Medical vacuum system supplier": "medical_vacuum_system_supplier",
    "Monitoring company / central station integrator": "monitoring_company_central_station_integrator",
    "NFPA 99 medical gas verification agency / verifier": "nfpa_99_medical_gas_verification_agency_verifier",
    "Notification appliance supplier": "notification_appliance_supplier",
    "Paint / Coatings Suppliers": "paint_coatings_suppliers",
    "Paver / Flatwork Suppliers": "paver_flatwork_suppliers",
    "Pipe/fittings suppliers": "pipe_fittings_suppliers",
    "Pipe insulation supplier": "pipe_insulation_supplier",
    "Plumbing Supplier": "plumbing_supplier",
    "Pool equipment supplier / distributor": "pool_equipment_supplier_distributor",
    "Portable Sanitation Rental": "portable_sanitation_rental",
    "Pressure regulator & line regulator supplier": "pressure_regulator_line_regulator_supplier",
    "Rack & condensing unit supplier": "rack_condensing_unit_supplier",
    "Racking and Mounting Supplier (solar)": "racking_mounting_supplier_solar",
    "Railing system suppliers": "railing_system_suppliers",
    "Rebar/Fabrication Shop": "rebar_fabrication_shop",
    "Rebar & structural hardware": "rebar_structural_hardware_supplier",
    "rebar & structural hardware; vapor barrier & under-slab Suppliers": "rebar_structural_hardware_vapor_barrier_under_slab_suppliers",
    "Refrigerant & specialty gas supplier": "refrigerant_specialty_gas_supplier",
    "Refrigeration valves & fittings supplier.": "refrigeration_valves_fittings_supplier",
    "Riser assembly supplier": "riser_assembly_supplier",
    "Roofing Materials Distributor": "roofing_materials_distributor",
    "Safety compliance suppliers": "safety_compliance_suppliers",
    "Safety/fall protection vendor": "safety_fall_protection_vendor",
    "Scaffolding Vendor": "scaffolding_vendor",
    "Sealant /adhesive suppliers": "sealant_adhesive_suppliers",
    "Security system supplier": "security_system_supplier",
    "Seismic bracing & hanger hardware supplier": "seismic_bracing_hanger_hardware_supplier",
    "Seismic Gas Shutoff Valve Supplier": "seismic_gas_shutoff_valve_supplier",
    "shoring/trench safety rental suppliers": "shoring_trench_safety_rental_suppliers",
    "Shotcrete/gunite materials supplier": "shotcrete_gunite_materials_supplier",
    "Shower Glass Supplier": "shower_glass_supplier",
    "Siding / Trim Supplier": "siding_trim_supplier",
    "Sign component suppliers": "sign_component_suppliers",
    "Smart Gas Control Supplier": "smart_gas_control_supplier",
    "Sod / grass Suppliers": "sod_grass_suppliers",
    "Solar Module Supplier": "solar_module_supplier",
    "Solar/PV Equipment Supplier": "solar_pv_equipment_supplier",
    "Sprinkler head manufacturer / distributor": "sprinkler_head_manufacturer_distributor",
    "Steel supplier / structural metals distributor": "steel_supplier_structural_metals_distributor",
    "Stone / Aggregate Supplier": "stone_aggregate_supplier",
    "Stone/Quartz Slab Supplier": "stone_quartz_slab_supplier",
    "Storefront/curtain wall system manufacturers / distributors": "storefront_curtain_wall_system_manufacturers_distributors",
    "structural connector & hardware Suppliers": "structural_connector_hardware_suppliers",
    "Temporary Fencing Supplier": "temporary_fencing_supplier",
    "Thermostat & controls supplier": "thermostat_controls_supplier",
    "Third-party verifier / certifier": "third_party_verifier_certifier",
    "Tile Suppliers": "tile_suppliers",
    "Tool Supplier": "tool_supplier",
    "Tower Crane Erector": "tower_crane_erector",
    "Tracer Wire & Marking Materials Supplier": "tracer_wire_marking_materials_supplier",
    "Tree Removal Service": "tree_removal_service",
    "Truss Company": "truss_company",
    "Underground piping & fittings supplier": "underground_piping_fittings_supplier",
    "Valves & specialty fittings supplier": "valves_specialty_fittings_supplier",
    "Vapor barrier & under-slab suppliers": "vapor_barrier_under_slab_suppliers",
    "Venting system supplier": "venting_system_supplier",
    "Vinyl fence suppliers": "vinyl_fence_suppliers",
    "Waste/Roll-Off Service": "waste_roll_off_service",
    "Waterproofing / Air Barrier Suppliers": "waterproofing_air_barrier_suppliers",
    "Window / Door / Glass Distributors": "window_door_glass_distributors",
    "Anchor bolts/embeds supplier": "anchor_bolts_embeds_supplier",
    "Asbestos abatement material supplier": "asbestos_abatement_material_supplier",
    "Commercial hardware supplier": "commercial_hardware_supplier",
    "Decking material supplier (treated wood/composite/PVC)": "decking_material_supplier",
    "Dock lighting supplier": "dock_lighting_supplier",
    "Dock system manufacturer/supplier": "dock_system_supplier",
    "Drying equipment rental (dehumidifiers, air movers, heaters)": "drying_equipment_rental",
    "Duct supply (duct board/metal duct, registers, dampers)": "duct_supply_supplier",
    "Elevator fixtures/interior supplier (COP, buttons, lanterns, cab finishes)": "elevator_fixtures_interior_supplier",
    "Elevator parts supplier (if independent/mod: controller packages, drives, fixtures)": "elevator_parts_supplier",
    "Escalator Handrail supplier (handrail belts\u2014common replacement item)": "escalator_handrail_supplier",
    "Escalator / moving-walk OEM / manufacturer (unit package)": "escalator_moving_walk_oem_manufacturer",
    "Escalator parts supplier (modernization components, drives, controllers)": "escalator_parts_supplier",
    "Fertilizer/seed supplier": "fertilizer_seed_supplier",
    "Fill Dirt / Soil": "fill_dirt_soil_supplier",
    "Generator OEM / Dealer": "generator_oem_dealer",
    "Hazmat disposal supplier / transporter": "hazmat_disposal_transporter",
    "HVAC Parts supplier (capacitors, contactors, disconnects, whip, pad, vibration isolators)": "hvac_parts_supplier",
    "Interior doors/frames/hardware supplier": "interior_doors_frames_hardware_supplier",
    "Kitchen equipment supplier": "kitchen_equipment_supplier",
    "Marine hardware supplier (cleats, brackets, bolts, hangers)": "marine_hardware_supplier",
    "Metal stud/track supplier": "metal_stud_track_supplier",
    "Modular ramp system supplier (aluminum ramp kits, landings)": "modular_ramp_system_supplier",
    "Mulch Supplier": "mulch_supplier",
    "Overhead door equipment supplier": "overhead_door_equipment_supplier",
    "Piles supplier (timber/steel/concrete)": "piles_supplier_timber_steel_concrete",
    "Plant nursery supplier (trees/shrubs/perennials)": "plant_nursery_supplier",
    "Platform lift OEM / manufacturer": "platform_lift_oem_manufacturer",
    "Plywood/sheathing supplier (deck repairs)": "plywood_sheathing_supplier_deck_repairs",
    "PPE / safety supplier": "ppe_safety_supplier",
    "Safety equipment supplier (PPE, signage, cones, fire extinguishers)": "safety_equipment_supplier",
    "Topsoil supplier": "topsoil_supplier",
    "Underlayment supplier (synthetic felt, ice & water shield)": "underlayment_supplier",
    "Walk-in cooler/freezer supplier": "walk_in_cooler_freezer_supplier",
    "Weatherproofing/sealants supplier (flashing tape, sealant, gaskets)": "weatherproofing_sealants_supplier",
    "Asbestos abatement contractor": "asbestos_abatement_contractor",
    "Boat Lift Installer": "boat_lift_installer",
    "Building Contractor": "building_contractor",
    "Commercial Framing Contractor": "commercial_framing_contractor",
    "Commercial Roofing contractor": "commercial_roofing_contractor",
    "Contents pack-out / cleaning company": "contents_packout_cleaning_company",
    "Demolition Contractor": "demolition_contractor",
    "Drilling / caisson contractor": "drilling_caisson_contractor",
    "Exterior cladding contractor": "exterior_cladding_contractor",
    "Lead shielding contractor (imaging/X-ray)": "lead_shielding_contractor",
    "Millwork installer (counters, displays, back bar)": "millwork_installer",
    "Mold remediation contractor": "mold_remediation_contractor",
    "Monument sign fabricator": "monument_sign_fabricator",
    "Overhead door / storefront entry door installer": "overhead_door_storefront_entry_door_installer",
    "Pest Control / Termite": "pest_control_termite",
    "Recycling / salvage contractor": "recycling_salvage_contractor",
    "Sheet metal contractor (edge metal, copings, custom flashings)": "sheet_metal_contractor",
    "Sheet metal / ductwork contractor": "sheet_metal_ductwork_contractor",
    "Site Security installer": "site_security_installer",
    "Stair / guardrail / handrail contractor": "stair_guardrail_handrail_contractor",
    "Storefront / glazing / curtain wall contractor": "storefront_glazing_curtain_wall_contractor",
    "Striping/signage installer": "striping_signage_installer",
    "TAB contractor (air balancing)": "tab_contractor_air_balancing",
    "Third-party verifier / certifier; NFPA 99 medical gas verification agency / verifier": "third_party_nfpa99_medical_gas_verifier",
    "Water mitigation company": "water_mitigation_company",
    "Zone valve box supplier": "zone_valve_box_supplier",
    "Doors/frames/hardware supplier": "doors_frames_hardware_supplier",
    "Elevator OEM / manufacturer (cab, controller, machine, doors, rails)": "elevator_oem_manufacturer",
}


@router.post("/suggest-suppliers", response_model=SupplierMatchingResponse)
def suggest_suppliers(
    payload: JobMatchingRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suggest which supplier types should see this job and when.
    Returns a list of supplier types with display name, slug, and offset days (using exact mapping).
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
    # matches: List[{"user_type": display_name, "offset_days": int}]
    enriched_matches = []
    for m in matches:
        display_name = m["user_type"]
        slug = SUPPLIER_SLUG_DISPLAY_MAP.get(display_name)
        if slug is None:
            # If not found, skip or raise error (strict)
            continue
        enriched_matches.append(
            UserTypeMatch(
                display_name=display_name, slug=slug, offset_days=m["offset_days"]
            )
        )
    return SupplierMatchingResponse(matches=enriched_matches)


# New endpoint for suggesting related suppliers


@router.post("/suggest-related-suppliers", response_model=RelatedSuppliersResponse)
def suggest_related_suppliers(
    payload: RelatedSuppliersRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suggest related suppliers based on an input array of suppliers.

    Uses AI to analyze the input suppliers and recommend related/complementary suppliers
    from the master list, excluding the suppliers that were sent in the request.

    Example:
    Input: ["Concrete Supplier", "Rebar/Fabrication Shop"]
    Output: ["Steel supplier / structural metals distributor", "Anchor bolts/embeds supplier", ...]
    """

    logger.info(
        f"Suggesting related suppliers for {len(payload.suppliers)} input suppliers"
    )

    # All available supplier types (from the user's list)
    all_suppliers = [
        # 1. Structural, Concrete, Masonry & Metals
        "Anchor bolts/embeds supplier",
        "Fasteners / anchoring suppliers",
        "structural connector & hardware Suppliers",
        "Seismic bracing & hanger hardware supplier",
        "rebar & structural hardware; vapor barrier & under-slab Suppliers",
        "Rebar/Fabrication Shop",
        "Concrete Supplier",
        "CMU block Supplier",
        "Masonry Supplier",
        "Steel supplier / structural metals distributor",
        "Stone / Aggregate Supplier",
        "Piles supplier (timber/steel/concrete)",
        "Shotcrete/gunite materials supplier",
        # 2. Lumber, Framing & Carpentry Materials
        "Lumber Supplier",
        "Truss Company",
        "Plywood/sheathing supplier (deck repairs)",
        "Finish Carpentry Suppliers (Interior Doors & Trim)",
        "Closet System Vendor",
        "Cabinet Supplier",
        "Countertop Suppliers",
        "Stone/Quartz Slab Supplier",
        # 3. Roofing, Siding, Decking, Waterproofing & Sealants
        "Roofing Materials Distributor",
        "Underlayment supplier (synthetic felt, ice & water shield)",
        "Siding / Exterior Trim Supplier",
        "Composite/PVC decking distributor",
        "Decking material supplier (treated wood/composite/PVC)",
        "Awning/canopy materials suppliers",
        "Insulation Supplier",
        "Gutter Supplier",
        "Sealant /adhesive suppliers",
        "Weatherproofing/sealants supplier (flashing tape, sealant, gaskets)",
        "waterproofing / air barrier Suppliers",
        "Vapor barrier / underslab insulation supplier",
        # 4. Openings, Hardware, Glass & Storefront
        "Doors/frames/hardware supplier",
        "Interior doors/frames/hardware supplier",
        "Commercial hardware supplier",
        "Access control Door hardware supplier",
        "Gate/door operator & barrier supplier",
        "Garage Door Supplier",
        "Overhead door equipment supplier",
        "Modular ramp system supplier (aluminum ramp kits, landings)",
        "Window/Door/Glass Distributors",
        "Glass fabricator",
        "Shower Glass Supplier",
        "Storefront/curtain wall system manufacturers / distributors",
        "Extrusion / framing system suppliers",
        # 5. Interior Finishes & Architectural Products
        "Drywall / Sheetrock Supplier",
        "Metal stud/track supplier",
        "Acoustical Supplier",
        "Flooring Distributor (Tile, LVP, Wood & Carpet)",
        "Tile Suppliers",
        "Paint / Coatings Suppliers",
        "Railing system suppliers",
        "Sign component suppliers",
        # 6. Electrical, Lighting, Security & Controls Supply
        "Electrical Supply House",
        "Electrical gear supplier",
        "Electrical/Low Voltage Distributor",
        "Conduit & raceway supplier",
        "Lighting distributors / commercial",
        "Lighting/LED module suppliers",
        "Low-voltage cable & device supplier",
        "Security system supplier",
        "Controls hardware supplier",
        "Instrumentation & controls supplier",
        "Interface module supplier",
        "Thermostat & controls supplier",
        "Generator OEM / Dealer",
        "ESS / Battery System Supplier",
        "Inverter + BOS Supplier",
        "Solar Module Supplier",
        "Solar/PV Equipment Supplier",
        "Racking and Mounting Supplier (solar)",
        # 7. Mechanical & HVAC Equipment / Air Distribution
        "HVAC Distributor",
        "HVAC Parts supplier (capacitors, contactors, disconnects, whip, pad, vibration isolators)",
        "Boiler / furnace equipment supplier",
        "Chiller manufacturer / distributor",
        "Cooling tower / fluid cooler supplier",
        "Makeup air unit (MAU) supplier",
        "Exhaust fan supplier",
        "Evaporator / coil supplier",
        "Hydronic components supplier",
        "Condensate pump & neutralizer supplier",
        "duct supply (duct board/metal duct, registers, dampers)",
        "Pipe insulation supplier",
        # 8. Plumbing, Water, Drainage & Venting
        "Plumbing Supplier",
        "Pipe/fittings suppliers",
        "Underground piping & fittings supplier",
        "Drainage suppliers",
        "Backflow preventer supplier",
        "Valves & specialty fittings supplier",
        "Venting system supplier",
        "Zone valve box supplier",
        "Tracer Wire & Marking Materials Supplier",
        # 9. Gas Distribution, Regulators & Shutoff Controls
        "Gas Pipe & Fittings Supplier",
        "Gas Regulator & Meter Set Supplier",
        "Pressure regulator & line regulator supplier",
        "Fuel shutoff valve supplier",
        "Seismic Gas Shutoff Valve Supplier",
        "Smart Gas Control Supplier",
        "Gas Appliance Supplier",
        # 10. Fire Protection & Life Safety Systems
        "Fire sprinkler material house",
        "Sprinkler head manufacturer / distributor",
        "Fire Protection Material Supplier",
        "Riser assembly supplier",
        "Fire pump controller suppliers",
        "Fire pump manufacturers / authorized distributors",
        "Fire alarm panel manufacturer / distributor",
        "Fire alarm cable supplier",
        "Fire alarm equipment supplier",
        "Annunciator & graphic panel supplier",
        "Notification appliance supplier",
        "Battery + exit sign component suppliers",
        "Hood suppression equipment distributor",
        # 11. Refrigeration & Commercial Kitchen Supply
        "Appliance Suppliers",
        "Kitchen equipment supplier",
        "kitchen hood manufacturer / dealer",
        "Grease duct & fittings supplier",
        "Walk-in cooler/freezer supplier",
        "Rack & condensing unit supplier",
        "Refrigeration valves & fittings supplier",
        "Refrigerant & specialty gas supplier",
        # 12. Medical Gas, Specialty Gas & Healthcare Systems
        "medical Gas and equipment Suppliers",
        "Bulk gas supplier (O₂, N₂O, N₂, CO₂, etc.)",
        "Manifold & cylinder system supplier",
        "Medical gas outlet / inlet terminal supplier",
        "Medical gas copper tube supplier",
        "Medical gas fittings & brazing materials supplier",
        "Medical vacuum system supplier",
        "Medical air compressor system supplier",
        "Instrument air system supplier",
        "Headwall & boom manufacturer / dealer",
        "Leak Detection & Testing Equipment Supplier",
        # 13. Vertical Transportation & Lifts
        "Elevator OEM / manufacturer (cab, controller, machine, doors, rails)",
        "Elevator parts supplier (if independent/mod: controller packages, drives, fixtures)",
        "Elevator fixtures/interior supplier (COP, buttons, lanterns, cab finishes)",
        "Escalator / moving-walk OEM / manufacturer (unit package)",
        "Escalator parts supplier (modernization components, drives, controllers)",
        "Escalator Handrail supplier (handrail belts—common replacement item)",
        "Platform lift OEM / manufacturer",
        # 14. Site, Civil, Utilities & Erosion Control
        "Erosion control supplier",
        "Fill Dirt / Soil",
        "Topsoil supplier",
        "Mulch Supplier",
        "Paver /Flatwork Suppliers",
        # 15. Landscaping, Fencing, Rental, Safety & Environmental Support
        "Landscape Suppliers",
        "irrigation Suppliers",
        "Fertilizer/seed supplier",
        "Plant nursery supplier (trees/shrubs/perennials)",
        "Sod / grass Suppliers",
        "Fence material suppliers/distributors",
        "Vinyl fence suppliers",
        "Dock system manufacturer/supplier",
        "Dock lighting supplier",
        "Marine hardware supplier (cleats, brackets, bolts, hangers)",
        "Temporary Fencing Supplier",
        "Equipment Rental",
        "shoring/trench safety rental suppliers",
        "Scaffolding Vendor",
        "Tool Supplier",
        "Dumpster/Roll Off Supplier",
        "Portable Sanitation Rental",
        "Drying equipment rental (dehumidifiers, air movers, heaters)",
        "PPE / safety supplier",
        "Safety compliance suppliers (pool alarms, self-closing/self-latching gate hardware)",
        "Safety equipment supplier (PPE, signage, cones, fire extinguishers)",
        "Safety/fall protection vendor",
        "Hazmat disposal supplier / transporter",
        "Asbestos abatement material supplier",
    ]

    # Build prompt for Groq
    suppliers_str = ", ".join(payload.suppliers)
    all_suppliers_str = ", ".join(all_suppliers)

    prompt = f"""You are an expert construction supply chain analyst. Given a list of supplier types, suggest 5-10 RELATED or COMPLEMENTARY suppliers that would typically be needed for the same type of project.

INPUT SUPPLIERS:
{suppliers_str}

AVAILABLE SUPPLIER TYPES (choose from this list ONLY):
{all_suppliers_str}

CRITICAL INSTRUCTIONS:
1. Suggest 5-10 suppliers that are RELATED or COMPLEMENTARY to the input suppliers
2. DO NOT include any of the input suppliers in your suggestions
3. Think about what other materials/equipment would be needed for the same type of project
4. Consider the construction workflow and what comes before/after these suppliers
5. Use EXACT names from the available supplier types list above
6. Return ONLY suppliers that are DIFFERENT from the input suppliers

EXAMPLES:

Input: ["Concrete Supplier", "Rebar/Fabrication Shop"]
Output: ["Steel supplier / structural metals distributor", "Anchor bolts/embeds supplier", "Fasteners / anchoring suppliers", "waterproofing / air barrier Suppliers", "Vapor barrier / underslab insulation supplier"]

Input: ["HVAC Distributor", "Electrical Supply House"]
Output: ["Plumbing Supplier", "Controls hardware supplier", "Thermostat & controls supplier", "Conduit & raceway supplier", "Low-voltage cable & device supplier"]

Input: ["Lumber Supplier", "Truss Company"]
Output: ["Fasteners / anchoring suppliers", "Plywood/sheathing supplier (deck repairs)", "Roofing Materials Distributor", "Window/Door/Glass Distributors", "Insulation Supplier"]

CRITICAL: Return ONLY valid JSON in this exact format:
{{
  "suggested_suppliers": [
    "Supplier Name 1",
    "Supplier Name 2",
    "Supplier Name 3"
  ]
}}

Analyze the input suppliers and return 5-10 related suppliers that would be needed for similar projects."""

    # Call Groq API
    service = GroqMatchingService()

    headers = {
        "Authorization": f"Bearer {service.api_key}",
        "Content-Type": "application/json",
    }

    request_body = {
        "model": service.model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert construction supply chain analyst. Suggest related suppliers based on input suppliers. Always return valid JSON.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.4,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }

    try:
        logger.info("Calling Groq API for related supplier suggestions")

        response = requests.post(
            service.api_endpoint,
            json=request_body,
            headers=headers,
            timeout=service.DEFAULT_TIMEOUT,
        )

        if not response.ok:
            error_text = response.text
            logger.error(
                "Groq API returned status %s: %s", response.status_code, error_text
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Groq API error (status {response.status_code})",
            )

        response_json = response.json()
        content = response_json["choices"][0]["message"]["content"]
        result = json.loads(content)
        suggested_suppliers = result.get("suggested_suppliers", [])

        # Filter out any suppliers that were in the input (just to be safe)
        suggested_suppliers = [
            s for s in suggested_suppliers if s not in payload.suppliers
        ]

        logger.info(
            f"Successfully suggested {len(suggested_suppliers)} related suppliers"
        )

        return RelatedSuppliersResponse(suggested_suppliers=suggested_suppliers)

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
        logger.error("Unexpected error during related supplier suggestion: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post("/suggest-related-contractors", response_model=RelatedContractorsResponse)
def suggest_related_contractors(
    payload: RelatedContractorsRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suggest related contractors based on an input array of contractors.

    Uses AI to analyze the input contractors and recommend related/complementary contractors
    from the master list, excluding the contractors that were sent in the request.

    Example:
    Input: ["Concrete Contractor", "Framing Contractor"]
    Output: ["Masonry Contractor", "Roofing Contractor", "Waterproofing / air barrier Contractor", ...]
    """

    logger.info(
        f"Suggesting related contractors for {len(payload.contractors)} input contractors"
    )

    # All available contractor types (from the user's list)
    all_contractors = [
        # 1. General / Prime Contractors
        "Building Contractor",
        "General Contractor",
        # 2. Structural, Concrete & Framing
        "Commercial Framing Contractor",
        "Framing Contractor",
        "Concrete Contractor",
        "Foundation / Pier Installer",
        "Masonry Contractor",
        "Structural steel / equipment support fabricator",
        "Welding Contractor",
        "Stair / guardrail / handrail contractor",
        # 3. Building Envelope, Openings & Exterior
        "Commercial Roofing contractor",
        "Roofing Contractor",
        "Exterior cladding contractor",
        "Siding / Exterior Trim Contractor",
        "Stucco Contractor",
        "Waterproofing / air barrier Contractor",
        "Window/Door Contractor",
        "Gutter Installer",
        "Sheet metal contractor (edge metal, copings, custom flashings)",
        "Storefront / glazing / curtain wall contractor",
        "Insulation Contractor",
        "Garage Door Contractor",
        "Gate Operator",
        "Overhead door / storefront entry door installer",
        "Door hardware / access control contractor",
        # 4. Interiors & Finish Trades
        "Drywall / Sheetrock Contractor",
        "Painting Contractor",
        "Acoustical Contractor",
        "Flooring / carpet Installers",
        "Flooring/Epoxy Installer",
        "Tile Contractor",
        "Cabinet Installer",
        "Countertop Fabricator",
        "millwork installer (counters, displays, back bar)",
        "Trim Carpenter",
        "Racking/shelving installer",
        # 5. Mechanical (HVAC, Refrigeration, Ductwork & TAB)
        "Mechanical/HVAC Contractor",
        "Refrigeration Contractor",
        "Hydronic Piping Contractor",
        "Sheet metal / ductwork contractor",
        "Pipe Insulation Contractor",
        "Boiler/Pressure Vessel",
        "Balancing / TAB contractor",
        "TAB contractor (air balancing)",
        "Test & Balance / commissioning agent",
        # 6. Plumbing, Gas & Water Systems
        "Plumbing Contractor",
        "Backflow Tester/Installer",
        "Fuel Gas Contractor",
        "Gas Contractor",
        "Gas Equipment Appliance Installer",
        "Septic/On Site Waste Water Installer",
        "Graywater/Rainwater System Installer",
        "Water treatment contractor",
        "Water Well Driller/Pump Installer",
        # 7. Electrical, Low Voltage, Controls & Security
        "Electrical Contractor",
        "Low Voltage Contractor",
        "Controls / BAS integrator",
        "Controls / BMS integrator",
        "Site Security installer",
        "Monitoring company / central station integrator",
        # 8. Fire Protection & Life Safety
        "Fire Alarm Contractor",
        "Fire Sprinkler Contractor",
        "Fire pump testing & service company",
        "Hood Suppression Contractor",
        "Dry chemical / foam / special hazard contractor",
        # 9. Sitework, Civil, Utilities & Logistics
        "Site Work/Grading Contractor",
        "Excavation/Trenching Contractor",
        "Land Clearing Contractor",
        "Erosion Control Contractor",
        "underground utility contractor",
        "Directional boring / jack & bore contractor",
        "Drilling / caisson contractor",
        "Shoring/Underpinning Contractor",
        "Retaining Wall Contractor",
        "Scaffolding Contractor",
        "Construction Trailer",
        "Event/Assembly Installer",
        "Traffic Control Company",
        "Waste/Roll-Off Service",
        "Recycling / salvage contractor",
        # 10. Environmental, Hazmat & Remediation
        "Asbestos abatement contractor",
        "Demolition Contractor",
        "Mold remediation contractor",
        "Water mitigation company",
        "Contents pack-out / cleaning company",
        "Pest Control / Termite",
        "Explosives Storage Operator",
        # 11. Landscaping, Hardscape & Site Amenities
        "Landscape Contractor",
        "Irrigation Contractor",
        "Arborist",
        "Tree Removal Service",
        "Paver /Flatwork Contractor",
        "Gunite/shotcrete subcontractor",
        "Pool service & maintenance company",
        "Fence/Railing Contractor",
        "Monument sign fabricator",
        "Striping/signage installer",
        # 12. Specialty Equipment, Vertical Transport & Compliance
        "Commercial kitchen hood installer fabricator",
        "Grease duct fabricator / installer",
        "Hood (Mechanical) Contractor",
        "Kitchen equipment installer",
        "Walk-in cooler/freezer builder",
        "Medical Gas Contractor",
        "Vacuum pump & medical air system installer",
        "Third-party verifier / certifier",
        "NFPA 99 medical gas verification agency / verifier",
        "Lead shielding contractor (imaging/X-ray)",
        "Spray Booth Installer",
        "Conveyance/Lift/Hoist Installer",
        "Escalator/Elevator",
        "Material Hoist/Manlift",
        "Crane Service",
        "Tower Crane Erector",
        "Boat Lift Installer",
    ]

    # Build prompt for Groq
    contractors_str = ", ".join(payload.contractors)
    all_contractors_str = ", ".join(all_contractors)

    prompt = f"""You are an expert construction project analyst. Given a list of contractor types, suggest 5-10 RELATED or COMPLEMENTARY contractors that would typically be needed for the same type of project.

INPUT CONTRACTORS:
{contractors_str}

AVAILABLE CONTRACTOR TYPES (choose from this list ONLY):
{all_contractors_str}

CRITICAL INSTRUCTIONS:
1. Suggest 5-10 contractors that are RELATED or COMPLEMENTARY to the input contractors
2. DO NOT include any of the input contractors in your suggestions
3. Think about what other trades would be needed for the same type of project
4. Consider the construction workflow and what comes before/after these contractors
5. Use EXACT names from the available contractor types list above
6. Return ONLY contractors that are DIFFERENT from the input contractors

EXAMPLES:

Input: ["Concrete Contractor", "Framing Contractor"]
Output: ["Masonry Contractor", "Roofing Contractor", "Waterproofing / air barrier Contractor", "Foundation / Pier Installer", "Window/Door Contractor"]

Input: ["Electrical Contractor", "Plumbing Contractor"]
Output: ["Mechanical/HVAC Contractor", "Fire Alarm Contractor", "Fire Sprinkler Contractor", "Low Voltage Contractor", "Controls / BAS integrator"]

Input: ["Drywall / Sheetrock Contractor", "Painting Contractor"]
Output: ["Flooring / carpet Installers", "Tile Contractor", "Cabinet Installer", "Trim Carpenter", "Acoustical Contractor"]

CRITICAL: Return ONLY valid JSON in this exact format:
{{
  "suggested_contractors": [
    "Contractor Name 1",
    "Contractor Name 2",
    "Contractor Name 3"
  ]
}}

Analyze the input contractors and return 5-10 related contractors that would be needed for similar projects."""

    # Call Groq API
    service = GroqMatchingService()

    headers = {
        "Authorization": f"Bearer {service.api_key}",
        "Content-Type": "application/json",
    }

    request_body = {
        "model": service.model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert construction project analyst. Suggest related contractors based on input contractors. Always return valid JSON.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.4,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }

    try:
        logger.info("Calling Groq API for related contractor suggestions")

        response = requests.post(
            service.api_endpoint,
            json=request_body,
            headers=headers,
            timeout=service.DEFAULT_TIMEOUT,
        )

        if not response.ok:
            error_text = response.text
            logger.error(
                "Groq API returned status %s: %s", response.status_code, error_text
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Groq API error (status {response.status_code})",
            )

        response_json = response.json()
        content = response_json["choices"][0]["message"]["content"]
        result = json.loads(content)
        suggested_contractors = result.get("suggested_contractors", [])

        # Filter out any contractors that were in the input (just to be safe)
        suggested_contractors = [
            c for c in suggested_contractors if c not in payload.contractors
        ]

        logger.info(
            f"Successfully suggested {len(suggested_contractors)} related contractors"
        )

        return RelatedContractorsResponse(suggested_contractors=suggested_contractors)

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
        logger.error(
            "Unexpected error during related contractor suggestion: %s", str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
