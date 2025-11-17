# Preview Cube Anomaly Validation

## Overview

BonsaiTester now includes automatic detection of "preview cube anomalies" - elements whose bounding boxes are suspiciously cube-like (equal dimensions in all three axes).

## The Problem

In some geometry generation processes, elements may incorrectly receive placeholder cube geometries (often 1m×1m×1m) instead of their proper shapes. This typically indicates:

- Failed geometry extraction from source files
- Placeholder/fallback geometry being used
- Incorrect preview mode bbox generation
- Missing or corrupted source geometry data

## Detection Logic

The validator checks if an element's bounding box has all three dimensions approximately equal (within 5% tolerance):

```python
# Check if width ≈ depth ≈ height (within 5%)
tolerance = 0.05
avg_dim = (width + depth + height) / 3

is_cube_like = (
    abs(width - avg_dim) / avg_dim < tolerance and
    abs(depth - avg_dim) / avg_dim < tolerance and
    abs(height - avg_dim) / avg_dim < tolerance
)
```

## When It Triggers

- **Flagged**: Elements with bbox dimensions within 5% of each other AND larger than 1cm
- **Ignored**: Very small elements (< 1cm) that might legitimately be cube-shaped fasteners, etc.
- **Ignored**: Elements with invalid/tiny bboxes (already caught by other validators)

## Example Output

```
❌ VALIDATION FAILED - 103 geometry errors

Preview cube anomalies detected:
  • 02fa4c88-d3cb-44bd-912a-299235a359de:
    └─ Preview cube anomaly: bbox is suspiciously cube-like (1.000×1.000×1.000m, ratio ~1:1:1)
  
  • 058df6d6-f35f-4937-9f1b-bfb70fff4232:
    └─ Preview cube anomaly: bbox is suspiciously cube-like (1.000×1.000×1.000m, ratio ~1:1:1)
```

## Test Results on 2Dto3D Database

**Database:** `Terminal1_MainBuilding_FILTERED.db`
**Total Elements:** 1,185

**Findings:**
- ✅ 1,078 elements with proper non-cube geometries (91.0%)
- ⚠️ 103 elements with perfect 1m×1m×1m cubes (8.7%)
- ❌ 4 elements with tiny bboxes (0.3%)

**Most Common Cube Size:** 1.000m × 1.000m × 1.000m (exact placeholder cubes)

## Implications

Elements flagged as preview cube anomalies indicate:

1. **For 2D-to-3D conversion:** DXF elements that failed to convert properly
2. **For IFC imports:** Elements with missing or corrupted geometry
3. **For preview mode:** Incorrect bbox generation algorithm

## Recommended Actions

1. **Investigate source data:** Check if these elements have valid geometry in source files
2. **Review conversion logs:** Look for errors during DXF→IFC or geometry extraction
3. **Manual inspection:** Open in Blender and verify element appearance
4. **Consider filtering:** May want to exclude perfect cubes from preview mode

## Integration

The check runs automatically as part of Tier 2 (Geometry) validation:

```bash
./bonsai-test database.db --geometry
```

Results appear in:
- Console output (failures section)
- HTML report (failure breakdown table)
- Text log file (.log)

## Technical Details

**Validation Code Location:** `bonsai_tester/validators/geometry_validator.py`
**Function:** `validate_geometry_blob()`
**Validation Level:** Tier 2 (Geometry)
**Performance Impact:** Negligible (simple arithmetic check)

## Future Enhancements

Potential improvements:
- Flag common placeholder dimensions (1m, 2m, 0.5m cubes)
- Compare against expected IFC class dimensions
- Integration with repair mode to regenerate problem geometries
- Statistical analysis of cube distribution by discipline/type

---

**Added:** November 17, 2025
**Status:** Production Ready ✅
