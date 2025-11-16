"""
BonsaiTester - Headless Testing Engine for Bonsai BIM
======================================================

Fast, deterministic validation of IFC/BIM data without launching Blender GUI.

Tier 1: Database Schema Validation (< 5 seconds)
Tier 2: Geometry Validation (10-20 seconds)
Tier 3: Visual Validation with Blender (30-60 seconds)

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
Repository: https://github.com/red1oon/BonsaiTester
"""

__version__ = "0.1.0"
__author__ = "Redhuan D. Oon"
__license__ = "LGPL-3.0"

from .validators.geometry_validator import (
    validate_geometry_blob,
    validate_database_geometries,
    parse_geometry,
    GeometryStats,
    ValidationResult
)

__all__ = [
    'validate_geometry_blob',
    'validate_database_geometries',
    'parse_geometry',
    'GeometryStats',
    'ValidationResult'
]
