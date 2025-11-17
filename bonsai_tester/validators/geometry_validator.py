#!/usr/bin/env python3
"""
Tier 2 Geometry Validator - BonsaiTester
========================================

Validates 3D geometry stored in SQLite databases without requiring Blender.

This module parses binary geometry blobs (vertices, faces, normals) and performs
comprehensive validation checks:
- Blob integrity (correct sizes, alignment)
- Vertex/face counts and validity
- Bounding box dimensions
- Normal vector validation
- Mesh topology checks

Format Specification:
- Vertices: Little-endian floats, packed as <Nf (x,y,z triplets)
- Faces: Little-endian unsigned ints, packed as <NI (i1,i2,i3 triplets)
- Normals: Little-endian floats, packed as <Nf (nx,ny,nz triplets)

Compatible with IfcOpenShell geometry format used by Bonsai.

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0 (same as Bonsai/IfcOpenShell)
"""

import struct
import math
import sqlite3
from pathlib import Path
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class GeometryStats:
    """Statistics about a parsed geometry blob"""
    guid: str
    vertex_count: int
    face_count: int
    normal_count: int
    bbox_min: Tuple[float, float, float]
    bbox_max: Tuple[float, float, float]
    bbox_size: Tuple[float, float, float]
    has_degenerate_faces: bool
    normals_valid: bool
    vertices_blob_size: int
    faces_blob_size: int
    normals_blob_size: int


@dataclass
class ValidationResult:
    """Result of a validation check"""
    passed: bool
    message: str
    details: Optional[Dict] = None


# ============================================================================
# BINARY BLOB DESERIALIZATION
# ============================================================================

def unpack_vertices(blob: bytes) -> List[Tuple[float, float, float]]:
    """
    Unpack vertices from binary blob.

    Format: Little-endian floats (<f), packed as x,y,z,x,y,z,...

    Args:
        blob: Binary blob from database

    Returns:
        List of (x, y, z) vertex tuples

    Raises:
        ValueError: If blob size is not multiple of 12 bytes (3 floats)
    """
    if len(blob) % 12 != 0:
        raise ValueError(f"Vertex blob size {len(blob)} not multiple of 12 bytes (3 floats)")

    # Unpack all floats at once
    float_count = len(blob) // 4
    floats = struct.unpack(f'<{float_count}f', blob)

    # Group into (x,y,z) tuples
    vertices = []
    for i in range(0, len(floats), 3):
        vertices.append((floats[i], floats[i+1], floats[i+2]))

    return vertices


def unpack_faces(blob: bytes) -> List[Tuple[int, int, int]]:
    """
    Unpack faces from binary blob.

    Format: Little-endian unsigned ints (<I), packed as i1,i2,i3,i1,i2,i3,...

    Args:
        blob: Binary blob from database

    Returns:
        List of (i1, i2, i3) face index tuples

    Raises:
        ValueError: If blob size is not multiple of 12 bytes (3 ints)
    """
    if len(blob) % 12 != 0:
        raise ValueError(f"Face blob size {len(blob)} not multiple of 12 bytes (3 ints)")

    # Unpack all ints at once
    int_count = len(blob) // 4
    indices = struct.unpack(f'<{int_count}I', blob)

    # Group into (i1,i2,i3) tuples
    faces = []
    for i in range(0, len(indices), 3):
        faces.append((indices[i], indices[i+1], indices[i+2]))

    return faces


def unpack_normals(blob: bytes) -> List[Tuple[float, float, float]]:
    """
    Unpack normals from binary blob.

    Format: Little-endian floats (<f), packed as nx,ny,nz,nx,ny,nz,...

    Args:
        blob: Binary blob from database

    Returns:
        List of (nx, ny, nz) normal vector tuples

    Raises:
        ValueError: If blob size is not multiple of 12 bytes (3 floats)
    """
    if len(blob) % 12 != 0:
        raise ValueError(f"Normal blob size {len(blob)} not multiple of 12 bytes (3 floats)")

    # Unpack all floats at once
    float_count = len(blob) // 4
    floats = struct.unpack(f'<{float_count}f', blob)

    # Group into (nx,ny,nz) tuples
    normals = []
    for i in range(0, len(floats), 3):
        normals.append((floats[i], floats[i+1], floats[i+2]))

    return normals


# ============================================================================
# GEOMETRY VALIDATION FUNCTIONS
# ============================================================================

def compute_bounding_box(vertices: List[Tuple[float, float, float]]) -> Tuple[
    Tuple[float, float, float],  # min (x,y,z)
    Tuple[float, float, float]   # max (x,y,z)
]:
    """
    Compute axis-aligned bounding box from vertices.

    Args:
        vertices: List of (x,y,z) vertex positions

    Returns:
        Tuple of (min_point, max_point)
    """
    if not vertices:
        return ((0, 0, 0), (0, 0, 0))

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    min_point = (min(xs), min(ys), min(zs))
    max_point = (max(xs), max(ys), max(zs))

    return min_point, max_point


def validate_face_indices(faces: List[Tuple[int, int, int]],
                          vertex_count: int) -> ValidationResult:
    """
    Validate that all face indices reference valid vertices.

    Args:
        faces: List of (i1,i2,i3) face index tuples
        vertex_count: Total number of vertices

    Returns:
        ValidationResult indicating success/failure
    """
    invalid_faces = []

    for i, face in enumerate(faces):
        for idx in face:
            if idx < 0 or idx >= vertex_count:
                invalid_faces.append((i, face, idx))

    if invalid_faces:
        return ValidationResult(
            passed=False,
            message=f"Found {len(invalid_faces)} faces with invalid indices",
            details={'invalid_faces': invalid_faces[:10]}  # Limit to first 10
        )

    return ValidationResult(
        passed=True,
        message=f"All {len(faces)} faces have valid indices (0-{vertex_count-1})"
    )


def detect_degenerate_faces(vertices: List[Tuple[float, float, float]],
                           faces: List[Tuple[int, int, int]],
                           epsilon: float = 1e-6) -> ValidationResult:
    """
    Detect degenerate faces (zero area, duplicate vertices).

    Args:
        vertices: List of vertex positions
        faces: List of face indices
        epsilon: Tolerance for zero-area detection

    Returns:
        ValidationResult with degenerate face details
    """
    degenerate_faces = []

    for i, face in enumerate(faces):
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]

        # Check for duplicate vertex indices
        if face[0] == face[1] or face[1] == face[2] or face[0] == face[2]:
            degenerate_faces.append((i, 'duplicate_indices', face))
            continue

        # Check for zero-area triangle (cross product magnitude)
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        # Cross product
        cx = e1[1] * e2[2] - e1[2] * e2[1]
        cy = e1[2] * e2[0] - e1[0] * e2[2]
        cz = e1[0] * e2[1] - e1[1] * e2[0]

        area = math.sqrt(cx*cx + cy*cy + cz*cz) / 2.0

        if area < epsilon:
            degenerate_faces.append((i, 'zero_area', area))

    if degenerate_faces:
        return ValidationResult(
            passed=False,
            message=f"Found {len(degenerate_faces)} degenerate faces",
            details={'degenerate_faces': degenerate_faces[:10]}
        )

    return ValidationResult(
        passed=True,
        message=f"No degenerate faces detected in {len(faces)} faces"
    )


def validate_normals(normals: List[Tuple[float, float, float]],
                    face_count: int,
                    tolerance: float = 0.05) -> ValidationResult:
    """
    Validate that normals are unit-length and count matches faces.

    Args:
        normals: List of normal vectors
        face_count: Expected number of normals (should equal face count)
        tolerance: Tolerance for unit-length check (default 0.05 = 5%)

    Returns:
        ValidationResult with normal validation details
    """
    # Check count matches faces
    if len(normals) != face_count:
        return ValidationResult(
            passed=False,
            message=f"Normal count {len(normals)} != face count {face_count}"
        )

    # Check unit-length
    non_unit_normals = []

    for i, normal in enumerate(normals):
        length = math.sqrt(normal[0]**2 + normal[1]**2 + normal[2]**2)

        # Allow tolerance for floating point errors
        if abs(length - 1.0) > tolerance:
            non_unit_normals.append((i, normal, length))

    if non_unit_normals:
        return ValidationResult(
            passed=False,
            message=f"Found {len(non_unit_normals)} non-unit normals (tolerance: {tolerance})",
            details={'non_unit_normals': non_unit_normals[:10]}
        )

    return ValidationResult(
        passed=True,
        message=f"All {len(normals)} normals are unit-length (±{tolerance})"
    )


# ============================================================================
# HIGH-LEVEL GEOMETRY ANALYSIS
# ============================================================================

def parse_geometry(guid: str,
                   vertices_blob: bytes,
                   faces_blob: bytes,
                   normals_blob: Optional[bytes]) -> GeometryStats:
    """
    Parse geometry blobs and compute statistics.

    Args:
        guid: Element GUID
        vertices_blob: Binary vertex data
        faces_blob: Binary face data
        normals_blob: Binary normal data (optional, can be None)

    Returns:
        GeometryStats with parsed data and statistics

    Raises:
        ValueError: If blobs are malformed
    """
    # Unpack blobs
    vertices = unpack_vertices(vertices_blob)
    faces = unpack_faces(faces_blob)

    # Normals are optional in some databases
    if normals_blob and len(normals_blob) > 0:
        normals = unpack_normals(normals_blob)
    else:
        normals = []  # No normals available

    # Compute bounding box
    bbox_min, bbox_max = compute_bounding_box(vertices)
    bbox_size = (
        bbox_max[0] - bbox_min[0],
        bbox_max[1] - bbox_min[1],
        bbox_max[2] - bbox_min[2]
    )

    # Check for degenerate faces
    degenerate_result = detect_degenerate_faces(vertices, faces)
    has_degenerate = not degenerate_result.passed

    # Validate normals (if present)
    if normals:
        normals_result = validate_normals(normals, len(faces))
        normals_valid = normals_result.passed
    else:
        # No normals in database - this is OK for some schemas
        normals_valid = True

    return GeometryStats(
        guid=guid,
        vertex_count=len(vertices),
        face_count=len(faces),
        normal_count=len(normals),
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        bbox_size=bbox_size,
        has_degenerate_faces=has_degenerate,
        normals_valid=normals_valid,
        vertices_blob_size=len(vertices_blob),
        faces_blob_size=len(faces_blob),
        normals_blob_size=len(normals_blob) if normals_blob else 0
    )


def validate_geometry_blob(guid: str,
                           vertices_blob: bytes,
                           faces_blob: bytes,
                           normals_blob: Optional[bytes],
                           expected_bbox: Optional[Tuple[float, float, float]] = None,
                           ifc_class: Optional[str] = None,
                           verbose: bool = False) -> List[ValidationResult]:
    """
    Comprehensive validation of a single geometry blob.

    Args:
        guid: Element GUID
        vertices_blob: Binary vertex data
        faces_blob: Binary face data
        normals_blob: Binary normal data
        expected_bbox: Optional (width, depth, height) for dimension validation
        ifc_class: Optional IFC class name for class-specific validation
        verbose: If True, include detailed validation results

    Returns:
        List of ValidationResult objects
    """
    results = []

    try:
        # Parse geometry
        stats = parse_geometry(guid, vertices_blob, faces_blob, normals_blob)

        # Validation 1: Blob sizes
        results.append(ValidationResult(
            passed=True,
            message=f"Blobs parsed: {stats.vertex_count} verts, {stats.face_count} faces, {stats.normal_count} normals"
        ))

        # Validation 2: Vertex count > 0
        if stats.vertex_count == 0:
            results.append(ValidationResult(
                passed=False,
                message="Empty geometry (0 vertices)"
            ))
        else:
            results.append(ValidationResult(
                passed=True,
                message=f"Vertex count valid: {stats.vertex_count}"
            ))

        # Validation 3: Face indices
        vertices = unpack_vertices(vertices_blob)
        faces = unpack_faces(faces_blob)
        face_result = validate_face_indices(faces, stats.vertex_count)
        results.append(face_result)

        # Validation 4: Degenerate faces
        if not stats.has_degenerate_faces:
            results.append(ValidationResult(
                passed=True,
                message="No degenerate faces detected"
            ))
        else:
            results.append(ValidationResult(
                passed=False,
                message="Degenerate faces detected"
            ))

        # Validation 5: Normals (optional)
        if stats.normal_count > 0:
            if stats.normals_valid:
                results.append(ValidationResult(
                    passed=True,
                    message=f"Normals valid: {stats.normal_count} unit-length vectors"
                ))
            else:
                results.append(ValidationResult(
                    passed=False,
                    message="Normal validation failed"
                ))
        else:
            # No normals - this is OK, skip validation
            if verbose:
                results.append(ValidationResult(
                    passed=True,
                    message="Normals not present (OK for some schemas)"
                ))

        # Validation 6: Bounding box sanity check
        bbox_size = stats.bbox_size
        max_dim = max(bbox_size)
        min_dim = min(bbox_size)

        if max_dim > 1000:  # Larger than 1km is suspicious
            results.append(ValidationResult(
                passed=False,
                message=f"Bounding box too large: {max_dim:.2f}m"
            ))
        elif min_dim < 0.001:  # Smaller than 1mm is suspicious
            results.append(ValidationResult(
                passed=False,
                message=f"Bounding box too small: {min_dim:.6f}m"
            ))
        else:
            results.append(ValidationResult(
                passed=True,
                message=f"Bbox size valid: {bbox_size[0]:.2f}×{bbox_size[1]:.2f}×{bbox_size[2]:.2f}m"
            ))

        # Validation 6b: Class-based cube anomaly check
        # Certain IFC classes should NEVER be cube-like (linear/planar elements)
        # Others (equipment, furniture) legitimately can be cubes
        if min_dim > 0.001 and ifc_class:  # Only check if bbox is valid and we have class info
            w, d, h = bbox_size

            # Define IFC classes that should NOT be cube-like
            LINEAR_CLASSES = {
                'IfcWall', 'IfcWallStandardCase', 'IfcCurtainWall',
                'IfcBeam', 'IfcColumn',
                'IfcPipeSegment', 'IfcCableSegment', 'IfcDuctSegment',
                'IfcCableCarrierSegment', 'IfcConduit',
                'IfcRailing', 'IfcRamp', 'IfcStair', 'IfcStairFlight',
                'IfcMember', 'IfcPlate', 'IfcSlab', 'IfcRoof'
            }

            # Classes that CAN legitimately be cubes (skip check)
            ALLOWED_CUBE_CLASSES = {
                'IfcBuildingElementProxy',  # Can be equipment/furniture
                'IfcFurnishingElement', 'IfcFurniture',
                'IfcFlowTerminal',  # Equipment
                'IfcDistributionControlElement'
            }

            # Only validate if element is in LINEAR_CLASSES
            if ifc_class in LINEAR_CLASSES:
                # Calculate aspect ratios
                tolerance = 0.05  # 5% tolerance for "equal" dimensions
                avg_dim = (w + d + h) / 3

                # Check if all dimensions are within 5% of each other (cube-like)
                w_diff = abs(w - avg_dim) / avg_dim if avg_dim > 0 else 0
                d_diff = abs(d - avg_dim) / avg_dim if avg_dim > 0 else 0
                h_diff = abs(h - avg_dim) / avg_dim if avg_dim > 0 else 0

                is_cube_like = (w_diff < tolerance and d_diff < tolerance and h_diff < tolerance)

                if is_cube_like and max_dim > 0.01:  # Only flag cubes larger than 1cm
                    results.append(ValidationResult(
                        passed=False,
                        message=f"Cube anomaly in {ifc_class}: should be linear but bbox is cube-like ({w:.3f}×{d:.3f}×{h:.3f}m)"
                    ))
                elif verbose:
                    # Pass - linear element has proper elongated geometry
                    ratio_str = f"{w/min_dim:.1f}:{d/min_dim:.1f}:{h/min_dim:.1f}"
                    results.append(ValidationResult(
                        passed=True,
                        message=f"{ifc_class} aspect ratio OK: {ratio_str}"
                    ))
            elif verbose and ifc_class in ALLOWED_CUBE_CLASSES:
                # Cube-like is acceptable for these classes
                results.append(ValidationResult(
                    passed=True,
                    message=f"{ifc_class} can be cube-like (equipment/furniture)"
                ))

        # Validation 7: Expected dimensions (if provided)
        if expected_bbox:
            expected_w, expected_d, expected_h = expected_bbox
            actual_w, actual_d, actual_h = bbox_size

            # Allow 10% tolerance
            tolerance = 0.1
            w_ok = abs(actual_w - expected_w) / expected_w < tolerance if expected_w > 0 else True
            d_ok = abs(actual_d - expected_d) / expected_d < tolerance if expected_d > 0 else True
            h_ok = abs(actual_h - expected_h) / expected_h < tolerance if expected_h > 0 else True

            if w_ok and d_ok and h_ok:
                results.append(ValidationResult(
                    passed=True,
                    message=f"Dimensions within 10% of expected: {expected_w}×{expected_d}×{expected_h}m"
                ))
            else:
                results.append(ValidationResult(
                    passed=False,
                    message=f"Dimensions mismatch: expected {expected_w}×{expected_d}×{expected_h}m, got {actual_w:.2f}×{actual_d:.2f}×{actual_h:.2f}m"
                ))

    except Exception as e:
        results.append(ValidationResult(
            passed=False,
            message=f"Geometry parsing failed: {e}"
        ))

    return results


# ============================================================================
# DATABASE-LEVEL VALIDATION
# ============================================================================

def validate_database_geometries(db_path: Path,
                                 sample_size: Optional[int] = None,
                                 verbose: bool = False) -> Dict:
    """
    Validate all geometries in a database.

    Args:
        db_path: Path to SQLite database
        sample_size: If set, only validate random sample of N elements
        verbose: If True, print detailed progress

    Returns:
        Dictionary with validation summary
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Detect schema type (check if element_geometry view exists)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='element_geometry'")
    has_element_geometry_view = cursor.fetchone() is not None

    # Choose table/view based on schema
    if has_element_geometry_view:
        # Federation database schema (element_geometry view)
        geometry_table = "element_geometry"
        if verbose:
            print("DEBUG: Using element_geometry view (Federation schema)")
    else:
        # 2D-to-3D database schema (base_geometries table with guid)
        geometry_table = "base_geometries"
        if verbose:
            print("DEBUG: Using base_geometries table (2D-to-3D schema)")

    # Get total count
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {geometry_table}")
        total_count = cursor.fetchone()[0]
        if verbose:
            print(f"DEBUG: Total geometries in {geometry_table}: {total_count}")
    except sqlite3.Error as e:
        return {
            'total': 0,
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'errors': [f'Database query failed: {e}']
        }

    if total_count == 0:
        return {
            'total': 0,
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'errors': ['No geometries found in database']
        }

    # Determine sample size
    if sample_size is None:
        sample_size = total_count
    else:
        sample_size = min(sample_size, total_count)

    # Query geometries with IFC class (join with elements_meta)
    try:
        if sample_size < total_count:
            # Random sample
            if verbose:
                print(f"DEBUG: Sampling {sample_size} random geometries")
            cursor.execute(f"""
                SELECT g.guid, g.vertices, g.faces, g.normals, m.ifc_class
                FROM {geometry_table} g
                LEFT JOIN elements_meta m ON g.guid = m.guid
                ORDER BY RANDOM()
                LIMIT ?
            """, (sample_size,))
        else:
            # All geometries
            if verbose:
                print(f"DEBUG: Validating all {total_count} geometries")
            cursor.execute(f"""
                SELECT g.guid, g.vertices, g.faces, g.normals, m.ifc_class
                FROM {geometry_table} g
                LEFT JOIN elements_meta m ON g.guid = m.guid
            """)
    except sqlite3.Error as e:
        return {
            'total': total_count,
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'errors': [f'Failed to query geometries: {e}']
        }

    # Validate each geometry
    passed_count = 0
    failed_count = 0
    validation_failures = []

    for row in cursor.fetchall():
        guid, vertices_blob, faces_blob, normals_blob, ifc_class = row

        try:
            results = validate_geometry_blob(
                guid, vertices_blob, faces_blob, normals_blob,
                ifc_class=ifc_class, verbose=verbose
            )

            # Check if all validations passed
            all_passed = all(r.passed for r in results)

            if all_passed:
                passed_count += 1
                if verbose:
                    print(f"✓ {guid}: All checks passed")
            else:
                failed_count += 1
                failed_checks = [r.message for r in results if not r.passed]
                validation_failures.append({
                    'guid': guid,
                    'failures': failed_checks
                })
                if verbose:
                    print(f"✗ {guid}: {len(failed_checks)} failures")

        except Exception as e:
            failed_count += 1
            validation_failures.append({
                'guid': guid,
                'failures': [f"Exception: {e}"]
            })
            if verbose:
                print(f"✗ {guid}: Exception - {e}")

    conn.close()

    return {
        'total': total_count,
        'validated': sample_size,
        'passed': passed_count,
        'failed': failed_count,
        'failures': validation_failures
    }


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 geometry_validator.py <database.db> [--sample N] [--verbose]")
        print("\nValidates 3D geometry in Bonsai database without Blender.")
        print("\nOptions:")
        print("  --sample N    Validate random sample of N elements (default: all)")
        print("  --verbose     Print detailed validation results")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    sample_size = None
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

    print("=" * 70)
    print("BONSAI GEOMETRY VALIDATOR (Tier 2)")
    print("=" * 70)
    print(f"Database: {db_path}")
    print(f"Sample: {'All elements' if sample_size is None else f'{sample_size} elements'}")
    print("=" * 70)

    results = validate_database_geometries(db_path, sample_size, verbose)

    print(f"\nValidation Summary:")
    print(f"  Total geometries: {results['total']:,}")
    print(f"  Validated: {results['validated']:,}")
    print(f"  ✓ Passed: {results['passed']:,}")
    print(f"  ✗ Failed: {results['failed']:,}")

    if results['failed'] > 0:
        print(f"\nFirst 10 failures:")
        for failure in results['failures'][:10]:
            print(f"  {failure['guid']}:")
            for msg in failure['failures']:
                print(f"    - {msg}")

        sys.exit(1)
    else:
        print("\n✅ ALL GEOMETRIES VALID")
        sys.exit(0)
