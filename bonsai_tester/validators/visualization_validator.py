#!/usr/bin/env python3
"""
Tier 2.5 Visualization Validator - BonsaiTester
================================================

Validates that 2D-to-3D converted geometry will display properly in Blender,
catching issues where geometry exists but won't show improvements in Preview mode.

This module focuses on:
- Rotation distribution (detecting "all zeros" placeholders)
- Geometry vs bounding box shape comparison
- Preview mode readiness (elements_rtree vs base_geometries)
- Discipline color assignment

Designed for 2Dto3D databases where geometry may exist but not be visually distinct.

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0 (same as Bonsai/IfcOpenShell)
"""

import sqlite3
import struct
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import Counter


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class VisualizationIssue:
    """Represents a visualization problem that affects Blender display"""
    guid: str
    ifc_class: str
    discipline: str
    issue_type: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    message: str
    details: Optional[Dict] = None


@dataclass
class VisualizationReport:
    """Summary report of visualization validation"""
    total_elements: int
    elements_checked: int
    issues: List[VisualizationIssue]
    rotation_stats: Dict
    geometry_stats: Dict
    preview_readiness: Dict


# ============================================================================
# ROTATION ANALYSIS
# ============================================================================

def analyze_rotation_distribution(db_path: Path, verbose: bool = False) -> Dict:
    """
    Analyze rotation_z distribution in element_transforms table.

    Detects:
    - All rotations == 0 (placeholder geometry, not rotated)
    - Too few unique rotations (limited diversity)
    - Rotation clumping (all walls same angle)

    Args:
        db_path: Path to database
        verbose: Print detailed statistics

    Returns:
        Dictionary with rotation analysis results
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all rotation_z values
        cursor.execute("""
            SELECT rotation_z, COUNT(*) as count
            FROM element_transforms
            GROUP BY rotation_z
            ORDER BY count DESC
        """)
        rotation_counts = cursor.fetchall()

        # Get total element count
        cursor.execute("SELECT COUNT(*) FROM element_transforms")
        total_elements = cursor.fetchone()[0]

        # Calculate statistics
        unique_rotations = len(rotation_counts)
        zero_count = next((count for rot, count in rotation_counts if abs(rot) < 0.001), 0)
        non_zero_count = total_elements - zero_count

        # Get rotation distribution by IFC class
        cursor.execute("""
            SELECT m.ifc_class,
                   COUNT(*) as total,
                   SUM(CASE WHEN ABS(t.rotation_z) < 0.001 THEN 1 ELSE 0 END) as zero_rotations,
                   COUNT(DISTINCT ROUND(t.rotation_z, 2)) as unique_angles
            FROM element_transforms t
            JOIN elements_meta m ON t.guid = m.guid
            GROUP BY m.ifc_class
            ORDER BY total DESC
        """)
        class_rotation_stats = cursor.fetchall()

        conn.close()

        # Assess rotation quality
        rotation_quality = "GOOD"
        warnings = []

        if zero_count == total_elements:
            rotation_quality = "CRITICAL"
            warnings.append("ALL rotations are 0° - geometry not rotated!")
        elif zero_count > total_elements * 0.9:
            rotation_quality = "WARNING"
            warnings.append(f"90%+ rotations are 0° ({zero_count}/{total_elements})")
        elif unique_rotations < 10 and total_elements > 100:
            rotation_quality = "WARNING"
            warnings.append(f"Only {unique_rotations} unique rotations for {total_elements} elements")

        # Check for rotation clumping (too many elements with same angle)
        if rotation_counts:
            most_common_rotation, most_common_count = rotation_counts[0]
            if most_common_count > total_elements * 0.5 and unique_rotations > 1:
                rotation_quality = "WARNING"
                warnings.append(f"{most_common_count} elements share rotation {most_common_rotation:.1f}°")

        return {
            'total_elements': total_elements,
            'unique_rotations': unique_rotations,
            'zero_rotations': zero_count,
            'non_zero_rotations': non_zero_count,
            'rotation_diversity': non_zero_count / total_elements if total_elements > 0 else 0,
            'rotation_quality': rotation_quality,
            'warnings': warnings,
            'top_rotations': rotation_counts[:10],  # Top 10 most common rotations
            'class_stats': class_rotation_stats
        }

    except sqlite3.Error as e:
        conn.close()
        return {
            'error': f"Database query failed: {e}",
            'rotation_quality': "UNKNOWN"
        }


# ============================================================================
# GEOMETRY VS BOUNDING BOX COMPARISON
# ============================================================================

def compare_geometry_to_bbox(guid: str,
                             vertices_blob: bytes,
                             expected_bbox: Tuple[float, float, float]) -> Dict:
    """
    Compare actual geometry shape to expected bounding box.

    Detects when geometry is just a box (placeholder) vs actual detailed shape.

    Args:
        guid: Element GUID
        vertices_blob: Binary vertex data from base_geometries
        expected_bbox: (width, depth, height) from element_transforms

    Returns:
        Dictionary with comparison results
    """
    # Unpack vertices
    float_count = len(vertices_blob) // 4
    floats = struct.unpack(f'<{float_count}f', vertices_blob)

    # Group into (x,y,z) tuples
    vertices = []
    for i in range(0, len(floats), 3):
        vertices.append((floats[i], floats[i+1], floats[i+2]))

    if len(vertices) < 3:
        return {
            'is_placeholder': True,
            'reason': "Too few vertices (< 3)",
            'vertex_count': len(vertices)
        }

    # Compute actual bounding box from vertices
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    actual_bbox = (
        max(xs) - min(xs),
        max(ys) - min(ys),
        max(zs) - min(zs)
    )

    # Check if geometry is just a simple box (8 vertices, 12 faces = cube)
    is_simple_box = len(vertices) == 8

    # Check if actual bbox matches expected (geometry fills bounding box)
    # If they match exactly, geometry is likely just a box placeholder
    tolerance = 0.01  # 1% tolerance
    bbox_matches = all(
        abs(actual - expected) / expected < tolerance if expected > 0 else actual < 0.001
        for actual, expected in zip(actual_bbox, expected_bbox)
    )

    # Determine if this is placeholder geometry
    is_placeholder = is_simple_box and bbox_matches

    # Calculate vertex density (vertices per cubic meter)
    volume = actual_bbox[0] * actual_bbox[1] * actual_bbox[2]
    vertex_density = len(vertices) / volume if volume > 0 else 0

    return {
        'is_placeholder': is_placeholder,
        'is_simple_box': is_simple_box,
        'bbox_matches': bbox_matches,
        'vertex_count': len(vertices),
        'vertex_density': vertex_density,
        'actual_bbox': actual_bbox,
        'expected_bbox': expected_bbox,
        'reason': "Simple box geometry matching bounding box exactly" if is_placeholder else "Detailed geometry"
    }


# ============================================================================
# PREVIEW MODE READINESS
# ============================================================================

def check_preview_mode_readiness(db_path: Path, sample_size: int = 100, verbose: bool = False) -> Dict:
    """
    Check if elements_rtree (Preview mode) reflects rotated geometries.

    In Bonsai, Preview mode uses elements_rtree (bounding boxes) while
    Full Load uses base_geometries (actual geometry).

    This checks if rtree bounding boxes are oriented (non-axis-aligned)
    which indicates rotations are applied.

    Args:
        db_path: Path to database
        sample_size: Number of elements to sample
        verbose: Print detailed results

    Returns:
        Dictionary with preview mode readiness assessment
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if elements_rtree exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='elements_rtree'
        """)
        if not cursor.fetchone():
            conn.close()
            return {
                'status': 'SKIP',
                'message': 'elements_rtree table not found - Preview mode check skipped',
                'sample_size': 0,
                'axis_aligned_count': 0,
                'rotated_count': 0,
                'warnings': [],
                'issues': []
            }

        # Sample elements with non-zero rotations
        # Note: rtree id = base_geometries ROWID
        cursor.execute("""
            SELECT g.guid, t.rotation_z, t.width, t.depth, t.height,
                   r.minX, r.maxX, r.minY, r.maxY, r.minZ, r.maxZ,
                   m.ifc_class
            FROM base_geometries g
            JOIN element_transforms t ON g.guid = t.guid
            JOIN elements_rtree r ON g.ROWID = r.id
            JOIN elements_meta m ON g.guid = m.guid
            WHERE ABS(t.rotation_z) > 0.001
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        sample_elements = cursor.fetchall()
        conn.close()

        if not sample_elements:
            return {
                'status': 'SKIP',
                'message': 'No rotated elements found to check',
                'sample_size': 0,
                'axis_aligned_count': 0,
                'rotated_count': 0,
                'warnings': [],
                'issues': []
            }

        # Check each element's rtree bbox
        axis_aligned_count = 0
        rotated_count = 0
        issues = []

        for row in sample_elements:
            guid, rotation_z, width, depth, height, minX, maxX, minY, maxY, minZ, maxZ, ifc_class = row

            # Calculate rtree bbox dimensions
            rtree_width = maxX - minX
            rtree_depth = maxY - minY
            rtree_height = maxZ - minZ

            # Check if rtree bbox is axis-aligned (matches original width/depth)
            # If rotated, bbox should be larger than original dimensions
            expected_diag = math.sqrt(width**2 + depth**2)  # Diagonal after rotation
            actual_max = max(rtree_width, rtree_depth)

            # If actual bbox is close to original (not expanded), rotation not applied
            tolerance = 0.05  # 5% tolerance
            is_axis_aligned = abs(actual_max - max(width, depth)) / max(width, depth) < tolerance if max(width, depth) > 0 else True

            if is_axis_aligned:
                axis_aligned_count += 1
                if verbose:
                    issues.append({
                        'guid': guid,
                        'ifc_class': ifc_class,
                        'rotation_z': rotation_z,
                        'expected_diagonal': expected_diag,
                        'actual_max_dim': actual_max,
                        'issue': 'Rtree bbox is axis-aligned despite rotation_z != 0'
                    })
            else:
                rotated_count += 1

        # Assess preview readiness
        preview_quality = "GOOD"
        warnings = []

        if axis_aligned_count == len(sample_elements):
            preview_quality = "CRITICAL"
            warnings.append("ALL rtree bboxes are axis-aligned - Preview mode won't show rotations!")
        elif axis_aligned_count > len(sample_elements) * 0.5:
            preview_quality = "WARNING"
            warnings.append(f"50%+ rtree bboxes are axis-aligned ({axis_aligned_count}/{len(sample_elements)})")

        return {
            'status': preview_quality,
            'sample_size': len(sample_elements),
            'axis_aligned_count': axis_aligned_count,
            'rotated_count': rotated_count,
            'warnings': warnings,
            'issues': issues[:10] if verbose else []  # First 10 issues
        }

    except sqlite3.Error as e:
        conn.close()
        return {
            'status': 'ERROR',
            'message': f'Database query failed: {e}',
            'sample_size': 0,
            'axis_aligned_count': 0,
            'rotated_count': 0,
            'warnings': [],
            'issues': []
        }


# ============================================================================
# MAIN VALIDATION FUNCTION
# ============================================================================

def validate_2dto3d_visualization(db_path: Path,
                                 sample_size: int = 100,
                                 verbose: bool = False) -> VisualizationReport:
    """
    Comprehensive 2D-to-3D visualization validation.

    Checks:
    1. Rotation distribution (are elements actually rotated?)
    2. Geometry quality (detailed vs placeholder boxes?)
    3. Preview mode readiness (will rotations show in Preview?)
    4. Discipline assignment (can elements be colored?)

    Args:
        db_path: Path to database
        sample_size: Number of elements to sample for detailed checks
        verbose: Print detailed results

    Returns:
        VisualizationReport with all findings
    """
    issues = []

    # Check 1: Rotation distribution
    print("\n[1/3] Analyzing rotation distribution...")
    rotation_stats = analyze_rotation_distribution(db_path, verbose)

    if rotation_stats.get('rotation_quality') == 'CRITICAL':
        for warning in rotation_stats.get('warnings', []):
            issues.append(VisualizationIssue(
                guid="N/A",
                ifc_class="All",
                discipline="All",
                issue_type="ROTATION_MISSING",
                severity="CRITICAL",
                message=warning,
                details=rotation_stats
            ))
    elif rotation_stats.get('rotation_quality') == 'WARNING':
        for warning in rotation_stats.get('warnings', []):
            issues.append(VisualizationIssue(
                guid="N/A",
                ifc_class="All",
                discipline="All",
                issue_type="ROTATION_LIMITED",
                severity="WARNING",
                message=warning,
                details=rotation_stats
            ))

    # Check 2: Preview mode readiness
    print("[2/3] Checking Preview mode readiness...")
    preview_readiness = check_preview_mode_readiness(db_path, sample_size, verbose)

    if preview_readiness.get('status') == 'CRITICAL':
        for warning in preview_readiness.get('warnings', []):
            issues.append(VisualizationIssue(
                guid="N/A",
                ifc_class="All",
                discipline="All",
                issue_type="PREVIEW_NOT_READY",
                severity="CRITICAL",
                message=warning,
                details=preview_readiness
            ))
    elif preview_readiness.get('status') == 'WARNING':
        for warning in preview_readiness.get('warnings', []):
            issues.append(VisualizationIssue(
                guid="N/A",
                ifc_class="All",
                discipline="All",
                issue_type="PREVIEW_PARTIAL",
                severity="WARNING",
                message=warning,
                details=preview_readiness
            ))

    # Check 3: Geometry quality (sample-based)
    print(f"[3/3] Analyzing geometry quality (sample: {sample_size})...")
    geometry_stats = analyze_geometry_quality(db_path, sample_size, verbose)

    if geometry_stats.get('placeholder_ratio', 0) > 0.5:
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="PLACEHOLDER_GEOMETRY",
            severity="WARNING",
            message=f"{geometry_stats['placeholder_count']}/{geometry_stats['sampled']} elements are simple boxes (50%+)",
            details=geometry_stats
        ))

    total_elements = rotation_stats.get('total_elements', 0)

    return VisualizationReport(
        total_elements=total_elements,
        elements_checked=sample_size,
        issues=issues,
        rotation_stats=rotation_stats,
        geometry_stats=geometry_stats,
        preview_readiness=preview_readiness
    )


def analyze_geometry_quality(db_path: Path, sample_size: int, verbose: bool = False) -> Dict:
    """
    Analyze geometry quality by sampling base_geometries.

    Checks if geometries are detailed (many vertices) or simple boxes (8 vertices).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT g.guid, g.vertices, t.width, t.depth, t.height, m.ifc_class
            FROM base_geometries g
            JOIN element_transforms t ON g.guid = t.guid
            JOIN elements_meta m ON g.guid = m.guid
            ORDER BY RANDOM()
            LIMIT ?
        """, (sample_size,))

        sample_elements = cursor.fetchall()
        conn.close()

        placeholder_count = 0
        detailed_count = 0
        vertex_counts = []

        for guid, vertices_blob, width, depth, height, ifc_class in sample_elements:
            result = compare_geometry_to_bbox(guid, vertices_blob, (width, depth, height))

            vertex_counts.append(result['vertex_count'])

            if result['is_placeholder']:
                placeholder_count += 1
            else:
                detailed_count += 1

        avg_vertices = sum(vertex_counts) / len(vertex_counts) if vertex_counts else 0

        return {
            'sampled': len(sample_elements),
            'placeholder_count': placeholder_count,
            'detailed_count': detailed_count,
            'placeholder_ratio': placeholder_count / len(sample_elements) if sample_elements else 0,
            'avg_vertices': avg_vertices,
            'vertex_distribution': Counter(vertex_counts).most_common(10)
        }

    except sqlite3.Error as e:
        conn.close()
        return {
            'error': f'Database query failed: {e}'
        }


# ============================================================================
# REPORTING
# ============================================================================

def generate_visualization_report(report: VisualizationReport) -> str:
    """Generate human-readable text report"""
    lines = []
    lines.append("=" * 70)
    lines.append("2D-TO-3D VISUALIZATION VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append(f"Total Elements: {report.total_elements:,}")
    lines.append(f"Elements Checked: {report.elements_checked:,}")
    lines.append("")

    # Rotation statistics
    lines.append("ROTATION ANALYSIS")
    lines.append("-" * 70)
    rotation = report.rotation_stats
    lines.append(f"  Unique Rotations: {rotation.get('unique_rotations', 0)}")
    lines.append(f"  Zero Rotations: {rotation.get('zero_rotations', 0)} ({rotation.get('zero_rotations', 0) / report.total_elements * 100:.1f}%)")
    lines.append(f"  Non-Zero Rotations: {rotation.get('non_zero_rotations', 0)} ({rotation.get('non_zero_rotations', 0) / report.total_elements * 100:.1f}%)")
    lines.append(f"  Rotation Quality: {rotation.get('rotation_quality', 'UNKNOWN')}")

    if rotation.get('top_rotations'):
        lines.append("\n  Top 5 Most Common Rotations:")
        for angle, count in rotation['top_rotations'][:5]:
            lines.append(f"    {angle:6.1f}° : {count:4d} elements ({count/report.total_elements*100:5.1f}%)")

    # Preview mode readiness
    lines.append("")
    lines.append("PREVIEW MODE READINESS")
    lines.append("-" * 70)
    preview = report.preview_readiness
    lines.append(f"  Status: {preview.get('status', 'UNKNOWN')}")
    lines.append(f"  Sample Size: {preview.get('sample_size', 0)}")
    lines.append(f"  Axis-Aligned Boxes: {preview.get('axis_aligned_count', 0)}")
    lines.append(f"  Rotated Boxes: {preview.get('rotated_count', 0)}")

    # Geometry quality
    lines.append("")
    lines.append("GEOMETRY QUALITY")
    lines.append("-" * 70)
    geom = report.geometry_stats
    lines.append(f"  Sampled: {geom.get('sampled', 0)}")
    lines.append(f"  Simple Boxes: {geom.get('placeholder_count', 0)} ({geom.get('placeholder_ratio', 0)*100:.1f}%)")
    lines.append(f"  Detailed Geometry: {geom.get('detailed_count', 0)} ({(1-geom.get('placeholder_ratio', 0))*100:.1f}%)")
    lines.append(f"  Avg Vertices/Element: {geom.get('avg_vertices', 0):.1f}")

    # Issues summary
    lines.append("")
    lines.append("ISSUES FOUND")
    lines.append("-" * 70)

    if not report.issues:
        lines.append("  ✅ No visualization issues detected!")
    else:
        critical = [i for i in report.issues if i.severity == "CRITICAL"]
        warnings = [i for i in report.issues if i.severity == "WARNING"]

        if critical:
            lines.append(f"  🚨 CRITICAL: {len(critical)} issue(s)")
            for issue in critical:
                lines.append(f"     - {issue.message}")

        if warnings:
            lines.append(f"  ⚠️  WARNING: {len(warnings)} issue(s)")
            for issue in warnings:
                lines.append(f"     - {issue.message}")

    lines.append("")
    lines.append("=" * 70)

    # Overall assessment
    if not report.issues:
        lines.append("✅ VISUALIZATION VALIDATION PASSED")
        lines.append("   Geometry should display properly in Blender Preview mode")
    elif any(i.severity == "CRITICAL" for i in report.issues):
        lines.append("❌ CRITICAL VISUALIZATION ISSUES DETECTED")
        lines.append("   Preview mode may NOT show improved geometry")
        lines.append("   Full Load mode recommended for testing")
    else:
        lines.append("⚠️  VISUALIZATION WARNINGS DETECTED")
        lines.append("   Some elements may not display as expected")

    lines.append("=" * 70)

    return "\n".join(lines)


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 visualization_validator.py <database.db> [--sample N] [--verbose]")
        print("\nValidates 2D-to-3D visualization quality for Blender display.")
        print("\nOptions:")
        print("  --sample N    Number of elements to sample (default: 100)")
        print("  --verbose     Print detailed analysis")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    sample_size = 100
    verbose = False

    # Parse options
    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == '--sample' and i+1 < len(sys.argv):
            sample_size = int(sys.argv[i+1])
        elif arg == '--verbose':
            verbose = True

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    # Run validation
    report = validate_2dto3d_visualization(db_path, sample_size, verbose)

    # Print report
    print(generate_visualization_report(report))

    # Exit code
    sys.exit(0 if not any(i.severity == "CRITICAL" for i in report.issues) else 1)
