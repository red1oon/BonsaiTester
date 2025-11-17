# Engineering Design Formulas for MEP Placement
## Template-Based Programmatic Design Strategy

**Purpose:** Document the engineering formulas MEP engineers use to design systems,
implemented programmatically through templates and code.

**Building Type:** Transportation Hub (Assembly A-3 Occupancy, Light Hazard)

---

## 1. FIRE PROTECTION (NFPA 13)

### Design Strategy
Engineer's approach: Calculate coverage area needed → determine head spacing → verify compliance

### Core Formulas

#### 1.1 Coverage Area Formula
```
Area_per_head = Total_Room_Area / Number_of_Heads
Max_Coverage_Area = 130 sq ft (12.08 m²) [Light Hazard]
```

**Application:**
- Given room dimensions, calculate how many sprinkler heads needed
- Example: 1000 m² room ÷ 12.08 m²/head = 83 heads minimum

#### 1.2 Spacing Formula (Square Pattern)
```
S = sqrt(Area_per_head)
Max_S = 15 ft (4.572 m) [NFPA13_8.6.2.2.1]
```

**Application:**
- Place heads in grid pattern with spacing S
- Example: 12.08 m² coverage → S = 3.48m spacing

#### 1.3 Spacing Formula (Rectangular Pattern)
```
S × L ≤ Max_Coverage_Area
S/L ≤ 1.5 (aspect ratio limit)
Max_S = 15 ft (4.572 m)
```

**Application:**
- For rectangular rooms, adjust S and L to fit geometry
- Example: S=4m, L=3m → 12 m² coverage, ratio=1.33 ✓

#### 1.4 Wall Distance Formula
```
Distance_to_wall ≤ S/2
Max_wall_distance = 7.5 ft (2.29 m) [NFPA13_8.8.2]
```

**Application:**
- First row of heads placed at half-spacing from wall
- Ensures edge coverage

#### 1.5 Minimum Spacing
```
Min_spacing = 6 ft (1.83 m) [NFPA13_8.2.3]
```

**Application:**
- Prevents interference between spray patterns
- Guards against over-design

### Design Workflow
1. Calculate room area
2. Determine heads needed: Area / 12.08m²
3. Calculate grid spacing: S = sqrt(12.08) ≈ 3.48m
4. Adjust for walls: first row at S/2 from wall
5. Verify: min 1.83m, max 4.572m spacing

---

## 2. PLUMBING (IBC/IPC)

### Design Strategy
Engineer's approach: Calculate fixture count based on occupancy → distribute evenly → verify accessibility

### Core Formulas

#### 2.1 Fixture Count Formula (IBC Table 2902.1)
```
For Assembly (A-3):
- Water Closets (Male): 1 per 125 occupants
- Water Closets (Female): 1 per 65 occupants
- Lavatories: 1 per 200 occupants
- Drinking Fountains: 1 per 500 occupants
```

**Application:**
- Given occupancy load, calculate minimum fixtures
- Example: 1000 occupants → 8 male WC, 16 female WC, 5 lavatories

#### 2.2 Fixture Spacing Formula (ADA)
```
Accessible_stall_width = 60 inches (1.524 m) minimum
Standard_stall_width = 30 inches (0.762 m) minimum
Centerline_spacing = 30 inches (0.762 m) typical
```

**Application:**
- First stall: accessible (1.524m)
- Remaining stalls: 0.762m spacing
- Lavatory spacing: 0.762m centers

#### 2.3 Clearance Formula
```
Front_clearance = 48 inches (1.22 m) minimum [ADA]
Side_clearance = 18 inches (0.457 m) minimum
```

**Application:**
- Ensure wheelchair turning radius
- Verify door swing clearance

### Design Workflow
1. Calculate occupancy (floor area × occupancy factor)
2. Determine fixture count per IBC table
3. Layout fixtures with ADA-compliant spacing
4. Verify clearances and accessibility

---

## 3. HVAC (ASHRAE 90.1 / 62.1)

### Design Strategy
Engineer's approach: Calculate air changes per hour (ACH) needed → size ducts → determine diffuser locations

### Core Formulas

#### 3.1 Air Changes Per Hour (ACH) Formula
```
CFM_total = Room_Volume_ft³ × ACH / 60
ACH = 6-8 for assembly spaces (transportation hub)
```

**Application:**
- Calculate total airflow needed
- Example: 10,000 ft³ room × 8 ACH / 60 = 1,333 CFM

#### 3.2 Diffuser Coverage Formula
```
Area_per_diffuser = 100-150 sq ft (9.3-13.9 m²) typical
Throw_distance = Ceiling_height × 1.5
```

**Application:**
- Diffuser throw must reach opposite wall
- Example: 4m ceiling → 6m throw → diffusers every 12m

#### 3.3 Diffuser Spacing Formula
```
S = sqrt(Area_per_diffuser)
Max_S = 12 ft (3.66 m) typical for even distribution
```

**Application:**
- Grid pattern similar to sprinklers
- Adjust for supply/return balance

#### 3.4 Duct Velocity Formula
```
Velocity_fpm = CFM / Area_ft²
Max_velocity = 2000 fpm (main ducts)
Max_velocity = 1000 fpm (branches)
```

**Application:**
- Size ducts to avoid noise
- Example: 1000 CFM branch → min 1.0 ft² area

### Design Workflow
1. Calculate room volume
2. Determine ACH requirement (6-8 for assembly)
3. Calculate total CFM needed
4. Size main trunk ducts
5. Layout diffusers for coverage (every 3-4m)
6. Size branch ducts

---

## 4. ELECTRICAL (NEC)

### Design Strategy
Engineer's approach: Calculate lighting levels → determine fixture count → add outlets per code

### Core Formulas

#### 4.1 Lighting Level Formula (IES)
```
Lumens_needed = Area_ft² × Footcandles_required
Footcandles (Assembly): 30-50 fc (general), 10-20 fc (circulation)
Lumen_per_fixture = Lamp_watts × Efficacy_lm/W
```

**Application:**
- Calculate fixtures needed for illumination
- Example: 1000 ft² × 30 fc = 30,000 lumens needed

#### 4.2 Fixture Spacing Formula (IES)
```
Spacing_criterion (SC) = Max_spacing / Mounting_height
SC = 1.0-1.5 typical for uniform lighting
Max_spacing = Mounting_height × SC
```

**Application:**
- Uniform grid layout
- Example: 4m ceiling, SC=1.2 → 4.8m max spacing

#### 4.3 Outlet Spacing Formula (NEC 210.52)
```
Max_spacing = 12 ft (3.66 m) along walls
No point more than 6 ft (1.83 m) from outlet
```

**Application:**
- Wall outlets every 3.66m
- Ensures appliance access

#### 4.4 Circuit Load Formula
```
Circuit_load = Sum(Device_watts)
Max_load_per_circuit = Breaker_amps × Voltage × 0.8
```

**Application:**
- Group fixtures/outlets per circuit
- Example: 20A × 120V × 0.8 = 1,920W max

### Design Workflow
1. Calculate illumination needed (area × fc)
2. Determine fixture count (lumens/fixture_lumens)
3. Layout fixtures using spacing criterion
4. Add outlets per NEC spacing rules
5. Calculate circuit loads and panel sizing

---

## 5. SEATING/FURNITURE (IBC Egress)

### Design Strategy
Engineer's approach: Calculate occupancy → determine seating capacity → verify egress widths

### Core Formulas

#### 5.1 Occupancy Load Formula (IBC Table 1004.5)
```
Occupant_load = Floor_area_ft² / Occupant_load_factor
Assembly (unconcentrated): 15 sq ft/person
Assembly (concentrated seating): 7 sq ft/person
```

**Application:**
- Determines maximum occupancy
- Drives egress requirements

#### 5.2 Seating Spacing Formula (IBC/ADA)
```
Seat_width = 18-24 inches (0.457-0.610 m) typical
Row_spacing = 33-36 inches (0.838-0.914 m) back-to-back
Aisle_width = 36-44 inches (0.914-1.118 m) minimum
```

**Application:**
- Layout seating with accessibility
- Example: Rows of 10 seats, 0.914m row spacing

#### 5.3 Egress Width Formula (IBC)
```
Exit_width_inches = Occupant_load × 0.2 (stairs) or 0.15 (level)
Min_corridor_width = 44 inches (1.118 m)
```

**Application:**
- Calculate required exit widths
- Example: 500 occupants × 0.15 = 75 inches (1.905m) min

### Design Workflow
1. Calculate occupancy load (area / load factor)
2. Layout seating with proper spacing
3. Calculate egress widths needed
4. Verify aisle widths and travel distances

---

## 6. VALIDATOR IMPLEMENTATION STRATEGY

### Programmatic Approach

The placement validator verifies that these **formulas were applied correctly**, not just that elements are "not too close" or "too far apart".

#### Validation Questions (as an engineer would ask):

**Fire Protection:**
- Was the coverage area formula used? (12.08 m² per head)
- Is the spacing S = sqrt(coverage)?
- Are heads at S/2 from walls?
- Do all spacings fall within min/max limits?

**Plumbing:**
- Does fixture count match occupancy formula?
- Is spacing consistent with ADA standards?
- Are clearances maintained?

**HVAC:**
- Does CFM match ACH formula?
- Is diffuser spacing based on coverage area?
- Are throw distances appropriate for ceiling height?

**Electrical:**
- Do lumens match footcandle requirements?
- Is spacing based on spacing criterion?
- Are outlets within NEC spacing limits?

### Cross-Check with 8_IFC

The 8_IFC database serves as a **sanity check**:
- "Does my calculated spacing match what's in a known-good design?"
- "Is my ACH similar to the reference building?"
- Not a source of truth, but a reality check

### Report Output

The validator should report:
1. **Formula Applied**: Which engineering formula was detected
2. **Correctness**: Does placement match formula output?
3. **Deviations**: Where do placements deviate from formula?
4. **Recommendations**: Which formula should have been used?

Example output:
```
Fire Protection (FP):
✓ Coverage area formula applied: 12.08 m²/head average
✓ Spacing formula detected: S = 3.48m (matches sqrt(12.08))
✗ Wall distance formula violated: 12 heads >2.29m from walls
✓ Min/max spacing compliant: all heads within 1.83-4.572m range

Recommendation: Move 12 perimeter heads to S/2 from walls (1.74m)
```

---

## 7. TEMPLATE STRUCTURE

Engineering formulas should be embedded in templates:

```json
{
  "fire_protection": {
    "design_formulas": {
      "coverage_area": {
        "formula": "Area_per_head = Total_Area / Num_Heads",
        "max_coverage_m2": 12.08,
        "code_reference": "NFPA13_8.6.2.2.2"
      },
      "spacing_square": {
        "formula": "S = sqrt(coverage_area)",
        "max_spacing_m": 4.572,
        "code_reference": "NFPA13_8.6.2.2.1"
      },
      "wall_distance": {
        "formula": "distance_to_wall <= S/2",
        "max_distance_m": 2.29,
        "code_reference": "NFPA13_8.8.2"
      },
      "min_spacing": {
        "formula": "spacing >= min_spacing",
        "min_spacing_m": 1.83,
        "code_reference": "NFPA13_8.2.3"
      }
    }
  }
}
```

The validator **reads these formulas** and verifies they were applied correctly.

---

**END OF ENGINEERING DESIGN FORMULAS REFERENCE**
