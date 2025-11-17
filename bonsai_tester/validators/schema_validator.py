#!/usr/bin/env python3
"""
Tier 1 Schema Validator - BonsaiTester
=======================================

Fast database schema validation without geometry parsing.
Checks table existence, element counts, metadata integrity.

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SchemaCheckResult:
    """Result of a schema validation check"""
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict] = None


class SchemaValidator:
    """Validates database schema and structure"""

    # Expected tables for different schema types
    FEDERATION_TABLES = [
        'base_geometries',
        'elements_meta',
        'element_transforms',
        'elements_rtree',
        'coordinate_metadata',
        'global_offset'
    ]

    FEDERATION_VIEWS = [
        'element_geometry'
    ]

    def __init__(self, db_path: Path):
        """
        Initialize schema validator.

        Args:
            db_path: Path to database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.schema_type = self._detect_schema_type()

    def _detect_schema_type(self) -> str:
        """
        Detect database schema type.

        Returns:
            Schema type: 'federation', '2dto3d', or 'unknown'
        """
        # Check for element_geometry view (Federation)
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name='element_geometry'"
        )
        if self.cursor.fetchone():
            return 'federation'

        # Check for base_geometries table with guid column (2D-to-3D)
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='base_geometries'"
        )
        if self.cursor.fetchone():
            return '2dto3d'

        return 'unknown'

    def validate_all(self, verbose: bool = False) -> Dict:
        """
        Run all schema validation checks.

        Args:
            verbose: Print detailed progress

        Returns:
            Dictionary with validation results
        """
        results = {
            'schema_type': self.schema_type,
            'checks': [],
            'passed': 0,
            'failed': 0,
            'warnings': []
        }

        # Run checks based on schema type
        if self.schema_type == 'federation':
            checks = self._validate_federation_schema(verbose)
        elif self.schema_type == '2dto3d':
            checks = self._validate_2dto3d_schema(verbose)
        else:
            checks = [SchemaCheckResult(
                check_name='Schema Detection',
                passed=False,
                message='Unknown schema type - unable to validate'
            )]

        # Count passed/failed
        for check in checks:
            results['checks'].append({
                'name': check.check_name,
                'passed': check.passed,
                'message': check.message,
                'details': check.details
            })

            if check.passed:
                results['passed'] += 1
            else:
                results['failed'] += 1

            if verbose:
                status = "✓" if check.passed else "✗"
                print(f"  {status} {check.check_name}: {check.message}")

        return results

    def _validate_federation_schema(self, verbose: bool) -> List[SchemaCheckResult]:
        """Validate federation database schema"""
        checks = []

        # Check 1: Required tables exist
        missing_tables = []
        for table in self.FEDERATION_TABLES:
            self.cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not self.cursor.fetchone():
                missing_tables.append(table)

        if missing_tables:
            checks.append(SchemaCheckResult(
                check_name='Required Tables',
                passed=False,
                message=f'Missing tables: {", ".join(missing_tables)}',
                details={'missing': missing_tables}
            ))
        else:
            checks.append(SchemaCheckResult(
                check_name='Required Tables',
                passed=True,
                message=f'All {len(self.FEDERATION_TABLES)} required tables present'
            ))

        # Check 2: Required views exist
        missing_views = []
        for view in self.FEDERATION_VIEWS:
            self.cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='view' AND name=?",
                (view,)
            )
            if not self.cursor.fetchone():
                missing_views.append(view)

        if missing_views:
            checks.append(SchemaCheckResult(
                check_name='Required Views',
                passed=False,
                message=f'Missing views: {", ".join(missing_views)}',
                details={'missing': missing_views}
            ))
        else:
            checks.append(SchemaCheckResult(
                check_name='Required Views',
                passed=True,
                message=f'All {len(self.FEDERATION_VIEWS)} required views present'
            ))

        # Check 3: Element counts consistency
        try:
            self.cursor.execute("SELECT COUNT(*) FROM base_geometries")
            geom_count = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM elements_meta")
            meta_count = self.cursor.fetchone()[0]

            if geom_count == meta_count:
                checks.append(SchemaCheckResult(
                    check_name='Element Count Consistency',
                    passed=True,
                    message=f'Geometry and metadata counts match: {geom_count:,}',
                    details={'geometry_count': geom_count, 'metadata_count': meta_count}
                ))
            else:
                checks.append(SchemaCheckResult(
                    check_name='Element Count Consistency',
                    passed=False,
                    message=f'Count mismatch: {geom_count:,} geometries vs {meta_count:,} metadata',
                    details={'geometry_count': geom_count, 'metadata_count': meta_count}
                ))
        except sqlite3.Error as e:
            checks.append(SchemaCheckResult(
                check_name='Element Count Consistency',
                passed=False,
                message=f'Query failed: {e}'
            ))

        # Check 4: Discipline distribution
        try:
            self.cursor.execute("""
                SELECT discipline, COUNT(*) as count
                FROM elements_meta
                GROUP BY discipline
                ORDER BY count DESC
            """)
            disciplines = self.cursor.fetchall()

            if len(disciplines) > 0:
                disc_summary = ', '.join([f"{d[0]}:{d[1]}" for d in disciplines[:5]])
                checks.append(SchemaCheckResult(
                    check_name='Discipline Distribution',
                    passed=True,
                    message=f'{len(disciplines)} disciplines found: {disc_summary}',
                    details={'disciplines': {d[0]: d[1] for d in disciplines}}
                ))
            else:
                checks.append(SchemaCheckResult(
                    check_name='Discipline Distribution',
                    passed=False,
                    message='No disciplines found in elements_meta'
                ))
        except sqlite3.Error as e:
            checks.append(SchemaCheckResult(
                check_name='Discipline Distribution',
                passed=False,
                message=f'Query failed: {e}'
            ))

        # Check 5: Coordinate metadata
        try:
            self.cursor.execute("SELECT COUNT(*) FROM global_offset")
            offset_count = self.cursor.fetchone()[0]

            if offset_count == 1:
                self.cursor.execute("SELECT offset_x, offset_y, offset_z FROM global_offset")
                offset = self.cursor.fetchone()
                checks.append(SchemaCheckResult(
                    check_name='Coordinate Offset',
                    passed=True,
                    message=f'Global offset set: ({offset[0]:.3f}, {offset[1]:.3f}, {offset[2]:.3f})',
                    details={'offset_x': offset[0], 'offset_y': offset[1], 'offset_z': offset[2]}
                ))
            elif offset_count == 0:
                checks.append(SchemaCheckResult(
                    check_name='Coordinate Offset',
                    passed=False,
                    message='No global offset defined'
                ))
            else:
                checks.append(SchemaCheckResult(
                    check_name='Coordinate Offset',
                    passed=False,
                    message=f'Multiple offsets found: {offset_count}'
                ))
        except sqlite3.Error:
            # global_offset table may not exist in older schemas
            checks.append(SchemaCheckResult(
                check_name='Coordinate Offset',
                passed=True,
                message='global_offset table not present (OK for some schemas)'
            ))

        return checks

    def _validate_2dto3d_schema(self, verbose: bool) -> List[SchemaCheckResult]:
        """Validate 2D-to-3D conversion database schema"""
        checks = []

        # Check 1: Core tables exist
        core_tables = ['base_geometries', 'elements_meta', 'element_transforms']
        missing_tables = []

        for table in core_tables:
            self.cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not self.cursor.fetchone():
                missing_tables.append(table)

        if missing_tables:
            checks.append(SchemaCheckResult(
                check_name='Core Tables',
                passed=False,
                message=f'Missing tables: {", ".join(missing_tables)}'
            ))
        else:
            checks.append(SchemaCheckResult(
                check_name='Core Tables',
                passed=True,
                message=f'All {len(core_tables)} core tables present'
            ))

        # Check 2: Element counts
        try:
            self.cursor.execute("SELECT COUNT(*) FROM base_geometries")
            geom_count = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM elements_meta")
            meta_count = self.cursor.fetchone()[0]

            if geom_count == meta_count:
                checks.append(SchemaCheckResult(
                    check_name='Element Counts',
                    passed=True,
                    message=f'{geom_count:,} elements with geometry and metadata'
                ))
            else:
                checks.append(SchemaCheckResult(
                    check_name='Element Counts',
                    passed=False,
                    message=f'Mismatch: {geom_count:,} geometries, {meta_count:,} metadata'
                ))
        except sqlite3.Error as e:
            checks.append(SchemaCheckResult(
                check_name='Element Counts',
                passed=False,
                message=f'Query failed: {e}'
            ))

        # Check 3: Rotation data
        try:
            self.cursor.execute("SELECT COUNT(*) FROM element_transforms WHERE rotation_z != 0")
            rotated_count = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM element_transforms")
            total_transforms = self.cursor.fetchone()[0]

            if rotated_count > 0:
                checks.append(SchemaCheckResult(
                    check_name='Rotation Data',
                    passed=True,
                    message=f'{rotated_count:,} elements have rotation ({rotated_count/total_transforms*100:.1f}%)'
                ))
            else:
                checks.append(SchemaCheckResult(
                    check_name='Rotation Data',
                    passed=True,
                    message='No rotated elements (all rotation_z = 0)'
                ))
        except sqlite3.Error as e:
            checks.append(SchemaCheckResult(
                check_name='Rotation Data',
                passed=False,
                message=f'Query failed: {e}'
            ))

        # Check 4: Discipline coverage
        try:
            self.cursor.execute("""
                SELECT discipline, COUNT(*) as count
                FROM elements_meta
                GROUP BY discipline
                ORDER BY count DESC
            """)
            disciplines = self.cursor.fetchall()

            if len(disciplines) > 0:
                disc_list = ', '.join([f"{d[0]}:{d[1]}" for d in disciplines])
                checks.append(SchemaCheckResult(
                    check_name='Disciplines',
                    passed=True,
                    message=f'{len(disciplines)} disciplines: {disc_list}'
                ))
            else:
                checks.append(SchemaCheckResult(
                    check_name='Disciplines',
                    passed=False,
                    message='No disciplines found'
                ))
        except sqlite3.Error as e:
            checks.append(SchemaCheckResult(
                check_name='Disciplines',
                passed=False,
                message=f'Query failed: {e}'
            ))

        return checks

    def close(self):
        """Close database connection"""
        self.conn.close()


def validate_database_schema(db_path: Path, verbose: bool = False) -> Dict:
    """
    Validate database schema (Tier 1 validation).

    Args:
        db_path: Path to database
        verbose: Print detailed progress

    Returns:
        Dictionary with validation results
    """
    validator = SchemaValidator(db_path)
    results = validator.validate_all(verbose)
    validator.close()

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 schema_validator.py <database.db> [--verbose]")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    verbose = '--verbose' in sys.argv

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print("=" * 70)
    print("BONSAI SCHEMA VALIDATOR (Tier 1)")
    print("=" * 70)
    print(f"Database: {db_path}")
    print("=" * 70)

    results = validate_database_schema(db_path, verbose)

    print(f"\nSchema Type: {results['schema_type']}")
    print(f"✓ Passed: {results['passed']}")
    print(f"✗ Failed: {results['failed']}")

    if results['failed'] > 0:
        print("\nFailed checks:")
        for check in results['checks']:
            if not check['passed']:
                print(f"  ✗ {check['name']}: {check['message']}")
        sys.exit(1)
    else:
        print("\n✅ ALL SCHEMA CHECKS PASSED")
        sys.exit(0)
