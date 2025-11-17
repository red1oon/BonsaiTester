#!/usr/bin/env python3
"""
Modular Placement Formulas - BonsaiTester
==========================================

Composable functions for MEP placement engineering formulas.

Divides into three modular components:
1. standards(building_type, discipline) - Which codes apply
2. coverage_area(discipline, building_type) - Area covered per device
3. spacing_settings(discipline, building_type) - Min/max spacing rules

These functions can be composed programmatically for any building type.

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class StandardsResult:
    """Results from standards() function"""
    building_type: str
    discipline: str
    applicable_codes: List[str]
    occupancy_classification: str
    hazard_classification: str


@dataclass
class CoverageAreaResult:
    """Results from coverage_area() function"""
    discipline: str
    building_type: str
    coverage_area_m2: float
    coverage_area_sqft: float
    formula: str
    code_reference: str


@dataclass
class SpacingSettingsResult:
    """Results from spacing_settings() function"""
    discipline: str
    building_type: str
    min_spacing_m: float
    max_spacing_m: float
    min_spacing_ft: float
    max_spacing_ft: float
    wall_distance_max_m: float
    wall_distance_formula: str
    spacing_formula: str
    code_references: Dict[str, str]


# ============================================================================
# FUNCTION 1: STANDARDS - Which codes apply
# ============================================================================

def standards(building_type: str, discipline: str) -> StandardsResult:
    """
    Determine which engineering standards/codes apply.

    Args:
        building_type: 'transportation_hub', 'office', 'hospital', etc.
        discipline: 'FP', 'ELEC', 'HVAC', 'PLB'

    Returns:
        StandardsResult with applicable codes

    Example:
        >>> result = standards('transportation_hub', 'FP')
        >>> result.applicable_codes
        ['NFPA 13', 'IBC', 'NFPA 72']
    """

    # Building type characteristics
    building_configs = {
        'transportation_hub': {
            'occupancy': 'Assembly (A-3)',
            'hazard': 'Light Hazard',
            'notes': 'Airport, bus terminal, jetty - high occupancy, open spaces'
        },
        'office': {
            'occupancy': 'Business (B)',
            'hazard': 'Light Hazard',
            'notes': 'Commercial office building'
        },
        'hospital': {
            'occupancy': 'Institutional (I-2)',
            'hazard': 'Light Hazard',
            'notes': 'Healthcare facility with critical systems'
        },
        'residential': {
            'occupancy': 'Residential (R-2)',
            'hazard': 'Light Hazard',
            'notes': 'Multi-family residential'
        }
    }

    # Discipline-specific codes
    discipline_codes = {
        'FP': {
            'base_codes': ['NFPA 13', 'IBC'],
            'additional_codes': {
                'transportation_hub': ['NFPA 72'],  # Fire alarm systems
                'hospital': ['NFPA 99', 'NFPA 101'],  # Healthcare facilities
            }
        },
        'ELEC': {
            'base_codes': ['NEC', 'IBC'],
            'additional_codes': {
                'transportation_hub': ['NEC Article 518'],  # Assembly occupancies
                'hospital': ['NEC Article 517'],  # Healthcare facilities
            }
        },
        'HVAC': {
            'base_codes': ['ASHRAE 90.1', 'ASHRAE 62.1', 'IMC'],
            'additional_codes': {
                'transportation_hub': [],
                'hospital': ['FGI Guidelines'],  # Facility Guidelines Institute
            }
        },
        'PLB': {
            'base_codes': ['IPC', 'IBC'],
            'additional_codes': {
                'transportation_hub': [],
                'hospital': ['FGI Guidelines'],
            }
        }
    }

    # Get building config
    building_config = building_configs.get(building_type, building_configs['transportation_hub'])

    # Get applicable codes
    disc_config = discipline_codes.get(discipline, {'base_codes': [], 'additional_codes': {}})
    base_codes = disc_config['base_codes']
    additional = disc_config['additional_codes'].get(building_type, [])

    applicable_codes = base_codes + additional

    return StandardsResult(
        building_type=building_type,
        discipline=discipline,
        applicable_codes=applicable_codes,
        occupancy_classification=building_config['occupancy'],
        hazard_classification=building_config['hazard']
    )


# ============================================================================
# FUNCTION 2: COVERAGE_AREA - Area covered per device
# ============================================================================

def coverage_area(discipline: str, building_type: str) -> CoverageAreaResult:
    """
    Calculate coverage area per device (engineering formula).

    Args:
        discipline: 'FP', 'ELEC', 'HVAC', 'PLB'
        building_type: 'transportation_hub', 'office', etc.

    Returns:
        CoverageAreaResult with coverage formula

    Example:
        >>> result = coverage_area('FP', 'transportation_hub')
        >>> result.coverage_area_m2
        12.08  # Light Hazard per NFPA 13
    """

    # Fire Protection coverage areas (NFPA 13)
    if discipline == 'FP':
        # Get hazard classification
        std = standards(building_type, discipline)
        hazard = std.hazard_classification

        if hazard == 'Light Hazard':
            return CoverageAreaResult(
                discipline='FP',
                building_type=building_type,
                coverage_area_m2=12.08,
                coverage_area_sqft=130.0,
                formula='Area_per_head = Total_Area / Num_Heads (max 130 sqft)',
                code_reference='NFPA13_8.6.2.2.2'
            )
        elif hazard == 'Ordinary Hazard Group 1':
            return CoverageAreaResult(
                discipline='FP',
                building_type=building_type,
                coverage_area_m2=11.15,
                coverage_area_sqft=120.0,
                formula='Area_per_head = Total_Area / Num_Heads (max 120 sqft)',
                code_reference='NFPA13_8.6.2.2.2'
            )
        else:  # Default to Light Hazard
            return CoverageAreaResult(
                discipline='FP',
                building_type=building_type,
                coverage_area_m2=12.08,
                coverage_area_sqft=130.0,
                formula='Area_per_head = Total_Area / Num_Heads (max 130 sqft)',
                code_reference='NFPA13_8.6.2.2.2'
            )

    # HVAC coverage areas (diffusers/grilles)
    elif discipline == 'HVAC':
        return CoverageAreaResult(
            discipline='HVAC',
            building_type=building_type,
            coverage_area_m2=12.0,
            coverage_area_sqft=129.2,
            formula='Area_per_diffuser = Room_Area / (CFM_total / CFM_per_diffuser)',
            code_reference='ASHRAE Fundamentals'
        )

    # Electrical coverage areas (light fixtures)
    elif discipline == 'ELEC':
        # Lighting coverage based on spacing criterion
        # Typical SC = 1.0-1.5, mounting height ~4m for transportation hub
        # Max_spacing = mounting_height × SC = 4m × 1.2 = 4.8m
        # Coverage = (4.8m)² = 23 m²
        return CoverageAreaResult(
            discipline='ELEC',
            building_type=building_type,
            coverage_area_m2=23.0,
            coverage_area_sqft=247.6,
            formula='Area_per_fixture = (Mounting_height × SC)²',
            code_reference='IES Lighting Handbook'
        )

    # Plumbing - not area-based, but fixture count
    elif discipline == 'PLB':
        return CoverageAreaResult(
            discipline='PLB',
            building_type=building_type,
            coverage_area_m2=0.0,  # Not applicable
            coverage_area_sqft=0.0,
            formula='Fixture_count = Occupancy / Occupant_per_fixture (IBC Table 2902.1)',
            code_reference='IBC_2902.1'
        )

    else:
        # Default fallback
        return CoverageAreaResult(
            discipline=discipline,
            building_type=building_type,
            coverage_area_m2=12.0,
            coverage_area_sqft=129.2,
            formula='Default coverage area',
            code_reference='N/A'
        )


# ============================================================================
# FUNCTION 3: SPACING_SETTINGS - Min/max spacing rules
# ============================================================================

def spacing_settings(discipline: str, building_type: str) -> SpacingSettingsResult:
    """
    Get minimum and maximum spacing rules (engineering formulas).

    Args:
        discipline: 'FP', 'ELEC', 'HVAC', 'PLB'
        building_type: 'transportation_hub', 'office', etc.

    Returns:
        SpacingSettingsResult with spacing formulas

    Example:
        >>> result = spacing_settings('FP', 'transportation_hub')
        >>> result.max_spacing_m
        4.572  # 15 ft per NFPA 13
    """

    # Fire Protection spacing (NFPA 13)
    if discipline == 'FP':
        return SpacingSettingsResult(
            discipline='FP',
            building_type=building_type,
            min_spacing_m=1.83,
            max_spacing_m=4.572,
            min_spacing_ft=6.0,
            max_spacing_ft=15.0,
            wall_distance_max_m=2.29,
            wall_distance_formula='distance_to_wall <= S/2 (max 7.5 ft)',
            spacing_formula='S = sqrt(coverage_area) (max 15 ft)',
            code_references={
                'min_spacing': 'NFPA13_8.2.3',
                'max_spacing': 'NFPA13_8.6.2.2.1',
                'wall_distance': 'NFPA13_8.8.2'
            }
        )

    # HVAC spacing (diffusers/grilles)
    elif discipline == 'HVAC':
        # Typical diffuser spacing for even air distribution
        return SpacingSettingsResult(
            discipline='HVAC',
            building_type=building_type,
            min_spacing_m=2.0,
            max_spacing_m=4.0,
            min_spacing_ft=6.6,
            max_spacing_ft=13.1,
            wall_distance_max_m=2.0,
            wall_distance_formula='distance_to_wall <= throw_distance',
            spacing_formula='S = sqrt(coverage_area), throw = ceiling_height × 1.5',
            code_references={
                'spacing': 'ASHRAE Fundamentals',
                'throw': 'SMACNA HVAC Systems Duct Design'
            }
        )

    # Electrical spacing (light fixtures)
    elif discipline == 'ELEC':
        # Spacing criterion method
        # Max_spacing = mounting_height × SC
        # For 4m ceiling, SC=1.2 → 4.8m max spacing
        return SpacingSettingsResult(
            discipline='ELEC',
            building_type=building_type,
            min_spacing_m=2.0,
            max_spacing_m=4.8,
            min_spacing_ft=6.6,
            max_spacing_ft=15.7,
            wall_distance_max_m=2.4,
            wall_distance_formula='distance_to_wall <= max_spacing/2',
            spacing_formula='max_spacing = mounting_height × SC (SC=1.0-1.5)',
            code_references={
                'spacing_criterion': 'IES RP-1',
                'uniformity': 'IES Lighting Handbook'
            }
        )

    # Plumbing spacing (fixtures)
    elif discipline == 'PLB':
        # ADA and IPC spacing requirements
        return SpacingSettingsResult(
            discipline='PLB',
            building_type=building_type,
            min_spacing_m=0.762,  # 30 inches centerline
            max_spacing_m=10.0,  # Not strictly defined, but reasonable
            min_spacing_ft=2.5,
            max_spacing_ft=32.8,
            wall_distance_max_m=0.457,  # 18 inches side clearance
            wall_distance_formula='side_clearance >= 18 inches (ADA)',
            spacing_formula='centerline_spacing = 30 inches (typical)',
            code_references={
                'ADA_clearance': 'ADA 2010 Standards 604.3',
                'stall_width': 'IPC 403.1'
            }
        )

    else:
        # Default fallback
        return SpacingSettingsResult(
            discipline=discipline,
            building_type=building_type,
            min_spacing_m=2.0,
            max_spacing_m=5.0,
            min_spacing_ft=6.6,
            max_spacing_ft=16.4,
            wall_distance_max_m=2.5,
            wall_distance_formula='Default wall distance',
            spacing_formula='Default spacing',
            code_references={}
        )


# ============================================================================
# COMPOSED VALIDATION FUNCTION
# ============================================================================

def validate_placement_formulas(elements: List[Dict], discipline: str,
                                building_type: str = 'transportation_hub') -> Dict:
    """
    Validate that engineering formulas were applied correctly.

    This composes the three modular functions:
    1. standards() - Get applicable codes
    2. coverage_area() - Get coverage formula
    3. spacing_settings() - Get spacing rules

    Args:
        elements: List of element dicts with {guid, x, y, z, ...}
        discipline: 'FP', 'ELEC', 'HVAC', 'PLB'
        building_type: 'transportation_hub', 'office', etc.

    Returns:
        Dict with validation results

    Example:
        >>> elements = [{'guid': '1', 'x': 0, 'y': 0, 'z': 0}, ...]
        >>> result = validate_placement_formulas(elements, 'FP', 'transportation_hub')
        >>> result['standards']['applicable_codes']
        ['NFPA 13', 'IBC', 'NFPA 72']
    """

    # Get modular components
    std = standards(building_type, discipline)
    cov = coverage_area(discipline, building_type)
    spc = spacing_settings(discipline, building_type)

    # Calculate actual values from elements
    import math
    total_elements = len(elements)

    # Calculate average spacing (nearest neighbor)
    spacings = []
    for i, elem1 in enumerate(elements):
        min_dist = float('inf')
        for j, elem2 in enumerate(elements):
            if i != j:
                dx = elem1['x'] - elem2['x']
                dy = elem1['y'] - elem2['y']
                dist = math.sqrt(dx**2 + dy**2)
                min_dist = min(min_dist, dist)
        if min_dist != float('inf'):
            spacings.append(min_dist)

    avg_spacing = sum(spacings) / len(spacings) if spacings else 0.0
    min_actual_spacing = min(spacings) if spacings else 0.0
    max_actual_spacing = max(spacings) if spacings else 0.0

    # Check formula compliance
    spacing_compliant = (min_actual_spacing >= spc.min_spacing_m and
                        max_actual_spacing <= spc.max_spacing_m)

    # Calculate expected spacing from coverage formula
    expected_spacing = math.sqrt(cov.coverage_area_m2) if cov.coverage_area_m2 > 0 else 0.0

    # Deviation from expected
    spacing_deviation = abs(avg_spacing - expected_spacing) / expected_spacing if expected_spacing > 0 else 0.0

    return {
        'discipline': discipline,
        'building_type': building_type,
        'total_elements': total_elements,

        # Module 1: Standards
        'standards': {
            'applicable_codes': std.applicable_codes,
            'occupancy': std.occupancy_classification,
            'hazard': std.hazard_classification
        },

        # Module 2: Coverage Area
        'coverage': {
            'formula': cov.formula,
            'expected_coverage_m2': cov.coverage_area_m2,
            'code_reference': cov.code_reference
        },

        # Module 3: Spacing Settings
        'spacing': {
            'formula': spc.spacing_formula,
            'expected_spacing_m': expected_spacing,
            'min_allowed_m': spc.min_spacing_m,
            'max_allowed_m': spc.max_spacing_m,
            'wall_distance_formula': spc.wall_distance_formula,
            'wall_distance_max_m': spc.wall_distance_max_m,
            'code_references': spc.code_references
        },

        # Actual measurements
        'measured': {
            'avg_spacing_m': avg_spacing,
            'min_spacing_m': min_actual_spacing,
            'max_spacing_m': max_actual_spacing,
            'spacing_deviation_pct': spacing_deviation * 100.0
        },

        # Compliance check
        'compliance': {
            'spacing_within_limits': spacing_compliant,
            'formula_applied_correctly': spacing_deviation < 0.2,  # <20% deviation
            'pass': spacing_compliant and spacing_deviation < 0.2
        }
    }


# ============================================================================
# DEMO / TESTING
# ============================================================================

if __name__ == '__main__':
    # Demo: Show modular functions for transportation hub

    print("=" * 70)
    print("MODULAR PLACEMENT FORMULAS DEMO")
    print("Building Type: Transportation Hub (Airport/Bus/Jetty)")
    print("=" * 70)

    disciplines = ['FP', 'HVAC', 'ELEC', 'PLB']

    for disc in disciplines:
        print(f"\n{'=' * 70}")
        print(f"DISCIPLINE: {disc}")
        print(f"{'=' * 70}")

        # Module 1: Standards
        std = standards('transportation_hub', disc)
        print(f"\n1. STANDARDS:")
        print(f"   Occupancy: {std.occupancy_classification}")
        print(f"   Hazard: {std.hazard_classification}")
        print(f"   Applicable Codes: {', '.join(std.applicable_codes)}")

        # Module 2: Coverage Area
        cov = coverage_area(disc, 'transportation_hub')
        print(f"\n2. COVERAGE AREA:")
        print(f"   Formula: {cov.formula}")
        print(f"   Coverage: {cov.coverage_area_m2:.2f} m² ({cov.coverage_area_sqft:.1f} sq ft)")
        print(f"   Code: {cov.code_reference}")

        # Module 3: Spacing Settings
        spc = spacing_settings(disc, 'transportation_hub')
        print(f"\n3. SPACING SETTINGS:")
        print(f"   Formula: {spc.spacing_formula}")
        print(f"   Min Spacing: {spc.min_spacing_m:.2f}m ({spc.min_spacing_ft:.1f} ft)")
        print(f"   Max Spacing: {spc.max_spacing_m:.2f}m ({spc.max_spacing_ft:.1f} ft)")
        print(f"   Wall Distance: {spc.wall_distance_formula}")
        print(f"   Max Wall Distance: {spc.wall_distance_max_m:.2f}m")
        print(f"   Code References:")
        for key, code in spc.code_references.items():
            print(f"     - {key}: {code}")

    print("\n" + "=" * 70)
    print("END OF DEMO")
    print("=" * 70)
