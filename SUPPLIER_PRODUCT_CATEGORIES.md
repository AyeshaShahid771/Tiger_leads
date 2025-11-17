# Supplier Product Categories

## Frontend Implementation Guide

When implementing Step 5 (Product Categories), use these organized category groups:

### 1. Core Building Materials

- Masonry / Concrete / CMU / Ready-Mix / Rebar
- Drywall / Acoustical / Insulation Supply
- Window / Door / Glass Supplier
- Lumber / Framing / Millwork Supply
- Paint / Coatings / Waterproofing Supplier
- Siding / WRB / Sealants Supplier
- Fasteners / Tools / PPE Supplier
- Jobsite Rentals (Lifts / Temp Power / Temp Climate / Fencing)
- Waste / Hauling / Roll-Off Dumpsters

### 2. Roofing & Envelope

- Roofing Distributor / Coatings OEM
- Gutter / Coil Supplier
- Edge Metals / Sheet Metal
- Roof Drains / Accessories

### 3. Electrical / Mechanical / Plumbing (Supplier Only)

- Electrical Distributor
- Lighting Manufacturer / Rep
- Plumbing / HVAC Distributor
- Fire Protection Supplier
- Low-Voltage / Security Supplier

### 4. Energy / Sustainability

- PV / ESS / EVSE Distributor
- Solar Panel Supplier
- Battery / ESS Supplier
- EV Charger Supplier

### 5. Site / Exterior

- Hardscape & Landscape Supply
- Irrigation Supply
- Water / Well / Septic Supply

### 6. Specialized Equipment / Rentals

- Cranes
- Manlifts
- Temp Power
- Temp Climate
- Material Hoists
- Jobsite Trailers

## Implementation Notes

- Use checkbox multi-select UI
- Users can select multiple categories
- Store selected categories as JSON array in database
- No maximum limit on selections (unlike contractor business_types which has max 5)
