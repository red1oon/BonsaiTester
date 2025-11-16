# BonsaiTester GUI Usage Guide

## Overview

BonsaiTester provides both **command-line** and **graphical** interfaces:

- **CLI (`bonsai-test`)**: For power users, automation, and CI/CD
- **GUI (`bonsai-test-gui`)**: For engineers with minimal coding experience

Both interfaces use the same validation engine - choose based on your workflow!

---

## Launching the GUI

```bash
cd /path/to/BonsaiTester
./bonsai-test-gui
```

Or on Windows:
```bash
python bonsai-test-gui
```

---

## GUI Layout

```
┌──────────────────────────────────────────────────────────────┐
│ BonsaiTester 🧪                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Database                                                     │
│ ┌────────────────────────────────────────┐                  │
│ │ /path/to/database.db            [Browse...]│              │
│ └────────────────────────────────────────┘                  │
│ 📁 Terminal1_MainBuilding_FILTERED.db (1.3 MB)              │
│                                                              │
│ Validation Tests                                            │
│ ☐ Tier 1: Schema Validation (Coming Soon)                  │
│ ☑ Tier 2: Geometry Validation                              │
│     • Validates vertices, faces, normals, bounding boxes    │
│ ☐ Tier 3: Visual Validation (Coming Soon)                  │
│                                                              │
│ Options                                                      │
│ ☑ Sample validation (faster): [100] elements               │
│ ☐ Verbose output (detailed results)                        │
│                                                              │
│ [▶ Run Tests]  [Cancel]    ⏳ Running validation...        │
│                                                              │
│ Results                                                      │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ =============================================================│
│ │ VALIDATION RESULTS                                       │
│ │ =============================================================│
│ │                                                          │
│ │ Database: /path/to/database.db                           │
│ │ Size: 1.3 MB                                             │
│ │ Time: 18.4 seconds                                       │
│ │                                                          │
│ │ Summary:                                                 │
│ │   Total geometries: 1,185                                │
│ │   Validated: 1,185                                       │
│ │   Passed: 1,181                                          │
│ │   Failed: 4                                              │
│ │                                                          │
│ │ ❌ VALIDATION FAILED - 4 geometry errors                │
│ │                                                          │
│ │ First 4 failures:                                        │
│ │   • 2f05e6a0-35b0-4849-964c-3543bae084bb:              │
│ │     └─ Bounding box too small: 0.000006m                │
│ │   • 43e27944-6021-47c4-9c8a-846ff43d9b01:              │
│ │     └─ Bounding box too small: 0.000006m                │
│ │   ...                                                    │
│ └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Usage

### 1. Select Database

**Option A: Browse**
- Click the **"Browse..."** button
- Navigate to your `.db` file
- Select and click "Open"

**Option B: Drag & Drop** (if supported by your OS)
- Drag `.db` file into the database field

**Info displayed:**
- 📁 Filename and size (e.g., "Terminal1_MainBuilding_FILTERED.db (1.3 MB)")

---

### 2. Choose Validation Tests

**Available tests:**

✅ **Tier 2: Geometry Validation** (Recommended)
- Validates vertices, faces, normals, bounding boxes
- Fastest validation (10-20 seconds for 1,000 elements)
- **Always enabled by default**

⏳ **Tier 1: Schema Validation** (Coming Soon)
- Database schema and integrity checks
- Future release

⏳ **Tier 3: Visual Validation** (Coming Soon)
- Blender background rendering and snapshot comparison
- Future release

---

### 3. Configure Options

**Sample Validation** (Recommended for large databases)
- ☑ Enable checkbox
- Enter number of elements (e.g., `100`)
- **Use case:** Quick validation during development
- **Speed:** ~1 second for 100 elements

**Verbose Output**
- ☐ Disable for summary only
- ☑ Enable for detailed per-element results
- **Use case:** Debugging specific geometry issues

---

### 4. Run Tests

Click **"▶ Run Tests"** button

**What happens:**
1. GUI validates your selections
2. Calls CLI backend in background thread
3. Shows progress indicator: "⏳ Running validation..."
4. Displays results in real-time

**Duration:**
- Sample (100 elements): ~1 second
- Full database (1,000 elements): 10-20 seconds
- Large database (10,000 elements): 2-3 minutes

---

### 5. Interpret Results

**Success (All Pass):**
```
✅ ALL GEOMETRIES VALID

Summary:
  Total geometries: 1,185
  Validated: 1,185
  Passed: 1,185
  Failed: 0
```

**Popup:** "✅ All 1,185 geometries are valid!"

---

**Failure (Some Errors):**
```
❌ VALIDATION FAILED - 4 geometry errors

First 4 failures:
  • 2f05e6a0-35b0-4849-964c-3543bae084bb:
    └─ Bounding box too small: 0.000006m
  • 43e27944-6021-47c4-9c8a-846ff43d9b01:
    └─ Bounding box too small: 0.000006m
  ...
```

**Action:** Fix geometry generation code, re-run validation

---

## Tips & Best Practices

### For Quick Checks
```
✅ Enable: Sample validation (100 elements)
✅ Disable: Verbose output
⏱ Speed: ~1 second
```

### For Full Validation
```
✅ Enable: Tier 2 Geometry Validation
✅ Disable: Sample validation (validate all)
☐ Optional: Verbose output (for debugging)
⏱ Speed: 10-20 seconds (1,000 elements)
```

### For Debugging Specific Elements
```
✅ Enable: Verbose output
✅ Enable: Sample validation (small number)
📋 Copy GUID from error message
🔍 Inspect in database or Blender
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open database (Browse) |
| `Ctrl+R` | Run tests |
| `Esc` | Cancel (if running) |
| `Ctrl+Q` | Quit application |

*(Shortcuts may vary by OS)*

---

## Troubleshooting

### "Please select a database file first!"
**Solution:** Click "Browse..." and select a `.db` file

---

### "Database file not found"
**Solution:** Check that the file path is correct and file exists

---

### "No tests selected!"
**Solution:** Enable at least one test (Tier 2 recommended)

---

### "Validation timed out (>5 minutes)"
**Causes:**
- Very large database (>10,000 elements)
- System resource constraints

**Solution:**
- Use sample validation instead
- Close other applications
- Increase timeout in code (advanced)

---

### Validation Results Not Showing
**Causes:**
- CLI not found (incorrect path)
- JSON parsing error

**Solution:**
1. Check that `bonsai-test` is in same folder as `bonsai-test-gui`
2. Run CLI manually to test: `./bonsai-test database.db --json`

---

## Comparison: CLI vs GUI

| Feature | CLI | GUI |
|---------|-----|-----|
| **Speed** | Instant | Same (calls CLI backend) |
| **Automation** | ✅ Yes | ❌ No |
| **CI/CD** | ✅ Yes | ❌ No |
| **User-friendly** | ❌ No (requires terminal) | ✅ Yes |
| **Visual feedback** | ❌ Text only | ✅ Color-coded |
| **Scriptable** | ✅ Yes | ❌ No |
| **SSH-friendly** | ✅ Yes | ❌ No (requires X11) |
| **Best for** | Developers, automation | Engineers, one-off testing |

**Recommendation:** Use GUI for manual testing, CLI for automation

---

## Advanced: Integration with CLI

The GUI simply calls the CLI with `--json` flag:

```bash
# What the GUI does internally:
./bonsai-test database.db --json --sample 100
```

**Output:**
```json
{
  "mode": "geometry",
  "database": "/path/to/database.db",
  "database_size_mb": 1.3,
  "sample_size": 100,
  "results": {
    "total": 1185,
    "validated": 100,
    "passed": 100,
    "failed": 0,
    "failures": [],
    "elapsed_time": 0.8
  },
  "success": true
}
```

**You can parse this JSON in your own scripts!**

---

## Future Enhancements (Planned)

- [ ] Tier 1 Schema Validation UI
- [ ] Tier 3 Visual Validation UI
- [ ] Progress bar (real-time %)
- [ ] Export results to HTML/PDF
- [ ] Element inspector (click GUID → show details)
- [ ] Comparison mode (diff two databases)
- [ ] Settings panel (save preferences)
- [ ] Recent databases list
- [ ] Drag-and-drop database loading

---

## Feedback & Support

**Found a bug?** Open an issue: https://github.com/red1oon/BonsaiTester/issues

**Feature request?** We'd love to hear from you!

**Questions?** Check the main README.md or CLI usage guide

---

**Made with ❤️ for the Bonsai BIM community**

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
