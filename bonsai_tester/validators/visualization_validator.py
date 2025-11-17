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
    discipline_colors: Dict  # NEW: Discipline color validation
    parametric_shapes: Dict  # NEW: Proper shape validation
    dimension_variance: Dict  # NEW: Dimension variance validation
    material_assignments: Dict  # NEW: Material assignment validation


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
# DISCIPLINE COLOR VALIDATION
# ============================================================================

def validate_discipline_colors(db_path: Path, verbose: bool = False) -> Dict:
    """
    Validate that disciplines are properly defined for Preview mode coloring.

    Checks:
    - All elements have non-null discipline values
    - Disciplines use standard codes (ARC, STR, ELEC, etc.)
    - Discipline distribution is reasonable

    Returns:
        Dictionary with discipline color validation results
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get discipline distribution
        cursor.execute("""
            SELECT discipline, COUNT(*) as count
            FROM elements_meta
            GROUP BY discipline
            ORDER BY count DESC
        """)
        discipline_counts = cursor.fetchall()

        # Get total elements
        cursor.execute("SELECT COUNT(*) FROM elements_meta")
        total_elements = cursor.fetchone()[0]

        # Check for null/empty disciplines
        cursor.execute("""
            SELECT COUNT(*) FROM elements_meta
            WHERE discipline IS NULL OR discipline = ''
        """)
        missing_discipline = cursor.fetchone()[0]

        conn.close()

        # Standard discipline codes (from 8_IFC database)
        standard_codes = {'ARC', 'STR', 'ELEC', 'ACMV', 'FP', 'SP', 'CW', 'LPG', 'REB'}

        disciplines = {}
        non_standard_disciplines = []

        for discipline, count in discipline_counts:
            if discipline:
                disciplines[discipline] = {
                    'count': count,
                    'percentage': count / total_elements * 100,
                    'is_standard': discipline.upper() in standard_codes
                }

                if discipline.upper() not in standard_codes:
                    non_standard_disciplines.append(discipline)

        # Assess color readiness
        if missing_discipline > 0:
            status = "CRITICAL"
            message = f"{missing_discipline} elements missing discipline assignment"
        elif non_standard_disciplines:
            status = "WARNING"
            message = f"Non-standard disciplines found: {', '.join(non_standard_disciplines)}"
        else:
            status = "OK"
            message = "All elements have standard discipline codes"

        return {
            'status': status,
            'message': message,
            'total_elements': total_elements,
            'disciplines': disciplines,
            'missing_count': missing_discipline,
            'non_standard': non_standard_disciplines,
            'unique_count': len(disciplines)
        }

    except sqlite3.Error as e:
        return {
            'status': 'ERROR',
            'message': f"Database error: {e}",
            'total_elements': 0,
            'disciplines': {},
            'missing_count': 0,
            'non_standard': [],
            'unique_count': 0
        }


# ============================================================================
# MATERIAL ASSIGNMENT VALIDATION
# ============================================================================

def validate_material_assignments(db_path: Path, verbose: bool = False) -> Dict:
    """
    Validate that elements have material assignments with colors (RGBA).

    For Material mode in Blender to display colors, elements need:
    1. Material assigned in material_assignments table
    2. RGBA color values defined
    3. Materials linked to element GUIDs

    Returns:
        Dictionary with material assignment validation results
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if material_assignments table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='material_assignments'
        """)

        if not cursor.fetchone():
            return {
                'status': 'SKIP',
                'message': 'No material_assignments table found',
                'total_elements': 0,
                'elements_with_materials': 0,
                'materials': {}
            }

        # Get total elements
        cursor.execute("SELECT COUNT(*) FROM elements_meta")
        total_elements = cursor.fetchone()[0]

        # Get material assignment counts
        cursor.execute("""
            SELECT COUNT(DISTINCT guid)
            FROM material_assignments
        """)
        elements_with_materials = cursor.fetchone()[0]

        # Get material distribution
        cursor.execute("""
            SELECT
                material_name,
                rgba,
                COUNT(*) as count
            FROM material_assignments
            GROUP BY material_name
            ORDER BY count DESC
        """)
        material_data = cursor.fetchall()

        conn.close()

        # Analyze materials
        materials = {}
        materials_with_color = 0
        materials_without_color = 0

        for mat_name, rgba, count in material_data:
            has_color = rgba is not None and rgba != ''
            materials[mat_name] = {
                'count': count,
                'rgba': rgba,
                'has_color': has_color
            }
            if has_color:
                materials_with_color += count
            else:
                materials_without_color += count

        # Determine status
        coverage_ratio = elements_with_materials / total_elements if total_elements > 0 else 0

        if coverage_ratio == 0:
            status = "CRITICAL"
            message = "No elements have material assignments"
        elif coverage_ratio < 0.5:
            status = "WARNING"
            message = f"Only {coverage_ratio*100:.1f}% of elements have materials"
        elif materials_without_color > 0:
            status = "WARNING"
            message = f"{materials_without_color} elements have materials without colors"
        else:
            status = "OK"
            message = f"All {elements_with_materials} elements have materials with colors"

        return {
            'status': status,
            'message': message,
            'total_elements': total_elements,
            'elements_with_materials': elements_with_materials,
            'materials_with_color': materials_with_color,
            'materials_without_color': materials_without_color,
            'coverage_ratio': coverage_ratio,
            'unique_materials': len(materials),
            'materials': materials
        }

    except sqlite3.Error as e:
        return {
            'status': 'ERROR',
            'message': f"Database error: {e}",
            'total_elements': 0,
            'elements_with_materials': 0,
            'materials': {}
        }


# ============================================================================
# DIMENSION VARIANCE VALIDATION
# ============================================================================

def validate_dimension_variance(db_path: Path, verbose: bool = False) -> Dict:
    """
    Validate that elements use real dimensions (not all 1.0m defaults).

    This checks if the database has properly extracted dimensions from source data,
    even if geometry is simple boxes. An 8-vertex box with varying dimensions
    (0.15m, 2.5m, 7.77m) is better than all 1m cubes.

    Returns:
        Dictionary with dimension variance validation results
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if element_transforms has dimension columns
        cursor.execute("PRAGMA table_info(element_transforms)")
        columns = [row[1] for row in cursor.fetchall()]

        # Different schemas store dimensions differently
        dimension_cols = []
        if 'length' in columns:
            dimension_cols.append('length')
        if 'width' in columns:
            dimension_cols.extend(['width', 'depth', 'height'])

        if not dimension_cols:
            return {
                'status': 'SKIP',
                'message': 'No dimension columns found in element_transforms',
                'by_class': {}
            }

        # Analyze dimension variance by IFC class
        results_by_class = {}

        # Get all IFC classes
        cursor.execute("SELECT DISTINCT ifc_class FROM elements_meta")
        ifc_classes = [row[0] for row in cursor.fetchall()]

        for ifc_class in ifc_classes:
            # For each dimension column, check variance
            class_stats = {}

            for dim_col in dimension_cols:
                cursor.execute(f"""
                    SELECT
                        COUNT(*) as total,
                        COUNT(DISTINCT t.{dim_col}) as unique_values,
                        MIN(t.{dim_col}) as min_val,
                        MAX(t.{dim_col}) as max_val,
                        AVG(t.{dim_col}) as avg_val
                    FROM element_transforms t
                    JOIN elements_meta m ON t.guid = m.guid
                    WHERE m.ifc_class = ?
                """, (ifc_class,))

                row = cursor.fetchone()
                if row and row[0] > 0:
                    total, unique, min_val, max_val, avg_val = row

                    # Calculate variance ratio (unique values / total elements)
                    variance_ratio = unique / total if total > 0 else 0

                    # Check if all values are 1.0 (placeholder)
                    is_placeholder = (unique == 1 and abs(min_val - 1.0) < 0.001)

                    class_stats[dim_col] = {
                        'total': total,
                        'unique': unique,
                        'min': min_val,
                        'max': max_val,
                        'avg': avg_val,
                        'variance_ratio': variance_ratio,
                        'is_placeholder': is_placeholder
                    }

            results_by_class[ifc_class] = class_stats

        conn.close()

        # Assess overall dimension quality
        total_classes = len(results_by_class)
        placeholder_classes = 0
        good_variance_classes = 0

        for ifc_class, stats in results_by_class.items():
            if stats:
                # Check first dimension column (usually 'length')
                first_dim = list(stats.values())[0] if stats else None
                if first_dim:
                    if first_dim['is_placeholder']:
                        placeholder_classes += 1
                    elif first_dim['variance_ratio'] > 0.1:  # >10% unique values
                        good_variance_classes += 1

        # Determine status
        if placeholder_classes == total_classes:
            status = "CRITICAL"
            message = "All elements use placeholder dimensions (all 1.0m)"
        elif placeholder_classes > total_classes * 0.5:
            status = "WARNING"
            message = f"{placeholder_classes}/{total_classes} IFC classes use placeholder dimensions"
        elif good_variance_classes > total_classes * 0.5:
            status = "OK"
            message = f"Good dimension variance: {good_variance_classes}/{total_classes} classes have varied dimensions"
        else:
            status = "WARNING"
            message = "Limited dimension variance across IFC classes"

        return {
            'status': status,
            'message': message,
            'by_class': results_by_class,
            'total_classes': total_classes,
            'placeholder_classes': placeholder_classes,
            'good_variance_classes': good_variance_classes,
            'dimension_columns': dimension_cols
        }

    except sqlite3.Error as e:
        return {
            'status': 'ERROR',
            'message': f"Database error: {e}",
            'by_class': {},
            'total_classes': 0,
            'placeholder_classes': 0,
            'good_variance_classes': 0,
            'dimension_columns': []
        }


# ============================================================================
# PARAMETRIC SHAPE VALIDATION
# ============================================================================

def validate_parametric_shapes(db_path: Path, sample_size: int = 100, verbose: bool = False) -> Dict:
    """
    Validate complex parametric shapes (cylinders, detailed meshes, not just boxes).

    NOTE: This validator checks for COMPLEX GEOMETRY (vertex count >8).
    For dimension variance (properly sized boxes), use validate_dimension_variance().

    Checks for recognizable shapes:
    - Pipes/conduits: Cylindrical (12+ vertices in circular pattern)
    - Columns: Cylindrical (24-32 vertices)
    - Fittings: Complex shapes (20+ vertices)
    - Equipment: Detailed meshes (100+ vertices)

    An 8-vertex box with varying dimensions (0.15m, 7.77m) is GOOD for dimensions
    but NOT counted as "complex parametric" by this validator.

    Returns:
        Dictionary with complex shape validation results
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if base_geometries has guid column (2Dto3D schema) or geometry_hash (8_IFC schema)
        cursor.execute("PRAGMA table_info(base_geometries)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'guid' in columns:
            # 2Dto3D schema
            cursor.execute("""
                SELECT g.guid, g.vertices, g.faces, m.ifc_class, m.discipline
                FROM base_geometries g
                JOIN elements_meta m ON g.guid = m.guid
                ORDER BY RANDOM()
                LIMIT ?
            """, (sample_size,))
        else:
            # 8_IFC schema - join via element_instances
            cursor.execute("""
                SELECT m.guid, g.vertices, g.faces, m.ifc_class, m.discipline
                FROM base_geometries g
                JOIN element_instances ei ON g.geometry_hash = ei.geometry_hash
                JOIN elements_meta m ON ei.guid = m.guid
                ORDER BY RANDOM()
                LIMIT ?
            """, (sample_size,))

        sample_elements = cursor.fetchall()
        conn.close()

        parametric_elements = []
        box_elements = []

        for guid, vertices_blob, faces_blob, ifc_class, discipline in sample_elements:
            shape_info = analyze_shape_type(vertices_blob, faces_blob, ifc_class)

            if shape_info['is_parametric']:
                parametric_elements.append({
                    'guid': guid,
                    'ifc_class': ifc_class,
                    'discipline': discipline,
                    'shape_type': shape_info['shape_type'],
                    'vertex_count': shape_info['vertex_count'],
                    'confidence': shape_info['confidence']
                })
            else:
                box_elements.append(guid)

        # Assess shape quality
        parametric_count = len(parametric_elements)

        if parametric_count >= 2:
            status = "OK"
            message = f"Found {parametric_count} elements with proper parametric shapes"
        elif parametric_count == 1:
            status = "WARNING"
            message = "Only 1 element has parametric shape (need at least 2)"
        else:
            status = "CRITICAL"
            message = "No parametric shapes found - all elements are simple boxes"

        return {
            'status': status,
            'message': message,
            'parametric_count': parametric_count,
            'box_count': len(box_elements),
            'sample_size': len(sample_elements),
            'parametric_ratio': parametric_count / len(sample_elements) if sample_elements else 0,
            'parametric_elements': parametric_elements[:10],  # Top 10 for reporting
            'shape_types_found': list(set(e['shape_type'] for e in parametric_elements))
        }

    except sqlite3.Error as e:
        return {
            'status': 'ERROR',
            'message': f"Database error: {e}",
            'parametric_count': 0,
            'box_count': 0,
            'sample_size': 0,
            'parametric_ratio': 0,
            'parametric_elements': [],
            'shape_types_found': []
        }


def analyze_shape_type(vertices_blob: bytes, faces_blob: bytes, ifc_class: str) -> Dict:
    """
    Analyze geometry to determine if it's a recognizable parametric shape.

    Detection patterns:
    - Cylinder: 12+ vertices, circular cross-section
    - Box: 8 vertices, 12 faces
    - Complex: 20+ vertices (fittings, equipment)
    """
    # Decode vertices
    vertex_count = len(vertices_blob) // (3 * 4)  # 3 floats per vertex
    vertices = []

    for i in range(vertex_count):
        offset = i * 12
        x, y, z = struct.unpack('<fff', vertices_blob[offset:offset+12])
        vertices.append((x, y, z))

    # Simple classification
    shape_type = "unknown"
    is_parametric = False
    confidence = "low"

    if vertex_count == 8:
        shape_type = "box"
        is_parametric = False
        confidence = "high"
    elif 12 <= vertex_count <= 36:
        # Likely cylinder (12, 16, 24, or 32 vertices common)
        if is_cylindrical_pattern(vertices):
            shape_type = "cylinder"
            is_parametric = True
            confidence = "high"
        else:
            shape_type = "custom_12-36"
            is_parametric = True
            confidence = "medium"
    elif vertex_count > 36:
        shape_type = "complex"
        is_parametric = True
        confidence = "high"

    # Class-specific expectations
    if ifc_class in ['IfcColumn', 'IfcPipeSegment', 'IfcPipeFitting']:
        if vertex_count >= 12:
            is_parametric = True

    return {
        'vertex_count': vertex_count,
        'shape_type': shape_type,
        'is_parametric': is_parametric,
        'confidence': confidence
    }


def is_cylindrical_pattern(vertices: List[Tuple[float, float, float]]) -> bool:
    """
    Check if vertices form a cylindrical pattern (circular cross-section).
    """
    if len(vertices) < 12:
        return False

    # For simplicity, check if vertices have a circular pattern in XY plane
    # Real cylinders have vertices at same Z forming circles

    # Group by Z coordinate (within tolerance)
    z_groups = {}
    tolerance = 0.001

    for x, y, z in vertices:
        # Find matching Z group
        matched = False
        for z_key in z_groups.keys():
            if abs(z - z_key) < tolerance:
                z_groups[z_key].append((x, y))
                matched = True
                break
        if not matched:
            z_groups[z] = [(x, y)]

    # Cylinders should have at least 2 rings (top and bottom)
    if len(z_groups) < 2:
        return False

    # Check if rings have similar point counts (circular pattern)
    ring_sizes = [len(points) for points in z_groups.values()]

    # Most rings should have same point count
    if len(set(ring_sizes)) == 1 and ring_sizes[0] >= 6:
        return True

    return False


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

    # Check 1: Discipline colors
    print("\n[1/7] Validating discipline colors...")
    discipline_colors = validate_discipline_colors(db_path, verbose)

    if discipline_colors.get('status') == 'CRITICAL':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="DISCIPLINE_MISSING",
            severity="CRITICAL",
            message=discipline_colors.get('message'),
            details=discipline_colors
        ))
    elif discipline_colors.get('status') == 'WARNING':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="DISCIPLINE_NON_STANDARD",
            severity="WARNING",
            message=discipline_colors.get('message'),
            details=discipline_colors
        ))

    # Check 2: Material assignments
    print("[2/7] Validating material assignments...")
    material_assignments = validate_material_assignments(db_path, verbose)

    if material_assignments.get('status') == 'CRITICAL':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="NO_MATERIALS",
            severity="CRITICAL",
            message=material_assignments.get('message'),
            details=material_assignments
        ))
    elif material_assignments.get('status') == 'WARNING':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="INCOMPLETE_MATERIALS",
            severity="WARNING",
            message=material_assignments.get('message'),
            details=material_assignments
        ))

    # Check 3: Dimension variance (properly sized boxes)
    print("[3/7] Validating dimension variance...")
    dimension_variance = validate_dimension_variance(db_path, verbose)

    if dimension_variance.get('status') == 'CRITICAL':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="NO_DIMENSION_VARIANCE",
            severity="CRITICAL",
            message=dimension_variance.get('message'),
            details=dimension_variance
        ))
    elif dimension_variance.get('status') == 'WARNING':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="LIMITED_DIMENSION_VARIANCE",
            severity="WARNING",
            message=dimension_variance.get('message'),
            details=dimension_variance
        ))

    # Check 4: Complex parametric shapes (cylinders, detailed meshes)
    print("[4/7] Validating complex parametric shapes...")
    parametric_shapes = validate_parametric_shapes(db_path, sample_size, verbose)

    # Note: This is now informational for 2Dto3D databases (boxes are OK if dimensioned)
    if parametric_shapes.get('status') == 'CRITICAL':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="NO_COMPLEX_SHAPES",
            severity="INFO",  # Downgraded from CRITICAL
            message=parametric_shapes.get('message') + " (boxes with real dimensions are acceptable)",
            details=parametric_shapes
        ))
    elif parametric_shapes.get('status') == 'WARNING':
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="FEW_COMPLEX_SHAPES",
            severity="INFO",  # Downgraded from WARNING
            message=parametric_shapes.get('message') + " (not critical if dimensions vary)",
            details=parametric_shapes
        ))

    # Check 5: Rotation distribution
    print("[5/7] Analyzing rotation distribution...")
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

    # Check 6: Preview mode readiness
    print("[6/7] Checking Preview mode readiness...")
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

    # Check 7: Geometry quality (sample-based)
    print(f"[7/7] Analyzing geometry quality (sample: {sample_size})...")
    geometry_stats = analyze_geometry_quality(db_path, sample_size, verbose)

    # Note: Simple boxes are now OK if dimensions vary (checked in step 3)
    if geometry_stats.get('placeholder_ratio', 0) > 0.5:
        issues.append(VisualizationIssue(
            guid="N/A",
            ifc_class="All",
            discipline="All",
            issue_type="SIMPLE_BOX_GEOMETRY",
            severity="INFO",  # Downgraded from WARNING
            message=f"{geometry_stats['placeholder_count']}/{geometry_stats['sampled']} elements are simple boxes (OK if dimensions vary)",
            details=geometry_stats
        ))

    total_elements = rotation_stats.get('total_elements', 0)

    return VisualizationReport(
        total_elements=total_elements,
        elements_checked=sample_size,
        issues=issues,
        rotation_stats=rotation_stats,
        geometry_stats=geometry_stats,
        preview_readiness=preview_readiness,
        discipline_colors=discipline_colors,
        parametric_shapes=parametric_shapes,
        dimension_variance=dimension_variance,
        material_assignments=material_assignments
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

    # Discipline colors
    lines.append("DISCIPLINE COLOR VALIDATION")
    lines.append("-" * 70)
    disc = report.discipline_colors
    lines.append(f"  Status: {disc.get('status', 'UNKNOWN')}")
    lines.append(f"  Message: {disc.get('message', 'N/A')}")
    lines.append(f"  Unique Disciplines: {disc.get('unique_count', 0)}")
    lines.append(f"  Missing Disciplines: {disc.get('missing_count', 0)}")

    if disc.get('disciplines'):
        lines.append("\n  Discipline Distribution:")
        for name, info in sorted(disc['disciplines'].items(), key=lambda x: x[1]['count'], reverse=True):
            std_marker = "✓" if info['is_standard'] else "⚠"
            lines.append(f"    {std_marker} {name:20s}: {info['count']:5d} ({info['percentage']:5.1f}%)")

    # Material assignments
    lines.append("")
    lines.append("MATERIAL ASSIGNMENT VALIDATION")
    lines.append("-" * 70)
    mats = report.material_assignments
    lines.append(f"  Status: {mats.get('status', 'UNKNOWN')}")
    lines.append(f"  Message: {mats.get('message', 'N/A')}")
    lines.append(f"  Coverage: {mats.get('elements_with_materials', 0)}/{mats.get('total_elements', 0)} ({mats.get('coverage_ratio', 0)*100:.1f}%)")

    if mats.get('unique_materials', 0) > 0:
        lines.append(f"  Unique Materials: {mats['unique_materials']}")
        lines.append("\n  Material Distribution:")
        for mat_name, mat_info in list(mats.get('materials', {}).items())[:10]:
            color_marker = "✓" if mat_info['has_color'] else "✗"
            rgba_display = mat_info['rgba'] if mat_info['rgba'] else "NO COLOR"
            lines.append(f"    {color_marker} {mat_name:30s}: {mat_info['count']:4d} elements  [{rgba_display}]")

    # Dimension variance (NEW - most important for 2Dto3D!)
    lines.append("")
    lines.append("DIMENSION VARIANCE VALIDATION")
    lines.append("-" * 70)
    dims = report.dimension_variance
    lines.append(f"  Status: {dims.get('status', 'UNKNOWN')}")
    lines.append(f"  Message: {dims.get('message', 'N/A')}")

    if dims.get('dimension_columns'):
        lines.append(f"  Dimension Columns: {', '.join(dims['dimension_columns'])}")

    if dims.get('by_class'):
        lines.append(f"\n  Classes with Good Variance: {dims.get('good_variance_classes', 0)}/{dims.get('total_classes', 0)}")
        lines.append(f"  Classes with Placeholders: {dims.get('placeholder_classes', 0)}/{dims.get('total_classes', 0)}")

        lines.append("\n  Top 5 Classes by Dimension Variance:")
        # Sort by variance ratio
        sorted_classes = sorted(
            dims['by_class'].items(),
            key=lambda x: list(x[1].values())[0].get('variance_ratio', 0) if x[1] else 0,
            reverse=True
        )[:5]

        for ifc_class, stats in sorted_classes:
            if stats:
                first_dim_name = list(stats.keys())[0]
                first_dim = stats[first_dim_name]
                status_mark = "✓" if not first_dim['is_placeholder'] else "✗"
                lines.append(f"    {status_mark} {ifc_class:30s}: {first_dim['unique']:3d} unique (min:{first_dim['min']:6.2f}m, max:{first_dim['max']:6.2f}m)")

    # Complex parametric shapes (cylinders, etc.)
    lines.append("")
    lines.append("COMPLEX PARAMETRIC SHAPES (Cylinders, Detailed Meshes)")
    lines.append("-" * 70)
    shapes = report.parametric_shapes
    lines.append(f"  Status: {shapes.get('status', 'UNKNOWN')}")
    lines.append(f"  Message: {shapes.get('message', 'N/A')}")
    lines.append(f"  Complex Elements: {shapes.get('parametric_count', 0)} / {shapes.get('sample_size', 0)} ({shapes.get('parametric_ratio', 0)*100:.1f}%)")
    lines.append(f"  Simple Box Elements: {shapes.get('box_count', 0)}")
    lines.append("\n  NOTE: Simple boxes are acceptable if dimensions vary (see above)")

    if shapes.get('shape_types_found'):
        lines.append(f"\n  Complex Shape Types Found: {', '.join(shapes['shape_types_found'])}")

    if shapes.get('parametric_elements'):
        lines.append("\n  Sample Complex Elements:")
        for elem in shapes['parametric_elements'][:5]:
            lines.append(f"    - {elem['ifc_class']:25s} ({elem['discipline']:4s}): {elem['shape_type']:12s} [{elem['vertex_count']:3d} verts, {elem['confidence']:6s}]")

    # Rotation statistics
    lines.append("")
    lines.append("ROTATION ANALYSIS")
    lines.append("-" * 70)
    rotation = report.rotation_stats
    lines.append(f"  Unique Rotations: {rotation.get('unique_rotations', 0)}")
    if report.total_elements > 0:
        lines.append(f"  Zero Rotations: {rotation.get('zero_rotations', 0)} ({rotation.get('zero_rotations', 0) / report.total_elements * 100:.1f}%)")
        lines.append(f"  Non-Zero Rotations: {rotation.get('non_zero_rotations', 0)} ({rotation.get('non_zero_rotations', 0) / report.total_elements * 100:.1f}%)")
    else:
        lines.append(f"  Zero Rotations: {rotation.get('zero_rotations', 0)}")
        lines.append(f"  Non-Zero Rotations: {rotation.get('non_zero_rotations', 0)}")
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
