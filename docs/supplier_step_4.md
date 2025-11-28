
# Supplier Onboarding — Step 4: Product Categories

Purpose
- Capture the supplier's primary product/material category and the detailed subcategory product types they supply. This data is used for lead matching, search/filtering, and displaying supplier profiles.

Quick schema notes
- Model: `SupplierStep4` (Pydantic)
- Fields:
  - `product_categories` (string): Primary category selected from the dropdown of 17 categories.
  - `product_types` (list[string]): One or more subcategory/product-type strings. Backend validation requires at least one and a maximum of 20.

Validation
- `product_types` must be a non-empty list (error: `Please provide at least one product type`).
- `product_types` accepts at most 20 entries (error: `You can provide at most 20 product types`).
- `product_categories` is stored as text and should match one of the 17 dropdown values for consistency.

Supplier Dropdown Categories (17 primary categories)
- Waste, hauling & sanitation
- Fencing, scaffolding & temporary structures
- Concrete, rebar & structural materials
- Lumber, framing & sheathing
- Roofing, waterproofing & insulation
- Windows, doors & storefronts
- Interior finishes (drywall, flooring, paint, cabinets)
- HVAC equipment & controls
- Plumbing fixtures, pipes & fittings
- Electrical supplies, lighting & panels
- Low-voltage, AV & security equipment
- Fire protection equipment (sprinklers, alarms, suppression)
- Sitework & utility materials (pipe, drainage, erosion control)
- Landscaping, irrigation & outdoor supplies
- Solar, batteries & EV charging equipment
- Accessibility & conveyance equipment
- Environmental & hazmat supplies

Supplier Subcategories (full table)
Below are the recommended subcategories (product types) grouped by primary category. Use these as the canonical subcategory list in UI autocomplete or multi-select.

- Waste, hauling & sanitation:
  - Dumpsters
  - Roll-off bins
  - Portable toilets
  - Recycling services
  - Debris removal

- Fencing, scaffolding & temporary structures:
  - Temporary fencing
  - Barricades
  - Scaffolding systems
  - Shoring
  - Safety netting

- Concrete, rebar & structural materials:
  - Ready-mix concrete
  - Rebar
  - Post-tension cables
  - Structural steel
  - Concrete blocks

- Lumber, framing & sheathing:
  - Dimensional lumber
  - LVL / engineered wood
  - Plywood
  - OSB
  - Trusses

- Roofing, waterproofing & insulation:
  - Roofing materials
  - Membranes
  - Underlayment
  - Insulation
  - Sealants
  - Flashing

- Windows, doors & storefronts:
  - Windows
  - Glass systems
  - Storefront framing
  - Doors
  - Frames
  - Hardware

- Interior finishes (drywall, flooring, paint, cabinets):
  - Drywall sheets
  - Joint compound
  - Ceiling tiles
  - Flooring (tile, carpet, vinyl)
  - Paint
  - Cabinets

- HVAC equipment & controls:
  - Package units
  - Split systems
  - VRF systems
  - Thermostats
  - Controls
  - Ducting
  - Fans

- Plumbing fixtures, pipes & fittings:
  - Pipes (PVC, PEX, Copper)
  - Valves
  - Fittings
  - Water heaters
  - Fixtures (sinks, toilets)

- Electrical supplies, lighting & panels:
  - Panels
  - Breakers
  - Wiring
  - Conduits
  - Lighting fixtures
  - Switchgear

- Low-voltage, AV & security equipment:
  - CAT cables
  - Cameras
  - Access control
  - Speakers
  - AV systems

- Fire protection equipment:
  - Sprinkler heads
  - Alarms
  - Fire pump equipment
  - Suppression chemicals

- Sitework & utility materials:
  - Pipe (storm, sanitary)
  - Drainage systems
  - Erosion control
  - Aggregate

- Landscaping, irrigation & outdoor supplies:
  - Plants & sod
  - Irrigation systems
  - Landscape stone
  - Outdoor site furnishings

- Solar, batteries & EV charging equipment:
  - Solar panels
  - Inverters
  - Batteries
  - EV chargers

- Accessibility & conveyance equipment:
  - Elevators
  - Lifts
  - Ramps
  - Handrails

- Environmental & hazmat supplies:
  - Spill kits
  - Containment
  - PPE
  - Hazardous waste disposal

Example JSON requests
- Example A — Concrete supplier (primary category and subcategories):
```json
{
  "product_categories": "Concrete, rebar & structural materials",
  "product_types": ["Ready-mix concrete", "Rebar", "Concrete blocks"]
}
```

- Example B — Electrical supplier:
```json
{
  "product_categories": "Electrical supplies, lighting & panels",
  "product_types": ["Panels", "Breakers", "Lighting fixtures"]
}
```

- Example C — Landscaping supplier:
```json
{
  "product_categories": "Landscaping, irrigation & outdoor supplies",
  "product_types": ["Irrigation systems", "Landscape stone", "Plants & sod"]
}
```

API integration notes
- Validate incoming payloads against `SupplierStep4` (Pydantic). On success, persist values into `SupplierProfile.product_categories` and `SupplierProfile.product_types`.
- Use `SupplierStepResponse` as the standard step response model: `message`, `step_completed`, `total_steps`, `is_completed`, `next_step`.

Storage recommendations
- Store `product_types` as an array or JSON column (`jsonb` recommended for PostgreSQL) to preserve order and allow indexing/filtering.
- Store `product_categories` as text but keep values limited to the 17 canonical options to simplify querying. If you need richer category queries or relationships, normalize categories and subcategories into dedicated tables with foreign keys.

UI recommendations
- Provide a required dropdown for the primary `product_categories` (use the 17 items above).
- Provide a searchable multi-select or autocomplete for `product_types` populated from the subcategory lists above.
- Enforce the 20-item max in the UI and show friendly validation messages.

Migration notes
- If existing supplier data contains free-text categories, consider a one-time mapping script to map legacy strings into the new 17-category canonical list before enforcing the dropdown.

Appendix: Machine-friendly list (copy/paste)
- Primary categories array:
```
["Waste, hauling & sanitation",
 "Fencing, scaffolding & temporary structures",
 "Concrete, rebar & structural materials",
 "Lumber, framing & sheathing",
 "Roofing, waterproofing & insulation",
 "Windows, doors & storefronts",
 "Interior finishes (drywall, flooring, paint, cabinets)",
 "HVAC equipment & controls",
 "Plumbing fixtures, pipes & fittings",
 "Electrical supplies, lighting & panels",
 "Low-voltage, AV & security equipment",
 "Fire protection equipment (sprinklers, alarms, suppression)",
 "Sitework & utility materials (pipe, drainage, erosion control)",
 "Landscaping, irrigation & outdoor supplies",
 "Solar, batteries & EV charging equipment",
 "Accessibility & conveyance equipment",
 "Environmental & hazmat supplies"]
```

---
This document expands the Step 4 guidance and provides the canonical 17 primary categories plus recommended subcategories for UI and backend integration.

