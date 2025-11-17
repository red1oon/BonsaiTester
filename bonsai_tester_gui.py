#!/usr/bin/env python3
"""
BonsaiTester GUI - Visual Database Validation Tool
==================================================

Visual interface for BonsaiTester with:
- Database selection and comparison
- Incremental and ALL testing modes
- Real-time progress visualization
- Interactive charts and graphs
- Export capabilities

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import sys
import json
import threading
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

# GUI imports
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

# Try to import matplotlib for charts (optional)
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not available - charts will be disabled")

# Add bonsai_tester to path
sys.path.insert(0, str(Path(__file__).parent))

from bonsai_tester.validators.geometry_validator import validate_database_geometries
from bonsai_tester.validators.schema_validator import validate_database_schema
from bonsai_tester.geometry_preview import (
    find_interesting_elements,
    extract_geometry_from_db,
    analyze_geometry_shape,
    plot_geometry_3d,
    plot_wireframe,
    plot_2d_projection
)
from bonsai_tester.gui_logger import get_logger, close_logger


# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================

class BonsaiTesterGUI:
    """Main GUI application window"""

    def __init__(self, root):
        self.root = root
        self.root.title("BonsaiTester - Visual Database Validator")
        self.root.geometry("1400x900")

        # Initialize logger
        self.logger = get_logger()
        self.logger.section("BONSAITESTER GUI STARTUP")
        self.logger.info("GUI Application Initialized")
        self.logger.debug(f"Python version: {sys.version}")
        self.logger.debug(f"Working directory: {Path.cwd()}")

        # State variables
        self.db_path = None
        self.compare_db_path = None
        self.test_mode = tk.StringVar(value="all")  # "all" or "incremental"
        self.is_running = False
        self.current_results = {}

        # Setup UI
        self._setup_styles()
        self._create_widgets()

        self.logger.info("GUI widgets created successfully")

        # Register cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Status colors
        style.configure("Pass.TLabel", foreground="green", font=("Arial", 10, "bold"))
        style.configure("Fail.TLabel", foreground="red", font=("Arial", 10, "bold"))
        style.configure("Running.TLabel", foreground="orange", font=("Arial", 10, "bold"))

        # Headers
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
        style.configure("SubHeader.TLabel", font=("Arial", 10, "bold"))

    def _create_widgets(self):
        """Create all GUI widgets"""

        # ===== TOP BAR: Database Selection =====
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="BonsaiTester - Visual Validator",
                 style="Header.TLabel").pack(side=tk.LEFT, padx=10)

        # Database 1
        ttk.Label(top_frame, text="Database 1:").pack(side=tk.LEFT, padx=5)
        self.db1_label = ttk.Label(top_frame, text="No database selected",
                                   foreground="gray")
        self.db1_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text="Select DB",
                  command=self._select_database).pack(side=tk.LEFT, padx=5)

        # Database 2 (for comparison)
        ttk.Label(top_frame, text="Compare with:").pack(side=tk.LEFT, padx=(20, 5))
        self.db2_label = ttk.Label(top_frame, text="(Optional)",
                                   foreground="gray")
        self.db2_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text="Select DB",
                  command=self._select_compare_database).pack(side=tk.LEFT, padx=5)

        # ===== CONTROL PANEL =====
        control_frame = ttk.LabelFrame(self.root, text="Test Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Test mode selection
        ttk.Label(control_frame, text="Mode:").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(control_frame, text="ALL (Run all tests)",
                       variable=self.test_mode, value="all").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(control_frame, text="Incremental (Step by step)",
                       variable=self.test_mode, value="incremental").pack(side=tk.LEFT, padx=5)

        # Test tier checkboxes
        self.tier1_var = tk.BooleanVar(value=True)
        self.tier2_var = tk.BooleanVar(value=True)
        self.tier25_var = tk.BooleanVar(value=True)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Label(control_frame, text="Tests:").pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(control_frame, text="Tier 1: Schema",
                       variable=self.tier1_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(control_frame, text="Tier 2: Geometry",
                       variable=self.tier2_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(control_frame, text="Tier 2.5: Visualization",
                       variable=self.tier25_var).pack(side=tk.LEFT, padx=5)

        # Run button
        self.run_button = ttk.Button(control_frame, text="▶ Run Tests",
                                     command=self._run_tests, style="Accent.TButton")
        self.run_button.pack(side=tk.RIGHT, padx=10)

        # Stop button
        self.stop_button = ttk.Button(control_frame, text="⏹ Stop",
                                      command=self._stop_tests, state=tk.DISABLED)
        self.stop_button.pack(side=tk.RIGHT, padx=5)

        # ===== MAIN CONTENT AREA =====
        content_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # LEFT: Test Results Panel
        left_frame = ttk.Frame(content_paned)
        content_paned.add(left_frame, weight=1)

        self._create_results_panel(left_frame)

        # RIGHT: Visualization Panel
        right_frame = ttk.Frame(content_paned)
        content_paned.add(right_frame, weight=1)

        self._create_visualization_panel(right_frame)

        # ===== BOTTOM: Status Bar =====
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(status_frame, text="Ready",
                                     relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, side=tk.LEFT, expand=True)

        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)

    def _create_results_panel(self, parent):
        """Create test results panel"""
        ttk.Label(parent, text="Test Results",
                 style="SubHeader.TLabel").pack(anchor=tk.W, pady=5)

        # Results tree view
        columns = ("Test", "Status", "Passed", "Failed", "Details")
        self.results_tree = ttk.Treeview(parent, columns=columns,
                                        show='headings', height=15)

        for col in columns:
            self.results_tree.heading(col, text=col)

        # Column widths
        self.results_tree.column("Test", width=150)
        self.results_tree.column("Status", width=80)
        self.results_tree.column("Passed", width=60)
        self.results_tree.column("Failed", width=60)
        self.results_tree.column("Details", width=250)

        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL,
                                 command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        # Bind double-click to show details
        self.results_tree.bind("<Double-1>", self._show_test_details)

        # Log output area
        log_frame = ttk.LabelFrame(parent, text="Test Output", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10,
                                                  wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_visualization_panel(self, parent):
        """Create visualization panel with charts"""
        ttk.Label(parent, text="Visualization",
                 style="SubHeader.TLabel").pack(anchor=tk.W, pady=5)

        # Create notebook for different visualizations
        self.viz_notebook = ttk.Notebook(parent)
        self.viz_notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Summary Charts
        self.summary_frame = ttk.Frame(self.viz_notebook)
        self.viz_notebook.add(self.summary_frame, text="Summary")

        # Tab 2: Geometry Stats
        self.geometry_frame = ttk.Frame(self.viz_notebook)
        self.viz_notebook.add(self.geometry_frame, text="Geometry")

        # Tab 3: Discipline Breakdown
        self.discipline_frame = ttk.Frame(self.viz_notebook)
        self.viz_notebook.add(self.discipline_frame, text="Disciplines")

        # Tab 4: Comparison (if 2 databases)
        self.comparison_frame = ttk.Frame(self.viz_notebook)
        self.viz_notebook.add(self.comparison_frame, text="Comparison")

        # Tab 5: Detailed Stats
        self.stats_frame = ttk.Frame(self.viz_notebook)
        self.viz_notebook.add(self.stats_frame, text="Detailed Stats")

        # Tab 6: 3D Preview
        self.preview_frame = ttk.Frame(self.viz_notebook)
        self.viz_notebook.add(self.preview_frame, text="3D Preview")

        # Initialize with placeholder
        ttk.Label(self.summary_frame,
                 text="Run tests to see visualization",
                 foreground="gray").pack(expand=True)

    # ===== EVENT HANDLERS =====

    def _select_database(self):
        """Select primary database"""
        self.logger.debug("Opening database selection dialog")

        file_path = filedialog.askopenfilename(
            title="Select Bonsai Database",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )

        if file_path:
            self.db_path = Path(file_path)
            size_mb = self.db_path.stat().st_size / (1024**2)

            self.logger.log_database_selection(self.db_path, size_mb)

            self.db1_label.config(text=self.db_path.name, foreground="black")
            self._log(f"Selected database: {self.db_path}")
            self._update_status(f"Database loaded: {self.db_path.name}")
        else:
            self.logger.debug("Database selection cancelled")

    def _select_compare_database(self):
        """Select comparison database"""
        file_path = filedialog.askopenfilename(
            title="Select Database for Comparison",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )

        if file_path:
            self.compare_db_path = Path(file_path)
            self.db2_label.config(text=self.compare_db_path.name, foreground="black")
            self._log(f"Comparison database: {self.compare_db_path}")

    def _run_tests(self):
        """Run selected tests"""
        if not self.db_path:
            messagebox.showwarning("No Database",
                                  "Please select a database first")
            return

        if not any([self.tier1_var.get(), self.tier2_var.get(), self.tier25_var.get()]):
            messagebox.showwarning("No Tests Selected",
                                  "Please select at least one test tier")
            return

        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        self.log_text.delete(1.0, tk.END)
        self.current_results = {}

        # Disable controls
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_running = True

        # Start progress animation
        self.progress_bar.start()

        # Run tests in thread
        mode = self.test_mode.get()
        if mode == "all":
            threading.Thread(target=self._run_all_tests, daemon=True).start()
        else:
            threading.Thread(target=self._run_incremental_tests, daemon=True).start()

    def _stop_tests(self):
        """Stop running tests"""
        self.is_running = False
        self._update_status("Tests stopped by user")
        self._finalize_test_run()

    def _run_all_tests(self):
        """Run all selected tests at once"""
        self._update_status("Running all tests...")
        self._log("=" * 70)
        self._log(f"Running tests in ALL mode on: {self.db_path.name}")
        self._log("=" * 70)

        # Log test start
        tiers = []
        if self.tier1_var.get():
            tiers.append("Tier 1: Schema")
        if self.tier2_var.get():
            tiers.append("Tier 2: Geometry")
        if self.tier25_var.get():
            tiers.append("Tier 2.5: Visualization")

        self.logger.log_test_start("ALL", tiers)

        start_time = datetime.now()

        # Run Tier 1: Schema
        if self.tier1_var.get() and self.is_running:
            self._run_schema_validation()

        # Run Tier 2: Geometry
        if self.tier2_var.get() and self.is_running:
            self._run_geometry_validation()

        # Run Tier 2.5: Visualization
        if self.tier25_var.get() and self.is_running:
            self._run_visualization_validation()

        # Calculate elapsed time
        elapsed = (datetime.now() - start_time).total_seconds()

        self._log("=" * 70)
        self._log(f"All tests completed in {elapsed:.1f} seconds")
        self._log("=" * 70)

        # Log test end
        success = not any(r.get('failed', 0) > 0 for r in self.current_results.values() if isinstance(r, dict))
        self.logger.log_test_end(elapsed, success)

        # Update visualizations
        self.root.after(0, self._update_all_visualizations)

        # Finalize
        self.root.after(0, self._finalize_test_run)

    def _run_incremental_tests(self):
        """Run tests one by one with pauses"""
        self._update_status("Running incremental tests...")
        self._log("=" * 70)
        self._log(f"Running tests in INCREMENTAL mode on: {self.db_path.name}")
        self._log("=" * 70)

        import time

        # Run Tier 1: Schema
        if self.tier1_var.get() and self.is_running:
            self._log("\n[Step 1/3] Starting Schema Validation...")
            self._run_schema_validation()
            self.root.after(0, self._update_schema_visualization)
            time.sleep(1)  # Pause for visualization

        # Run Tier 2: Geometry
        if self.tier2_var.get() and self.is_running:
            self._log("\n[Step 2/3] Starting Geometry Validation...")
            self._run_geometry_validation()
            self.root.after(0, self._update_geometry_visualization)
            time.sleep(1)  # Pause for visualization

        # Run Tier 2.5: Visualization
        if self.tier25_var.get() and self.is_running:
            self._log("\n[Step 3/3] Starting Visualization Validation...")
            self._run_visualization_validation()
            self.root.after(0, self._update_discipline_visualization)
            time.sleep(1)  # Pause for visualization

        self._log("\n" + "=" * 70)
        self._log("All incremental tests completed")
        self._log("=" * 70)

        # Finalize
        self.root.after(0, self._finalize_test_run)

    def _run_schema_validation(self):
        """Run Tier 1 schema validation"""
        try:
            self._log("\n[Tier 1: Schema Validation]")
            self.logger.log_validator_start("Tier 1", "Schema Validation")

            # Call validator
            import time
            start = time.time()
            results = validate_database_schema(self.db_path, verbose=False)
            elapsed_ms = (time.time() - start) * 1000

            self.logger.log_performance("Schema Validation", elapsed_ms)

            # Store results
            self.current_results['schema'] = results

            # Update tree
            status = "✓ PASS" if results['failed'] == 0 else "✗ FAIL"
            details = f"{results['schema_type']} schema"

            self.root.after(0, lambda: self.results_tree.insert(
                "", tk.END,
                values=("Tier 1: Schema", status, results['passed'],
                       results['failed'], details),
                tags=("pass" if results['failed'] == 0 else "fail",)
            ))

            # Log summary
            self._log(f"  Schema Type: {results['schema_type']}")
            self._log(f"  ✓ Passed: {results['passed']}")
            self._log(f"  ✗ Failed: {results['failed']}")

            self.logger.log_validator_end("Tier 1", "Schema Validation",
                                         results['passed'], results['failed'])

            # Log failures
            if results['failed'] > 0:
                self._log("\n  Failed checks:")
                for check in results['checks']:
                    if not check['passed']:
                        self._log(f"    ✗ {check['name']}: {check['message']}")
                        self.logger.warning(f"Schema check failed: {check['name']} - {check['message']}")

        except Exception as e:
            self._log(f"  ❌ Error: {str(e)}")
            self.logger.error(f"Schema validation error: {str(e)}", exc_info=True)
            self.current_results['schema'] = {'error': str(e)}

    def _run_geometry_validation(self):
        """Run Tier 2 geometry validation"""
        try:
            self._log("\n[Tier 2: Geometry Validation]")
            self.logger.log_validator_start("Tier 2", "Geometry Validation")

            # Call validator
            import time
            start = time.time()
            results = validate_database_geometries(self.db_path, verbose=False)
            elapsed_ms = (time.time() - start) * 1000

            self.logger.log_performance("Geometry Validation", elapsed_ms)

            # Store results
            self.current_results['geometry'] = results

            # Update tree
            status = "✓ PASS" if results['failed'] == 0 else "✗ FAIL"
            details = f"{results['validated']:,} geometries checked"

            self.root.after(0, lambda: self.results_tree.insert(
                "", tk.END,
                values=("Tier 2: Geometry", status, results['passed'],
                       results['failed'], details),
                tags=("pass" if results['failed'] == 0 else "fail",)
            ))

            # Log summary
            self._log(f"  Total geometries: {results['total']:,}")
            self._log(f"  Validated: {results['validated']:,}")
            self._log(f"  ✓ Passed: {results['passed']:,}")
            self._log(f"  ✗ Failed: {results['failed']:,}")

            self.logger.log_validator_end("Tier 2", "Geometry Validation",
                                         results['passed'], results['failed'])

            # Log first few failures
            if results['failed'] > 0 and 'failures' in results:
                self._log(f"\n  First {min(5, len(results['failures']))} failures:")
                for failure in results['failures'][:5]:
                    self._log(f"    • {failure['guid']}")
                    self.logger.warning(f"Geometry issue: {failure['guid']}")
                    for msg in failure['failures'][:2]:
                        self._log(f"      └─ {msg}")

        except Exception as e:
            self._log(f"  ❌ Error: {str(e)}")
            self.logger.error(f"Geometry validation error: {str(e)}", exc_info=True)
            self.current_results['geometry'] = {'error': str(e)}

    def _run_visualization_validation(self):
        """Run Tier 2.5 visualization validation using CLI"""
        try:
            self._log("\n[Tier 2.5: Visualization Validation]")
            self._log("  Running visualization validator...")
            self.logger.log_validator_start("Tier 2.5", "Visualization Validation")

            # Import and run the test script
            from bonsai_tester.validators.visualization_validator import (
                analyze_rotation_distribution,
                analyze_geometry_quality,
                analyze_discipline_colors,
                VisualizationReport
            )

            # Run analyses
            import time
            start = time.time()
            rotation_stats = analyze_rotation_distribution(self.db_path, verbose=False)
            geometry_stats = analyze_geometry_quality(self.db_path, verbose=False)
            discipline_stats = analyze_discipline_colors(self.db_path, verbose=False)
            elapsed_ms = (time.time() - start) * 1000

            self.logger.log_performance("Visualization Validation", elapsed_ms)

            # Build summary
            results = {
                'rotation_stats': rotation_stats,
                'geometry_stats': geometry_stats,
                'discipline_colors': discipline_stats,
                'total_elements': geometry_stats.get('total_elements', 0),
                'parametric_shapes': geometry_stats.get('detailed_geometry_count', 0),
                'simple_boxes': geometry_stats.get('simple_box_count', 0),
            }

            # Store results
            self.current_results['visualization'] = results

            # Calculate pass/fail
            passed = 0
            failed = 0

            # Check rotation diversity
            if rotation_stats['unique_angles'] > 10:
                passed += 1
            else:
                failed += 1

            # Check parametric shapes
            parametric_pct = (results['parametric_shapes'] / max(results['total_elements'], 1)) * 100
            if parametric_pct > 50:
                passed += 1
            else:
                failed += 1

            # Check discipline colors
            if discipline_stats.get('has_standard_codes', False):
                passed += 1
            else:
                failed += 1

            # Update tree
            status = "✓ PASS" if failed == 0 else "⚠ WARNING"
            details = f"{parametric_pct:.1f}% parametric shapes"

            self.root.after(0, lambda: self.results_tree.insert(
                "", tk.END,
                values=("Tier 2.5: Visualization", status, passed,
                       failed, details),
                tags=("pass" if failed == 0 else "warn",)
            ))

            # Log summary
            self._log(f"  Unique rotation angles: {rotation_stats['unique_angles']}")
            self._log(f"  Parametric shapes: {results['parametric_shapes']:,} ({parametric_pct:.1f}%)")
            self._log(f"  Simple boxes: {results['simple_boxes']:,}")
            self._log(f"  Discipline codes: {discipline_stats.get('unique_disciplines', 0)} unique")

            self.logger.log_validator_end("Tier 2.5", "Visualization Validation",
                                         passed, failed)

            # Log warnings if any
            if failed > 0:
                if rotation_stats['unique_angles'] <= 10:
                    self.logger.warning(f"Low rotation diversity: {rotation_stats['unique_angles']} unique angles")
                if parametric_pct <= 50:
                    self.logger.warning(f"Low parametric shapes: {parametric_pct:.1f}%")

        except Exception as e:
            self._log(f"  ❌ Error: {str(e)}")
            self.logger.error(f"Visualization validation error: {str(e)}", exc_info=True)
            import traceback
            self._log(traceback.format_exc())
            self.current_results['visualization'] = {'error': str(e)}

    def _update_schema_visualization(self):
        """Update schema visualization"""
        if 'schema' not in self.current_results:
            return

        results = self.current_results['schema']

        # Clear summary frame
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        # Create summary labels
        ttk.Label(self.summary_frame, text="Schema Validation Results",
                 style="SubHeader.TLabel").pack(pady=10)

        stats_frame = ttk.Frame(self.summary_frame)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        ttk.Label(stats_frame, text=f"Schema Type: {results.get('schema_type', 'Unknown')}",
                 font=("Arial", 12)).grid(row=0, column=0, columnspan=2, pady=10)

        ttk.Label(stats_frame, text="Passed:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.E, padx=5)
        ttk.Label(stats_frame, text=str(results.get('passed', 0)),
                 style="Pass.TLabel").grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(stats_frame, text="Failed:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.E, padx=5)
        ttk.Label(stats_frame, text=str(results.get('failed', 0)),
                 style="Fail.TLabel").grid(row=2, column=1, sticky=tk.W, padx=5)

    def _update_geometry_visualization(self):
        """Update geometry visualization with charts"""
        if 'geometry' not in self.current_results:
            return

        results = self.current_results['geometry']

        # Clear geometry frame
        for widget in self.geometry_frame.winfo_children():
            widget.destroy()

        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self.geometry_frame,
                     text="Install matplotlib for charts:\npip install matplotlib",
                     foreground="gray").pack(expand=True)
            return

        # Create matplotlib figure
        fig = Figure(figsize=(8, 6))

        # Pie chart: Pass vs Fail
        ax1 = fig.add_subplot(121)
        passed = results.get('passed', 0)
        failed = results.get('failed', 0)

        if passed + failed > 0:
            ax1.pie([passed, failed], labels=['Passed', 'Failed'],
                   autopct='%1.1f%%', colors=['green', 'red'],
                   startangle=90)
            ax1.set_title('Geometry Validation Results')

        # Bar chart: Issue types
        ax2 = fig.add_subplot(122)
        issue_types = {}

        if 'failures' in results:
            for failure in results['failures']:
                for msg in failure.get('failures', []):
                    # Extract issue type from message
                    if 'degenerate' in msg.lower():
                        issue_types['Degenerate Faces'] = issue_types.get('Degenerate Faces', 0) + 1
                    elif 'duplicate' in msg.lower():
                        issue_types['Duplicate Vertices'] = issue_types.get('Duplicate Vertices', 0) + 1
                    elif 'manifold' in msg.lower():
                        issue_types['Non-Manifold'] = issue_types.get('Non-Manifold', 0) + 1
                    else:
                        issue_types['Other'] = issue_types.get('Other', 0) + 1

        if issue_types:
            ax2.bar(issue_types.keys(), issue_types.values(), color='orange')
            ax2.set_title('Issue Types')
            ax2.set_ylabel('Count')
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

        fig.tight_layout()

        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.geometry_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _update_discipline_visualization(self):
        """Update discipline/visualization charts"""
        if 'visualization' not in self.current_results:
            return

        results = self.current_results['visualization']

        # Clear discipline frame
        for widget in self.discipline_frame.winfo_children():
            widget.destroy()

        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self.discipline_frame,
                     text="Install matplotlib for charts:\npip install matplotlib",
                     foreground="gray").pack(expand=True)
            return

        # Create matplotlib figure
        fig = Figure(figsize=(8, 6))

        # Pie chart: Parametric vs Simple Boxes
        ax1 = fig.add_subplot(121)
        parametric = results.get('parametric_shapes', 0)
        simple = results.get('simple_boxes', 0)

        if parametric + simple > 0:
            ax1.pie([parametric, simple], labels=['Parametric', 'Simple Boxes'],
                   autopct='%1.1f%%', colors=['green', 'orange'],
                   startangle=90)
            ax1.set_title('Geometry Complexity')

        # Bar chart: Rotation distribution
        ax2 = fig.add_subplot(122)
        rotation_stats = results.get('rotation_stats', {})
        unique_angles = rotation_stats.get('unique_angles', 0)
        total_elements = results.get('total_elements', 1)

        diversity_pct = (unique_angles / max(total_elements, 1)) * 100

        ax2.bar(['Unique Angles', 'Total Elements'], [unique_angles, total_elements],
               color=['blue', 'gray'])
        ax2.set_title(f'Rotation Diversity ({diversity_pct:.1f}%)')
        ax2.set_ylabel('Count')

        fig.tight_layout()

        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.discipline_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _update_all_visualizations(self):
        """Update all visualization tabs"""
        self._update_schema_visualization()
        self._update_geometry_visualization()
        self._update_discipline_visualization()
        self._update_stats_table()
        self._create_3d_preview()

    def _update_stats_table(self):
        """Update detailed stats table"""
        # Clear stats frame
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        # Create tree for detailed stats
        columns = ("Category", "Metric", "Value")
        stats_tree = ttk.Treeview(self.stats_frame, columns=columns,
                                 show='tree headings', height=20)

        for col in columns:
            stats_tree.heading(col, text=col)

        stats_tree.column("#0", width=50)
        stats_tree.column("Category", width=150)
        stats_tree.column("Metric", width=200)
        stats_tree.column("Value", width=150)

        # Populate with results
        if 'schema' in self.current_results:
            schema_node = stats_tree.insert("", tk.END, text="",
                                           values=("Schema", "", ""))
            results = self.current_results['schema']
            stats_tree.insert(schema_node, tk.END, text="",
                            values=("", "Schema Type", results.get('schema_type', 'Unknown')))
            stats_tree.insert(schema_node, tk.END, text="",
                            values=("", "Passed Checks", results.get('passed', 0)))
            stats_tree.insert(schema_node, tk.END, text="",
                            values=("", "Failed Checks", results.get('failed', 0)))

        if 'geometry' in self.current_results:
            geom_node = stats_tree.insert("", tk.END, text="",
                                         values=("Geometry", "", ""))
            results = self.current_results['geometry']
            stats_tree.insert(geom_node, tk.END, text="",
                            values=("", "Total Geometries", f"{results.get('total', 0):,}"))
            stats_tree.insert(geom_node, tk.END, text="",
                            values=("", "Validated", f"{results.get('validated', 0):,}"))
            stats_tree.insert(geom_node, tk.END, text="",
                            values=("", "Passed", f"{results.get('passed', 0):,}"))
            stats_tree.insert(geom_node, tk.END, text="",
                            values=("", "Failed", f"{results.get('failed', 0):,}"))

        if 'visualization' in self.current_results:
            viz_node = stats_tree.insert("", tk.END, text="",
                                        values=("Visualization", "", ""))
            results = self.current_results['visualization']
            rotation_stats = results.get('rotation_stats', {})

            stats_tree.insert(viz_node, tk.END, text="",
                            values=("", "Total Elements", f"{results.get('total_elements', 0):,}"))
            stats_tree.insert(viz_node, tk.END, text="",
                            values=("", "Unique Rotation Angles", rotation_stats.get('unique_angles', 0)))
            stats_tree.insert(viz_node, tk.END, text="",
                            values=("", "Parametric Shapes", f"{results.get('parametric_shapes', 0):,}"))
            stats_tree.insert(viz_node, tk.END, text="",
                            values=("", "Simple Boxes", f"{results.get('simple_boxes', 0):,}"))

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.stats_frame, orient=tk.VERTICAL,
                                 command=stats_tree.yview)
        stats_tree.configure(yscrollcommand=scrollbar.set)

        stats_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        # Expand all nodes
        for item in stats_tree.get_children():
            stats_tree.item(item, open=True)

    def _finalize_test_run(self):
        """Finalize test run and re-enable controls"""
        self.is_running = False
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_bar.stop()

        # Update status with summary
        total_tests = len(self.current_results)
        self._update_status(f"Tests completed: {total_tests} validators run")

        # Configure tree tags
        self.results_tree.tag_configure("pass", foreground="green")
        self.results_tree.tag_configure("fail", foreground="red")
        self.results_tree.tag_configure("warn", foreground="orange")

    def _show_test_details(self, event):
        """Show detailed results for selected test"""
        selection = self.results_tree.selection()
        if not selection:
            return

        item = self.results_tree.item(selection[0])
        test_name = item['values'][0]

        # Show details in message box
        details = f"Detailed results for: {test_name}\n\n"

        # Find matching results
        if 'Schema' in test_name and 'schema' in self.current_results:
            results = self.current_results['schema']
            details += f"Schema Type: {results.get('schema_type', 'Unknown')}\n"
            details += f"Passed: {results.get('passed', 0)}\n"
            details += f"Failed: {results.get('failed', 0)}\n\n"

            if 'checks' in results:
                details += "Check Details:\n"
                for check in results['checks']:
                    status = "✓" if check['passed'] else "✗"
                    details += f"{status} {check['name']}: {check['message']}\n"

        elif 'Geometry' in test_name and 'geometry' in self.current_results:
            results = self.current_results['geometry']
            details += f"Total: {results.get('total', 0):,}\n"
            details += f"Validated: {results.get('validated', 0):,}\n"
            details += f"Passed: {results.get('passed', 0):,}\n"
            details += f"Failed: {results.get('failed', 0):,}\n\n"

            if results.get('failed', 0) > 0 and 'failures' in results:
                details += f"First 10 Failures:\n"
                for i, failure in enumerate(results['failures'][:10], 1):
                    details += f"\n{i}. {failure['guid']}\n"
                    for msg in failure.get('failures', [])[:3]:
                        details += f"   - {msg}\n"

        # Show in dialog
        msg_window = tk.Toplevel(self.root)
        msg_window.title(f"Details: {test_name}")
        msg_window.geometry("600x400")

        text_widget = scrolledtext.ScrolledText(msg_window, wrap=tk.WORD,
                                               font=("Consolas", 9))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(1.0, details)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(msg_window, text="Close",
                  command=msg_window.destroy).pack(pady=5)

    def _create_3d_preview(self):
        """Create 3D preview interface"""
        if not self.db_path:
            return

        # Clear preview frame
        for widget in self.preview_frame.winfo_children():
            widget.destroy()

        # Create control panel
        control_panel = ttk.Frame(self.preview_frame)
        control_panel.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_panel, text="Select Element:",
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # Find interesting elements
        try:
            elements = find_interesting_elements(self.db_path, limit=20)

            if not elements:
                ttk.Label(self.preview_frame,
                         text="No suitable elements found for preview",
                         foreground="gray").pack(expand=True)
                return

            # Element selector
            element_names = [e['display_name'] for e in elements]
            self.selected_element_var = tk.StringVar(value=element_names[0])

            element_combo = ttk.Combobox(control_panel,
                                        textvariable=self.selected_element_var,
                                        values=element_names,
                                        width=50,
                                        state="readonly")
            element_combo.pack(side=tk.LEFT, padx=5)

            # Preview button
            ttk.Button(control_panel, text="Show 3D",
                      command=lambda: self._show_element_3d(elements)).pack(side=tk.LEFT, padx=5)

            ttk.Button(control_panel, text="Show Wireframe",
                      command=lambda: self._show_element_wireframe(elements)).pack(side=tk.LEFT, padx=5)

            ttk.Button(control_panel, text="Show 2D (Top)",
                      command=lambda: self._show_element_2d(elements)).pack(side=tk.LEFT, padx=5)

            # Canvas/plot area
            self.preview_canvas_frame = ttk.Frame(self.preview_frame)
            self.preview_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Show first element by default
            self._show_element_3d(elements)

        except Exception as e:
            ttk.Label(self.preview_frame,
                     text=f"Error loading elements: {str(e)}",
                     foreground="red").pack(expand=True)
            self._log(f"3D Preview error: {str(e)}")

    def _show_element_3d(self, elements):
        """Show selected element in 3D"""
        selected_name = self.selected_element_var.get()
        selected_elem = next((e for e in elements if e['display_name'] == selected_name), None)

        if not selected_elem:
            return

        # Log 3D preview start
        self.logger.log_3d_preview_start(selected_elem['guid'], selected_elem['ifc_class'])

        # Clear canvas
        for widget in self.preview_canvas_frame.winfo_children():
            widget.destroy()

        try:
            # Extract geometry
            geometry = extract_geometry_from_db(self.db_path, selected_elem['guid'])

            if not geometry:
                ttk.Label(self.preview_canvas_frame,
                         text="No geometry data found",
                         foreground="red").pack(expand=True)
                self.logger.warning(f"No geometry data found for {selected_elem['guid']}")
                return

            # Analyze shape
            analysis = analyze_geometry_shape(geometry)

            # Log preview result
            self.logger.log_3d_preview_result(
                geometry['vertex_count'],
                geometry['face_count'],
                analysis.get('quality')
            )

            # Info panel
            info_frame = ttk.Frame(self.preview_canvas_frame)
            info_frame.pack(fill=tk.X, pady=5)

            ttk.Label(info_frame, text=f"Quality: {analysis.get('quality', 'UNKNOWN')}",
                     font=("Arial", 10, "bold"),
                     foreground="green" if analysis.get('quality') == 'PARAMETRIC' else "orange").pack(side=tk.LEFT, padx=10)

            ttk.Label(info_frame, text=f"Shape: {analysis.get('shape_type', 'unknown')}").pack(side=tk.LEFT, padx=10)
            ttk.Label(info_frame, text=f"Vertices: {geometry['vertex_count']:,}").pack(side=tk.LEFT, padx=10)
            ttk.Label(info_frame, text=f"Faces: {geometry['face_count']:,}").pack(side=tk.LEFT, padx=10)

            if MATPLOTLIB_AVAILABLE:
                # Create 3D plot
                fig = Figure(figsize=(8, 6))
                ax = fig.add_subplot(111, projection='3d')

                plot_geometry_3d(geometry, ax)

                # Embed in tkinter
                canvas = FigureCanvasTkAgg(fig, master=self.preview_canvas_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            else:
                # Fallback to 2D projection
                ttk.Label(self.preview_canvas_frame,
                         text="Install matplotlib for 3D view: pip install matplotlib",
                         foreground="orange").pack(pady=10)
                self._show_element_2d(elements)

        except Exception as e:
            ttk.Label(self.preview_canvas_frame,
                     text=f"Error displaying geometry: {str(e)}",
                     foreground="red").pack(expand=True)
            self._log(f"3D display error: {str(e)}")
            self.logger.error(f"3D preview error for {selected_elem['guid']}: {str(e)}", exc_info=True)
            import traceback
            self._log(traceback.format_exc())

    def _show_element_wireframe(self, elements):
        """Show selected element as wireframe"""
        selected_name = self.selected_element_var.get()
        selected_elem = next((e for e in elements if e['display_name'] == selected_name), None)

        if not selected_elem:
            return

        # Clear canvas
        for widget in self.preview_canvas_frame.winfo_children():
            widget.destroy()

        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self.preview_canvas_frame,
                     text="Install matplotlib for wireframe view: pip install matplotlib",
                     foreground="orange").pack(expand=True)
            return

        try:
            geometry = extract_geometry_from_db(self.db_path, selected_elem['guid'])

            if not geometry:
                ttk.Label(self.preview_canvas_frame,
                         text="No geometry data found",
                         foreground="red").pack(expand=True)
                return

            # Create wireframe plot
            fig = Figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')

            plot_wireframe(geometry, ax)

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=self.preview_canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            ttk.Label(self.preview_canvas_frame,
                     text=f"Error displaying wireframe: {str(e)}",
                     foreground="red").pack(expand=True)
            self._log(f"Wireframe error: {str(e)}")

    def _show_element_2d(self, elements):
        """Show selected element as 2D projection"""
        selected_name = self.selected_element_var.get()
        selected_elem = next((e for e in elements if e['display_name'] == selected_name), None)

        if not selected_elem:
            return

        # Clear canvas
        for widget in self.preview_canvas_frame.winfo_children():
            widget.destroy()

        try:
            geometry = extract_geometry_from_db(self.db_path, selected_elem['guid'])

            if not geometry:
                ttk.Label(self.preview_canvas_frame,
                         text="No geometry data found",
                         foreground="red").pack(expand=True)
                return

            # Create tkinter canvas for 2D projection
            canvas = tk.Canvas(self.preview_canvas_frame, bg="white",
                             width=600, height=600)
            canvas.pack(fill=tk.BOTH, expand=True)

            plot_2d_projection(geometry, canvas, width=600, height=600)

        except Exception as e:
            ttk.Label(self.preview_canvas_frame,
                     text=f"Error displaying 2D projection: {str(e)}",
                     foreground="red").pack(expand=True)
            self._log(f"2D projection error: {str(e)}")

    # ===== UTILITY METHODS =====

    def _log(self, message):
        """Add message to log output"""
        self.root.after(0, lambda: self.log_text.insert(tk.END, message + "\n"))
        self.root.after(0, lambda: self.log_text.see(tk.END))

    def _update_status(self, message):
        """Update status bar"""
        self.root.after(0, lambda: self.status_label.config(text=message))

    def _on_closing(self):
        """Cleanup on window close"""
        self.logger.info("User closed GUI application")
        self.logger.section("BONSAITESTER GUI SHUTDOWN")
        close_logger()
        self.root.destroy()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()
    app = BonsaiTesterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
