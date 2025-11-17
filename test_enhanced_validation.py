#!/usr/bin/env python3
"""
Test enhanced visualization validator on both databases
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bonsai_tester.validators.visualization_validator import validate_2dto3d_visualization, generate_visualization_report
from datetime import datetime

def test_database(db_path: Path, name: str, log_dir: Path):
    """Test a single database and write results to log"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"Database: {db_path}")
    print(f"{'='*70}")

    # Run validation
    report = validate_2dto3d_visualization(db_path, sample_size=200, verbose=True)

    # Generate report text
    report_text = generate_visualization_report(report)

    # Print to console
    print(report_text)

    # Write to log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"visualization_validation_{timestamp}.txt"

    with open(log_file, 'w') as f:
        f.write(f"Enhanced Visualization Validation Report\n")
        f.write(f"Database: {db_path}\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n{report_text}\n")

    print(f"\n✓ Report saved to: {log_file}")

    return report

if __name__ == "__main__":
    # Test 8_IFC database (source of truth)
    db_8ifc = Path("/home/red1/Documents/bonsai/8_IFC/enhanced_federation.db")
    log_8ifc = Path("/home/red1/Documents/bonsai/8_IFC/logs")
    log_8ifc.mkdir(exist_ok=True)

    print("\n" + "="*70)
    print("TEST 1: 8_IFC Database (Source of Truth)")
    print("="*70)
    report_8ifc = test_database(db_8ifc, "8_IFC (Source of Truth)", log_8ifc)

    # Test 2Dto3D database
    db_2dto3d = Path("/home/red1/Documents/bonsai/2Dto3D/Terminal1_MainBuilding_FILTERED.db")
    log_2dto3d = Path("/home/red1/Documents/bonsai/2Dto3D/logs")
    log_2dto3d.mkdir(exist_ok=True)

    print("\n" + "="*70)
    print("TEST 2: 2Dto3D Database")
    print("="*70)
    report_2dto3d = test_database(db_2dto3d, "2Dto3D Terminal1", log_2dto3d)

    # Comparison summary
    print("\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)

    print("\n8_IFC (Expected Behavior):")
    print(f"  Disciplines: {report_8ifc.discipline_colors.get('status')}")
    print(f"  Parametric Shapes: {report_8ifc.parametric_shapes.get('status')} - {report_8ifc.parametric_shapes.get('parametric_count')} elements")
    print(f"  Shape Types: {', '.join(report_8ifc.parametric_shapes.get('shape_types_found', []))}")

    print("\n2Dto3D (Current Status):")
    print(f"  Disciplines: {report_2dto3d.discipline_colors.get('status')}")
    print(f"  Parametric Shapes: {report_2dto3d.parametric_shapes.get('status')} - {report_2dto3d.parametric_shapes.get('parametric_count')} elements")
    print(f"  Shape Types: {', '.join(report_2dto3d.parametric_shapes.get('shape_types_found', []))}")

    print("\n✓ All tests complete!")
