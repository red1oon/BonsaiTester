#!/usr/bin/env python3
"""
Placement Validator - BonsaiTester
===================================

Validates MEP element placement against engineering standards.

Modular, template-based validation system where:
- Each discipline has its own engineering standards
- GUI-selectable validators (validate specific disciplines)
- 8_IFC database cross-check for sanity verification
- Detects clustering, coverage gaps, and code violations

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import sqlite3
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class PlacementIssue:
    """Represents a placement validation issue"""
    issue_type: str  # 'clustering', 'gap', 'code_violation', 'outlier'
    discipline: str  # 'FP', 'ELEC', 'HVAC', 'PLB'
    severity: str  # 'CRITICAL', 'WARNING', 'INFO'
    code_reference: str  # e.g., 'NFPA13_8.6.2.2.1'
    description: str
    affected_elements: List[str]  # List of GUIDs
    location: Tuple[float, float, float]  # GPS coordinates
    measured_value: float
    expected_value: float
    unit: str


@dataclass
class ValidationResult:
    """Results from placement validation"""
    discipline: str
    total_elements: int
    validated_elements: int
    issues: List[PlacementIssue]
    passed: int
    failed: int
    warnings: int

    def get_pass_rate(self) -> float:
        """Calculate pass rate percentage"""
        if self.validated_elements == 0:
            return 0.0
        return (self.passed / self.validated_elements) * 100.0


class PlacementValidator:
    """
    Modular placement validator for MEP elements.

    Validates against engineering standards with optional 8_IFC cross-check.
    """

    def __init__(self, database_path: Path, template_path: Optional[Path] = None,
                 reference_db_path: Optional[Path] = None):
        """
        Initialize placement validator.

        Args:
            database_path: Path to database to validate (e.g., 2Dto3D)
            template_path: Path to engineering standards template JSON
            reference_db_path: Optional path to 8_IFC reference database
        """
        self.database_path = Path(database_path)
        self.reference_db_path = Path(reference_db_path) if reference_db_path else None

        # Load engineering standards template
        if template_path is None:
            # Default to 2Dto3D template location
            template_path = Path(__file__).parent.parent.parent.parent / \
                           "2Dto3D" / "Templates" / "master_template_schema.json"

        self.template_path = Path(template_path)
        self.standards = self._load_standards()

        # Available validators
        self.available_disciplines = ['FP', 'ELEC', 'HVAC', 'PLB']

    def _load_standards(self) -> Dict:
        """Load engineering standards from template JSON"""
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        with open(self.template_path, 'r') as f:
            return json.load(f)

    def validate_discipline(self, discipline: str, verbose: bool = False) -> ValidationResult:
        """
        Validate placement for a specific discipline.

        Args:
            discipline: Discipline code ('FP', 'ELEC', 'HVAC', 'PLB')
            verbose: Print detailed progress

        Returns:
            ValidationResult with issues found
        """
        if discipline not in self.available_disciplines:
            raise ValueError(f"Unknown discipline: {discipline}")

        if verbose:
            print(f"\n{'=' * 70}")
            print(f"VALIDATING {discipline} PLACEMENT")
            print(f"{'=' * 70}")

        # Get elements from database
        elements = self._get_elements_by_discipline(discipline)

        if verbose:
            print(f"Found {len(elements)} {discipline} elements")

        # Run discipline-specific validation
        if discipline == 'FP':
            issues = self._validate_fire_protection(elements, verbose)
        elif discipline == 'ELEC':
            issues = self._validate_electrical(elements, verbose)
        elif discipline == 'HVAC':
            issues = self._validate_hvac(elements, verbose)
        elif discipline == 'PLB':
            issues = self._validate_plumbing(elements, verbose)
        else:
            issues = []

        # Optional: Cross-check against 8_IFC reference
        if self.reference_db_path and self.reference_db_path.exists():
            if verbose:
                print(f"Cross-checking against reference database...")
            reference_issues = self._cross_check_with_reference(discipline, elements, verbose)
            issues.extend(reference_issues)

        # Calculate statistics
        critical_count = sum(1 for i in issues if i.severity == 'CRITICAL')
        warning_count = sum(1 for i in issues if i.severity == 'WARNING')
        passed = len(elements) - critical_count

        return ValidationResult(
            discipline=discipline,
            total_elements=len(elements),
            validated_elements=len(elements),
            issues=issues,
            passed=passed,
            failed=critical_count,
            warnings=warning_count
        )

    def _get_elements_by_discipline(self, discipline: str) -> List[Dict]:
        """
        Extract elements from database for a specific discipline.

        Returns:
            List of element dicts with {guid, ifc_class, x, y, z, discipline}
        """
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query elements with coordinates
        query = """
            SELECT
                em.guid,
                em.ifc_class,
                em.discipline,
                et.x,
                et.y,
                et.z
            FROM elements_meta em
            JOIN element_transforms et ON em.guid = et.guid
            WHERE em.discipline = ?
            ORDER BY et.x, et.y
        """

        cursor.execute(query, (discipline,))
        rows = cursor.fetchall()
        conn.close()

        elements = []
        for row in rows:
            elements.append({
                'guid': row['guid'],
                'ifc_class': row['ifc_class'],
                'discipline': row['discipline'],
                'x': row['x'],
                'y': row['y'],
                'z': row['z']
            })

        return elements

    def _validate_fire_protection(self, elements: List[Dict], verbose: bool) -> List[PlacementIssue]:
        """
        Validate fire protection elements against NFPA 13.

        Checks:
        - Maximum spacing between sprinklers (4.572m / 15ft)
        - Minimum spacing between sprinklers (1.83m / 6ft)
        - Coverage gaps (areas without protection)
        """
        issues = []

        # Get NFPA 13 standards from template
        fp_standards = self.standards.get('fire_protection', {})
        code_compliance = fp_standards.get('code_compliance', {})

        max_spacing_rule = code_compliance.get('NFPA13_8.6.2.2.1', {})
        min_spacing_rule = code_compliance.get('NFPA13_8.2.3', {})

        max_spacing_m = max_spacing_rule.get('max_spacing_m', 4.572)
        min_spacing_m = min_spacing_rule.get('min_spacing_m', 1.83)

        if verbose:
            print(f"  Checking spacing: min={min_spacing_m}m, max={max_spacing_m}m")

        # Check pairwise spacing
        for i, elem1 in enumerate(elements):
            for j, elem2 in enumerate(elements[i+1:], start=i+1):
                distance = self._calculate_distance_2d(elem1, elem2)

                # Too close (clustering)
                if distance < min_spacing_m:
                    issues.append(PlacementIssue(
                        issue_type='clustering',
                        discipline='FP',
                        severity='WARNING',
                        code_reference='NFPA13_8.2.3',
                        description=f"Sprinklers too close ({distance:.2f}m < {min_spacing_m}m minimum)",
                        affected_elements=[elem1['guid'], elem2['guid']],
                        location=(elem1['x'], elem1['y'], elem1['z']),
                        measured_value=distance,
                        expected_value=min_spacing_m,
                        unit='meters'
                    ))

                # Too far (coverage gap)
                elif distance > max_spacing_m:
                    issues.append(PlacementIssue(
                        issue_type='gap',
                        discipline='FP',
                        severity='CRITICAL',
                        code_reference='NFPA13_8.6.2.2.1',
                        description=f"Sprinklers too far apart ({distance:.2f}m > {max_spacing_m}m maximum)",
                        affected_elements=[elem1['guid'], elem2['guid']],
                        location=((elem1['x'] + elem2['x']) / 2, (elem1['y'] + elem2['y']) / 2, elem1['z']),
                        measured_value=distance,
                        expected_value=max_spacing_m,
                        unit='meters'
                    ))

        if verbose:
            print(f"  Found {len(issues)} spacing issues")

        return issues

    def _validate_electrical(self, elements: List[Dict], verbose: bool) -> List[PlacementIssue]:
        """
        Validate electrical elements against NEC.

        Checks:
        - Light fixture spacing for adequate illumination
        - Outlet spacing compliance
        """
        issues = []

        # TODO: Implement electrical-specific validation
        if verbose:
            print(f"  Electrical validation not yet implemented")

        return issues

    def _validate_hvac(self, elements: List[Dict], verbose: bool) -> List[PlacementIssue]:
        """
        Validate HVAC elements against ASHRAE 90.1.

        Checks:
        - Diffuser/grille spacing for coverage
        - Air changes per hour (ACH) compliance
        """
        issues = []

        # TODO: Implement HVAC-specific validation
        if verbose:
            print(f"  HVAC validation not yet implemented")

        return issues

    def _validate_plumbing(self, elements: List[Dict], verbose: bool) -> List[PlacementIssue]:
        """
        Validate plumbing elements against IPC/IBC.

        Checks:
        - Toilet/fixture spacing for accessibility
        - ADA compliance
        - Fixture counts per occupancy
        """
        issues = []

        # TODO: Implement plumbing-specific validation
        if verbose:
            print(f"  Plumbing validation not yet implemented")

        return issues

    def _cross_check_with_reference(self, discipline: str, elements: List[Dict],
                                     verbose: bool) -> List[PlacementIssue]:
        """
        Cross-check element placement against 8_IFC reference database.

        This is a sanity check - identifies statistical outliers compared
        to a known-good design.
        """
        issues = []

        # Get reference elements from 8_IFC
        ref_elements = self._get_reference_elements(discipline)

        if not ref_elements:
            if verbose:
                print(f"  No reference data for {discipline}")
            return issues

        # Calculate average spacing in reference
        ref_avg_spacing = self._calculate_average_spacing(ref_elements)

        # Calculate average spacing in test database
        test_avg_spacing = self._calculate_average_spacing(elements)

        # Flag if deviation is >30%
        deviation = abs(test_avg_spacing - ref_avg_spacing) / ref_avg_spacing

        if deviation > 0.3:
            issues.append(PlacementIssue(
                issue_type='outlier',
                discipline=discipline,
                severity='INFO',
                code_reference='8_IFC_REFERENCE',
                description=f"Average spacing differs from reference by {deviation*100:.1f}%",
                affected_elements=[],
                location=(0, 0, 0),
                measured_value=test_avg_spacing,
                expected_value=ref_avg_spacing,
                unit='meters'
            ))

        if verbose:
            print(f"  Reference check: {test_avg_spacing:.2f}m vs {ref_avg_spacing:.2f}m reference")

        return issues

    def _get_reference_elements(self, discipline: str) -> List[Dict]:
        """Get elements from 8_IFC reference database"""
        if not self.reference_db_path or not self.reference_db_path.exists():
            return []

        conn = sqlite3.connect(self.reference_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT
                em.guid,
                em.discipline,
                et.x,
                et.y,
                et.z
            FROM elements_meta em
            JOIN element_transforms et ON em.guid = et.guid
            WHERE em.discipline = ?
        """

        cursor.execute(query, (discipline,))
        rows = cursor.fetchall()
        conn.close()

        return [{'x': r['x'], 'y': r['y'], 'z': r['z']} for r in rows]

    def _calculate_average_spacing(self, elements: List[Dict]) -> float:
        """Calculate average distance to nearest neighbor"""
        if len(elements) < 2:
            return 0.0

        total_distance = 0.0
        count = 0

        for i, elem1 in enumerate(elements):
            # Find nearest neighbor
            min_dist = float('inf')
            for j, elem2 in enumerate(elements):
                if i != j:
                    dist = self._calculate_distance_2d(elem1, elem2)
                    min_dist = min(min_dist, dist)

            if min_dist != float('inf'):
                total_distance += min_dist
                count += 1

        return total_distance / count if count > 0 else 0.0

    def _calculate_distance_2d(self, elem1: Dict, elem2: Dict) -> float:
        """Calculate 2D distance between two elements (ignoring Z)"""
        dx = elem1['x'] - elem2['x']
        dy = elem1['y'] - elem2['y']
        return math.sqrt(dx**2 + dy**2)

    def validate_all(self, disciplines: Optional[List[str]] = None,
                     verbose: bool = False) -> Dict[str, ValidationResult]:
        """
        Validate multiple disciplines.

        Args:
            disciplines: List of discipline codes to validate (default: all)
            verbose: Print detailed progress

        Returns:
            Dict mapping discipline code to ValidationResult
        """
        if disciplines is None:
            disciplines = self.available_disciplines

        results = {}

        for discipline in disciplines:
            if verbose:
                print(f"\n{'=' * 70}")
                print(f"VALIDATING DISCIPLINE: {discipline}")
                print(f"{'=' * 70}")

            results[discipline] = self.validate_discipline(discipline, verbose)

        return results

    def generate_report(self, results: Dict[str, ValidationResult],
                       output_path: Optional[Path] = None) -> str:
        """
        Generate placement validation report.

        Args:
            results: Dict of ValidationResults by discipline
            output_path: Optional path to save report

        Returns:
            Report text
        """
        lines = []
        lines.append("=" * 70)
        lines.append("PLACEMENT VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append(f"Database: {self.database_path.name}")
        lines.append(f"Template: {self.template_path.name}")
        if self.reference_db_path:
            lines.append(f"Reference: {self.reference_db_path.name}")
        lines.append("=" * 70)

        for discipline, result in results.items():
            lines.append(f"\n{discipline} - {self._get_discipline_name(discipline)}")
            lines.append("-" * 70)
            lines.append(f"  Total elements: {result.total_elements}")
            lines.append(f"  Validated: {result.validated_elements}")
            lines.append(f"  ✓ Passed: {result.passed}")
            lines.append(f"  ✗ Failed: {result.failed}")
            lines.append(f"  ⚠ Warnings: {result.warnings}")
            lines.append(f"  Pass rate: {result.get_pass_rate():.1f}%")

            if result.issues:
                lines.append(f"\n  Issues found ({len(result.issues)}):")

                # Group by type
                by_type = defaultdict(list)
                for issue in result.issues:
                    by_type[issue.issue_type].append(issue)

                for issue_type, issue_list in by_type.items():
                    lines.append(f"\n  {issue_type.upper()} ({len(issue_list)}):")
                    for issue in issue_list[:5]:  # Show first 5
                        lines.append(f"    • {issue.description}")
                        lines.append(f"      Code: {issue.code_reference}")
                        lines.append(f"      Location: ({issue.location[0]:.1f}, {issue.location[1]:.1f}, {issue.location[2]:.1f})")

                    if len(issue_list) > 5:
                        lines.append(f"    ... and {len(issue_list) - 5} more")

        lines.append("\n" + "=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        report_text = "\n".join(lines)

        # Save to file if requested
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(report_text)

        return report_text

    def _get_discipline_name(self, code: str) -> str:
        """Get full discipline name from code"""
        names = {
            'FP': 'Fire Protection',
            'ELEC': 'Electrical',
            'HVAC': 'HVAC',
            'PLB': 'Plumbing'
        }
        return names.get(code, code)


# ============================================================================
# STANDALONE CLI INTERFACE
# ============================================================================

def main():
    """CLI entry point for placement validation"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate MEP element placement against engineering standards'
    )

    parser.add_argument('database', type=Path,
                       help='Database to validate (e.g., Terminal1_MainBuilding_FILTERED.db)')
    parser.add_argument('--discipline', '-d', choices=['FP', 'ELEC', 'HVAC', 'PLB'],
                       help='Validate specific discipline only')
    parser.add_argument('--reference', '-r', type=Path,
                       help='Reference database for cross-check (e.g., enhanced_federation.db)')
    parser.add_argument('--template', '-t', type=Path,
                       help='Custom template JSON path')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output report path')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    # Initialize validator
    validator = PlacementValidator(
        args.database,
        template_path=args.template,
        reference_db_path=args.reference
    )

    # Run validation
    if args.discipline:
        results = {args.discipline: validator.validate_discipline(args.discipline, args.verbose)}
    else:
        results = validator.validate_all(verbose=args.verbose)

    # Generate report
    report = validator.generate_report(results, args.output)
    print(report)

    # Exit with status
    total_failed = sum(r.failed for r in results.values())
    return 0 if total_failed == 0 else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
