#!/usr/bin/env python3
"""
Geometry Preview Module - BonsaiTester GUI
===========================================

Extracts and displays 3D geometry from database for visual validation.
Shows actual geometry shape to verify:
- Proper parametric forms (not just boxes)
- Rotation application
- Meaningful dimensions

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import sqlite3
import struct
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import tkinter as tk


# ============================================================================
# GEOMETRY EXTRACTION
# ============================================================================

def extract_geometry_from_db(db_path: Path, guid: str) -> Optional[Dict]:
    """
    Extract geometry data for a specific element.

    Args:
        db_path: Path to database
        guid: Element GUID

    Returns:
        Dictionary with vertices, faces, normals, and metadata
        None if element not found
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Detect column names (8_IFC uses 'verts', 2Dto3D uses 'vertices')
        cursor.execute("PRAGMA table_info(base_geometries)")
        columns = {row[1] for row in cursor.fetchall()}

        has_verts = 'verts' in columns
        has_vertices = 'vertices' in columns

        if has_verts:
            # 8_IFC schema: verts, faces, normals
            cursor.execute("""
                SELECT verts, faces, normals
                FROM base_geometries
                WHERE guid = ?
            """, (guid,))
        elif has_vertices:
            # 2Dto3D schema: vertices, faces, normals
            cursor.execute("""
                SELECT vertices, faces, normals
                FROM base_geometries
                WHERE guid = ?
            """, (guid,))
        else:
            return None

        result = cursor.fetchone()
        if not result:
            return None

        verts_blob, faces_blob, normals_blob = result

        # Unpack binary data
        vertices = _unpack_float_array(verts_blob) if verts_blob else []
        faces = _unpack_int_array(faces_blob) if faces_blob else []
        normals = _unpack_float_array(normals_blob) if normals_blob else []

        # Get metadata (same for both schemas)
        cursor.execute("""
            SELECT em.ifc_class, em.discipline, et.rotation_z
            FROM elements_meta em
            LEFT JOIN element_transforms et ON em.guid = et.guid
            WHERE em.guid = ?
        """, (guid,))

        meta_result = cursor.fetchone()
        ifc_class = meta_result[0] if meta_result else "Unknown"
        discipline = meta_result[1] if meta_result else "Unknown"
        rotation = meta_result[2] if meta_result and meta_result[2] else 0.0

        # Reshape vertices (assuming XYZ triplets)
        if len(vertices) % 3 == 0:
            vertices = np.array(vertices).reshape(-1, 3)
        else:
            vertices = np.array([])

        # Reshape faces (assuming triangle indices)
        if len(faces) % 3 == 0:
            faces = np.array(faces).reshape(-1, 3)
        else:
            faces = np.array([])

        return {
            'guid': guid,
            'ifc_class': ifc_class,
            'discipline': discipline,
            'rotation_z': rotation,
            'vertices': vertices,
            'faces': faces,
            'normals': normals,
            'vertex_count': len(vertices),
            'face_count': len(faces) if len(faces) > 0 else 0,
        }

    finally:
        conn.close()


def _unpack_float_array(blob: bytes) -> List[float]:
    """Unpack binary blob as float array"""
    if not blob:
        return []

    count = len(blob) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', blob))


def _unpack_int_array(blob: bytes) -> List[int]:
    """Unpack binary blob as integer array"""
    if not blob:
        return []

    count = len(blob) // 4  # 4 bytes per int
    return list(struct.unpack(f'{count}i', blob))


# ============================================================================
# ELEMENT SELECTION
# ============================================================================

def find_interesting_elements(db_path: Path, limit: int = 10) -> List[Dict]:
    """
    Find interesting elements for preview (doors, furniture, columns, etc.).

    Args:
        db_path: Path to database
        limit: Maximum number of elements to return

    Returns:
        List of element dictionaries with guid, ifc_class, discipline
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Detect column names (8_IFC uses 'verts', 2Dto3D uses 'vertices')
        cursor.execute("PRAGMA table_info(base_geometries)")
        columns = {row[1] for row in cursor.fetchall()}

        has_verts = 'verts' in columns
        has_vertices = 'vertices' in columns

        vertex_column = 'verts' if has_verts else 'vertices' if has_vertices else None

        if not vertex_column:
            return []

        # Prioritize visually interesting IFC classes
        # Organized by category for engineering validation
        interesting_classes = [
            # Architectural
            'IfcDoor', 'IfcWindow', 'IfcWall', 'IfcSlab', 'IfcStair',

            # Structure
            'IfcColumn', 'IfcBeam', 'IfcFooting',

            # Furniture & Fixtures
            'IfcFurnishingElement', 'IfcFurniture', 'IfcChair', 'IfcTable',
            'IfcSanitaryTerminal',  # Toilets, sinks

            # MEP - ACMV (Air Conditioning Mechanical Ventilation)
            'IfcAirTerminal',  # Diffusers, grilles
            'IfcFan',  # Fans
            'IfcAirToAirHeatRecovery',  # Heat recovery units
            'IfcUnitaryEquipment',  # FCU, AHU
            'IfcDuctSegment', 'IfcDuctFitting',

            # MEP - Plumbing
            'IfcPipeSegment', 'IfcPipeFitting',
            'IfcFlowTerminal',  # Generic terminals

            # MEP - Electrical
            'IfcLightFixture', 'IfcOutlet', 'IfcSwitchingDevice',
            'IfcCableSegment', 'IfcCableFitting',

            # Fire Protection
            'IfcFireSuppressionTerminal',  # Sprinklers
            'IfcAlarm',  # Fire alarms

            # Generic/Proxy (often used for custom elements)
            'IfcBuildingElementProxy'
        ]

        elements = []

        for ifc_class in interesting_classes:
            cursor.execute(f"""
                SELECT em.guid, em.ifc_class, em.discipline, bg.{vertex_column}
                FROM elements_meta em
                JOIN base_geometries bg ON em.guid = bg.guid
                WHERE em.ifc_class = ?
                LIMIT ?
            """, (ifc_class, limit))

            results = cursor.fetchall()

            for guid, ifc_class, discipline, verts_blob in results:
                # Count vertices
                vertex_count = len(verts_blob) // (4 * 3) if verts_blob else 0

                elements.append({
                    'guid': guid,
                    'ifc_class': ifc_class,
                    'discipline': discipline or 'Unknown',
                    'vertex_count': vertex_count,
                    'display_name': f"{ifc_class} ({discipline or 'N/A'}) - {vertex_count} vertices"
                })

                if len(elements) >= limit:
                    break

            if len(elements) >= limit:
                break

        return elements

    finally:
        conn.close()


# ============================================================================
# GEOMETRY ANALYSIS
# ============================================================================

def analyze_geometry_shape(geometry: Dict) -> Dict:
    """
    Analyze geometry shape characteristics.

    Args:
        geometry: Geometry dict from extract_geometry_from_db

    Returns:
        Dictionary with shape analysis
    """
    vertices = geometry['vertices']

    if len(vertices) == 0:
        return {
            'is_valid': False,
            'shape_type': 'empty',
            'message': 'No vertices'
        }

    # Calculate bounding box
    min_coords = np.min(vertices, axis=0)
    max_coords = np.max(vertices, axis=0)
    dimensions = max_coords - min_coords

    # Determine shape type
    vertex_count = len(vertices)
    face_count = geometry.get('face_count', 0)

    if vertex_count == 8 and np.allclose(dimensions[:2], 1.0, atol=0.01):
        shape_type = 'simple_box'
        quality = 'PLACEHOLDER'
    elif vertex_count == 8:
        shape_type = 'box'
        quality = 'BASIC'
    elif 20 <= vertex_count <= 40 and geometry['ifc_class'] == 'IfcColumn':
        shape_type = 'cylinder'
        quality = 'PARAMETRIC'
    elif vertex_count > 40:
        shape_type = 'complex'
        quality = 'DETAILED'
    else:
        shape_type = 'custom'
        quality = 'BASIC'

    return {
        'is_valid': True,
        'shape_type': shape_type,
        'quality': quality,
        'vertex_count': vertex_count,
        'face_count': face_count,
        'dimensions': dimensions,
        'bounding_box': (min_coords, max_coords),
        'message': f"{quality}: {shape_type} ({vertex_count} vertices)"
    }


# ============================================================================
# 3D PLOTTING (MATPLOTLIB)
# ============================================================================

def plot_geometry_3d(geometry: Dict, ax=None):
    """
    Plot geometry using matplotlib 3D.

    Args:
        geometry: Geometry dict from extract_geometry_from_db
        ax: Matplotlib 3D axis (optional, creates new if None)

    Returns:
        Matplotlib axis object
    """
    try:
        from mpl_toolkits.mplot3d import Axes3D
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required for 3D plotting: pip install matplotlib")

    if ax is None:
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection='3d')

    vertices = geometry['vertices']
    faces = geometry['faces']

    if len(vertices) == 0:
        ax.text(0, 0, 0, 'No geometry data', fontsize=12, color='red')
        return ax

    # Plot vertices as scatter
    ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2],
              c='blue', marker='o', s=20, alpha=0.6)

    # Plot faces if available
    if len(faces) > 0 and faces.shape[0] > 0:
        # Create triangles
        triangles = []
        for face in faces:
            if len(face) >= 3:
                try:
                    triangle = vertices[face[:3]]
                    triangles.append(triangle)
                except IndexError:
                    continue

        if triangles:
            collection = Poly3DCollection(triangles, alpha=0.3,
                                        facecolor='cyan',
                                        edgecolor='black',
                                        linewidths=0.5)
            ax.add_collection3d(collection)

    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(f"{geometry['ifc_class']} ({geometry['discipline']})\n"
                f"{geometry['vertex_count']} vertices, "
                f"{geometry['face_count']} faces")

    # Equal aspect ratio
    max_range = np.max(np.ptp(vertices, axis=0))
    mid = np.mean(vertices, axis=0)
    ax.set_xlim(mid[0] - max_range/2, mid[0] + max_range/2)
    ax.set_ylim(mid[1] - max_range/2, mid[1] + max_range/2)
    ax.set_zlim(mid[2] - max_range/2, mid[2] + max_range/2)

    return ax


def plot_wireframe(geometry: Dict, ax=None):
    """
    Plot geometry as wireframe (edges only).

    Args:
        geometry: Geometry dict from extract_geometry_from_db
        ax: Matplotlib 3D axis (optional, creates new if None)

    Returns:
        Matplotlib axis object
    """
    try:
        from mpl_toolkits.mplot3d import Axes3D
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required for 3D plotting: pip install matplotlib")

    if ax is None:
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection='3d')

    vertices = geometry['vertices']
    faces = geometry['faces']

    if len(vertices) == 0:
        ax.text(0, 0, 0, 'No geometry data', fontsize=12, color='red')
        return ax

    # Plot edges from faces
    if len(faces) > 0:
        for face in faces:
            if len(face) >= 3:
                try:
                    # Draw triangle edges
                    for i in range(3):
                        v1 = vertices[face[i]]
                        v2 = vertices[face[(i+1) % 3]]
                        ax.plot([v1[0], v2[0]], [v1[1], v2[1]], [v1[2], v2[2]],
                               'b-', linewidth=1, alpha=0.6)
                except IndexError:
                    continue

    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(f"{geometry['ifc_class']} - Wireframe\n"
                f"Rotation: {geometry['rotation_z']:.1f}°")

    # Equal aspect ratio
    max_range = np.max(np.ptp(vertices, axis=0))
    mid = np.mean(vertices, axis=0)
    ax.set_xlim(mid[0] - max_range/2, mid[0] + max_range/2)
    ax.set_ylim(mid[1] - max_range/2, mid[1] + max_range/2)
    ax.set_zlim(mid[2] - max_range/2, mid[2] + max_range/2)

    return ax


# ============================================================================
# SIMPLE 2D PROJECTION (FALLBACK)
# ============================================================================

def plot_2d_projection(geometry: Dict, canvas, width: int = 400, height: int = 400):
    """
    Plot simple 2D projection on tkinter canvas (fallback if matplotlib unavailable).

    Args:
        geometry: Geometry dict from extract_geometry_from_db
        canvas: Tkinter Canvas widget
        width: Canvas width
        height: Canvas height
    """
    vertices = geometry['vertices']

    if len(vertices) == 0:
        canvas.create_text(width/2, height/2, text="No geometry data",
                          fill="red", font=("Arial", 12))
        return

    # Project to XY plane (top view)
    x_coords = vertices[:, 0]
    y_coords = vertices[:, 1]

    # Normalize to canvas size
    x_min, x_max = np.min(x_coords), np.max(x_coords)
    y_min, y_max = np.min(y_coords), np.max(y_coords)

    margin = 20
    x_scale = (width - 2*margin) / max(x_max - x_min, 0.001)
    y_scale = (height - 2*margin) / max(y_max - y_min, 0.001)
    scale = min(x_scale, y_scale)

    # Transform coordinates
    def transform(x, y):
        tx = margin + (x - x_min) * scale
        ty = height - (margin + (y - y_min) * scale)  # Flip Y
        return tx, ty

    # Draw axes
    canvas.create_line(margin, height/2, width-margin, height/2,
                      fill="lightgray", dash=(2, 2))
    canvas.create_line(width/2, margin, width/2, height-margin,
                      fill="lightgray", dash=(2, 2))

    # Draw vertices
    for vertex in vertices:
        x, y = transform(vertex[0], vertex[1])
        canvas.create_oval(x-2, y-2, x+2, y+2, fill="blue", outline="black")

    # Draw faces if available
    faces = geometry.get('faces', np.array([]))
    if len(faces) > 0:
        for face in faces:
            if len(face) >= 3:
                try:
                    points = []
                    for idx in face[:3]:
                        v = vertices[idx]
                        points.extend(transform(v[0], v[1]))

                    if len(points) >= 6:
                        canvas.create_polygon(points, fill="cyan",
                                            outline="black", stipple="gray25")
                except IndexError:
                    continue

    # Draw title
    canvas.create_text(width/2, 15,
                      text=f"{geometry['ifc_class']} - Top View (XY)",
                      font=("Arial", 10, "bold"))

    # Draw info
    info_text = (f"{geometry['vertex_count']} vertices\n"
                f"Rotation: {geometry['rotation_z']:.1f}°")
    canvas.create_text(width-10, height-10, text=info_text,
                      anchor=tk.SE, font=("Arial", 8), fill="gray")
