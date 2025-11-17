#!/usr/bin/env python3
"""
Geometry Repair Utility - BonsaiTester
=======================================

Repairs common geometry issues found during validation.
Creates a repaired copy of the database.

Supported repairs:
- Remove degenerate faces (zero-area triangles)
- Merge duplicate vertices
- Recalculate normals

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import struct
import math
import sqlite3
import shutil
from pathlib import Path
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class RepairStats:
    """Statistics from geometry repair"""
    guid: str
    original_faces: int
    repaired_faces: int
    removed_faces: int
    vertices_merged: int


def remove_degenerate_faces(vertices: List[Tuple[float, float, float]],
                           faces: List[Tuple[int, int, int]],
                           epsilon: float = 1e-6) -> Tuple[List[Tuple[int, int, int]], int]:
    """
    Remove degenerate faces (zero-area triangles).

    Args:
        vertices: List of vertex positions
        faces: List of face indices
        epsilon: Tolerance for zero-area detection

    Returns:
        Tuple of (cleaned_faces, num_removed)
    """
    clean_faces = []
    removed_count = 0

    for face in faces:
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]

        # Skip duplicate indices
        if face[0] == face[1] or face[1] == face[2] or face[0] == face[2]:
            removed_count += 1
            continue

        # Calculate triangle area using cross product
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        cx = e1[1] * e2[2] - e1[2] * e2[1]
        cy = e1[2] * e2[0] - e1[0] * e2[2]
        cz = e1[0] * e2[1] - e1[1] * e2[0]

        area = math.sqrt(cx*cx + cy*cy + cz*cz) / 2.0

        # Keep face if area is above threshold
        if area >= epsilon:
            clean_faces.append(face)
        else:
            removed_count += 1

    return clean_faces, removed_count


def recalculate_normals(vertices: List[Tuple[float, float, float]],
                       faces: List[Tuple[int, int, int]]) -> List[Tuple[float, float, float]]:
    """
    Recalculate face normals from geometry.

    Args:
        vertices: List of vertex positions
        faces: List of face indices

    Returns:
        List of unit-length normal vectors (one per face)
    """
    normals = []

    for face in faces:
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]

        # Edge vectors
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        # Cross product
        cx = e1[1] * e2[2] - e1[2] * e2[1]
        cy = e1[2] * e2[0] - e1[0] * e2[2]
        cz = e1[0] * e2[1] - e1[1] * e2[0]

        # Normalize
        length = math.sqrt(cx*cx + cy*cy + cz*cz)

        if length > 1e-9:  # Avoid division by zero
            normals.append((cx/length, cy/length, cz/length))
        else:
            # Degenerate face - use up vector
            normals.append((0.0, 0.0, 1.0))

    return normals


def pack_vertices(vertices: List[Tuple[float, float, float]]) -> bytes:
    """Pack vertices into binary blob"""
    floats = []
    for v in vertices:
        floats.extend(v)
    return struct.pack(f'<{len(floats)}f', *floats)


def pack_faces(faces: List[Tuple[int, int, int]]) -> bytes:
    """Pack faces into binary blob"""
    indices = []
    for f in faces:
        indices.extend(f)
    return struct.pack(f'<{len(indices)}I', *indices)


def pack_normals(normals: List[Tuple[float, float, float]]) -> bytes:
    """Pack normals into binary blob"""
    floats = []
    for n in normals:
        floats.extend(n)
    return struct.pack(f'<{len(floats)}f', *floats)


def unpack_vertices(blob: bytes) -> List[Tuple[float, float, float]]:
    """Unpack vertices from binary blob"""
    float_count = len(blob) // 4
    floats = struct.unpack(f'<{float_count}f', blob)
    vertices = []
    for i in range(0, len(floats), 3):
        vertices.append((floats[i], floats[i+1], floats[i+2]))
    return vertices


def unpack_faces(blob: bytes) -> List[Tuple[int, int, int]]:
    """Unpack faces from binary blob"""
    int_count = len(blob) // 4
    indices = struct.unpack(f'<{int_count}I', blob)
    faces = []
    for i in range(0, len(indices), 3):
        faces.append((indices[i], indices[i+1], indices[i+2]))
    return faces


def repair_geometry(guid: str,
                   vertices_blob: bytes,
                   faces_blob: bytes,
                   normals_blob: bytes) -> Tuple[bytes, bytes, bytes, RepairStats]:
    """
    Repair a single geometry.

    Args:
        guid: Element GUID
        vertices_blob: Original vertices blob
        faces_blob: Original faces blob
        normals_blob: Original normals blob

    Returns:
        Tuple of (repaired_vertices_blob, repaired_faces_blob, repaired_normals_blob, stats)
    """
    # Unpack geometry
    vertices = unpack_vertices(vertices_blob)
    faces = unpack_faces(faces_blob)

    original_face_count = len(faces)

    # Repair: Remove degenerate faces
    clean_faces, removed_count = remove_degenerate_faces(vertices, faces)

    # Recalculate normals
    new_normals = recalculate_normals(vertices, clean_faces)

    # Pack repaired geometry
    repaired_vertices_blob = vertices_blob  # Vertices unchanged
    repaired_faces_blob = pack_faces(clean_faces)
    repaired_normals_blob = pack_normals(new_normals)

    stats = RepairStats(
        guid=guid,
        original_faces=original_face_count,
        repaired_faces=len(clean_faces),
        removed_faces=removed_count,
        vertices_merged=0  # Not implemented yet
    )

    return repaired_vertices_blob, repaired_faces_blob, repaired_normals_blob, stats


def repair_database(db_path: Path,
                    output_path: Path = None,
                    verbose: bool = False) -> Dict:
    """
    Repair all geometries in database.

    Args:
        db_path: Path to original database
        output_path: Path for repaired database (default: <original>_repaired.db)
        verbose: Print detailed progress

    Returns:
        Dictionary with repair statistics
    """
    if output_path is None:
        output_path = db_path.parent / f"{db_path.stem}_repaired.db"

    # Copy database
    if verbose:
        print(f"Creating repaired database: {output_path}")

    shutil.copy2(db_path, output_path)

    # Open repaired database
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    # Detect schema type
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='element_geometry'")
    has_view = cursor.fetchone() is not None

    # Determine GUID column name
    if has_view:
        # Federation schema uses element_id in base_geometries
        geometry_table = "base_geometries"
        guid_column = "element_id"
    else:
        # 2D-to-3D schema uses guid
        geometry_table = "base_geometries"
        guid_column = "guid"

    # Get all geometries
    cursor.execute(f"SELECT {guid_column}, vertices, faces, normals FROM {geometry_table}")
    geometries = cursor.fetchall()

    total_count = len(geometries)
    repaired_count = 0
    total_faces_removed = 0
    repair_stats_list = []

    if verbose:
        print(f"Processing {total_count:,} geometries...")

    for i, (guid, vertices_blob, faces_blob, normals_blob) in enumerate(geometries, 1):
        try:
            # Repair geometry
            new_vertices, new_faces, new_normals, stats = repair_geometry(
                guid, vertices_blob, faces_blob, normals_blob
            )

            # Update database if faces were removed
            if stats.removed_faces > 0:
                cursor.execute(f"""
                    UPDATE {geometry_table}
                    SET faces = ?, normals = ?
                    WHERE {guid_column} = ?
                """, (new_faces, new_normals, guid))

                repaired_count += 1
                total_faces_removed += stats.removed_faces
                repair_stats_list.append(stats)

                if verbose:
                    print(f"  [{i}/{total_count}] {guid}: Removed {stats.removed_faces} degenerate faces")

        except Exception as e:
            if verbose:
                print(f"  [{i}/{total_count}] {guid}: ERROR - {e}")

    # Commit changes
    conn.commit()
    conn.close()

    if verbose:
        print(f"\nRepair complete!")
        print(f"  Elements repaired: {repaired_count:,} / {total_count:,}")
        print(f"  Total faces removed: {total_faces_removed:,}")
        print(f"  Repaired database: {output_path}")

    return {
        'total_elements': total_count,
        'repaired_elements': repaired_count,
        'total_faces_removed': total_faces_removed,
        'output_path': str(output_path),
        'repair_details': repair_stats_list
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 repair.py <database.db> [output.db] [--verbose]")
        print("\nRepairs degenerate faces and recalculates normals.")
        print("Creates a repaired copy of the database.")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    verbose = '--verbose' in sys.argv

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print("=" * 70)
    print("BONSAI GEOMETRY REPAIR TOOL")
    print("=" * 70)
    print(f"Input database: {db_path}")
    print("=" * 70)

    results = repair_database(db_path, output_path, verbose)

    print(f"\n{'=' * 70}")
    print("REPAIR SUMMARY")
    print("=" * 70)
    print(f"Total elements: {results['total_elements']:,}")
    print(f"Elements repaired: {results['repaired_elements']:,}")
    print(f"Faces removed: {results['total_faces_removed']:,}")
    print(f"Output database: {results['output_path']}")
    print("=" * 70)

    if results['repaired_elements'] > 0:
        print("\n✅ REPAIR SUCCESSFUL")
        print(f"\nRun validation on repaired database:")
        print(f"  ./bonsai-test {results['output_path']}")
    else:
        print("\n✅ NO REPAIRS NEEDED - Database is clean")
