#!/usr/bin/env python3
"""
BonsaiTester Logging Module
============================

Manages log files and HTML report generation.
Logs are saved in a 'logs/' subdirectory in the database directory.

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List


class BonsaiLogger:
    """Logger that writes to both console and file in DB directory's logs/ subfolder"""

    def __init__(self, db_path: Path, mode: str = 'geometry'):
        """
        Initialize logger.

        Args:
            db_path: Path to database being tested
            mode: Test mode (fast/geometry/full)
        """
        self.db_path = db_path
        self.db_dir = db_path.parent
        self.mode = mode
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create logs subdirectory in database directory
        self.logs_dir = self.db_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # Create log filename based on database name and timestamp
        db_name = db_path.stem
        self.log_filename = f"bonsai_test_{db_name}_{self.timestamp}.log"
        self.log_path = self.logs_dir / self.log_filename

        # Open log file
        self.log_file = open(self.log_path, 'w', encoding='utf-8')

        # Write header
        self._write_header()

    def _write_header(self):
        """Write log file header"""
        header = f"""{'='*70}
BONSAI TESTER v0.1.0 - Test Log
{'='*70}
Test started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Database: {self.db_path.name}
Database path: {self.db_path}
Database size: {self.db_path.stat().st_size / (1024**2):.2f} MB
Mode: {self.mode.upper()}
{'='*70}

"""
        self.log_file.write(header)
        self.log_file.flush()

    def log(self, message: str, to_console: bool = True):
        """
        Write message to log file and optionally console.

        Args:
            message: Message to log
            to_console: If True, also print to console
        """
        self.log_file.write(message + '\n')
        self.log_file.flush()

        if to_console:
            print(message)

    def log_section(self, title: str, to_console: bool = True):
        """Log a section header"""
        separator = '='*70
        section = f"\n{separator}\n{title}\n{separator}\n"
        self.log(section, to_console)

    def log_subsection(self, title: str, to_console: bool = True):
        """Log a subsection header"""
        subsection = f"\n--- {title} ---\n"
        self.log(subsection, to_console)

    def log_results(self, results: Dict, to_console: bool = True):
        """
        Log validation results summary.

        Args:
            results: Results dictionary from validator
            to_console: If True, also print to console
        """
        summary = f"""
Total geometries: {results['total']:,}
Validated: {results['validated']:,}
✓ Passed: {results['passed']:,}
✗ Failed: {results['failed']:,}
Pass rate: {(results['passed']/results['validated']*100) if results['validated'] > 0 else 0:.1f}%
"""
        self.log(summary, to_console)

        # Log failures
        if results['failed'] > 0:
            self.log(f"\n❌ VALIDATION FAILED - {results['failed']} geometry errors\n", to_console)
            self.log("Failed elements:", to_console)
            for i, failure in enumerate(results['failures'], 1):
                self.log(f"\n  {i}. {failure['guid']}:", to_console)
                for msg in failure['failures']:
                    self.log(f"     └─ {msg}", to_console)
        else:
            self.log("\n✅ ALL GEOMETRIES VALID\n", to_console)

    def close(self):
        """Close log file"""
        footer = f"""
{'='*70}
Test completed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Log saved to: {self.log_path}
{'='*70}
"""
        self.log_file.write(footer)
        self.log_file.close()

    def get_log_path(self) -> Path:
        """Get path to log file"""
        return self.log_path


class HTMLReportGenerator:
    """Generates HTML reports from test results"""

    def __init__(self, db_path: Path, results: Dict, elapsed_time: float, mode: str = 'geometry'):
        """
        Initialize HTML report generator.

        Args:
            db_path: Path to database
            results: Validation results dictionary
            elapsed_time: Test execution time in seconds
            mode: Test mode (fast/geometry/full)
        """
        self.db_path = db_path
        self.results = results
        self.elapsed_time = elapsed_time
        self.mode = mode
        self.timestamp = datetime.now()

    def generate(self) -> Path:
        """
        Generate HTML report and save to database directory's logs subfolder.

        Returns:
            Path to generated HTML file
        """
        # Create logs subdirectory in database directory
        logs_dir = self.db_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        db_name = self.db_path.stem
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        html_filename = f"bonsai_test_{db_name}_{timestamp_str}.html"
        html_path = logs_dir / html_filename

        html_content = self._generate_html()

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return html_path

    def _generate_html(self) -> str:
        """Generate HTML content"""

        # Calculate statistics
        total = self.results['total']
        validated = self.results['validated']
        passed = self.results['passed']
        failed = self.results['failed']
        pass_rate = (passed / validated * 100) if validated > 0 else 0

        # Status color
        if failed == 0:
            status_color = '#28a745'  # Green
            status_text = '✅ ALL PASSED'
            grade = 'A+'
        elif pass_rate >= 95:
            status_color = '#5cb85c'  # Light green
            status_text = f'⚠️ {failed} FAILURES'
            grade = 'A'
        elif pass_rate >= 90:
            status_color = '#ffc107'  # Yellow
            status_text = f'⚠️ {failed} FAILURES'
            grade = 'B'
        else:
            status_color = '#dc3545'  # Red
            status_text = f'❌ {failed} FAILURES'
            grade = 'C'

        # Generate failure details HTML
        failures_html = self._generate_failures_html()

        # Generate failure type breakdown
        failure_breakdown = self._generate_failure_breakdown()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BonsaiTester Report - {self.db_path.name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}

        .status-banner {{
            background: {status_color};
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 1.5em;
            font-weight: bold;
        }}

        .content {{
            padding: 40px;
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .info-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}

        .info-card h3 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .info-card .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #333;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}

        .stat-card {{
            background: #fff;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }}

        .stat-card.passed {{
            border-color: #28a745;
            background: #f1f9f3;
        }}

        .stat-card.failed {{
            border-color: #dc3545;
            background: #fef5f5;
        }}

        .stat-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .stat-card.passed .number {{
            color: #28a745;
        }}

        .stat-card.failed .number {{
            color: #dc3545;
        }}

        .stat-card .label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .section {{
            margin: 40px 0;
        }}

        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }}

        .failure-list {{
            margin-top: 20px;
        }}

        .failure-item {{
            background: #fff;
            border: 1px solid #e9ecef;
            border-left: 4px solid #dc3545;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
        }}

        .failure-item .guid {{
            font-family: monospace;
            color: #667eea;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .failure-item .error {{
            color: #dc3545;
            margin-left: 20px;
            padding: 5px 0;
        }}

        .failure-item .error::before {{
            content: "└─ ";
            color: #999;
        }}

        .grade-badge {{
            display: inline-block;
            background: {status_color};
            color: white;
            padding: 10px 20px;
            border-radius: 50px;
            font-size: 1.5em;
            font-weight: bold;
            margin: 20px 0;
        }}

        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #28a745 0%, #5cb85c 100%);
            width: {pass_rate}%;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}

        .breakdown-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        .breakdown-table th,
        .breakdown-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }}

        .breakdown-table th {{
            background: #f8f9fa;
            color: #667eea;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.9em;
            letter-spacing: 1px;
        }}

        .breakdown-table tr:hover {{
            background: #f8f9fa;
        }}

        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 BonsaiTester Report</h1>
            <div class="subtitle">Geometry Validation Results</div>
        </div>

        <div class="status-banner">
            {status_text}
        </div>

        <div class="content">
            <div class="info-grid">
                <div class="info-card">
                    <h3>Database</h3>
                    <div class="value" style="font-size: 1.2em;">{self.db_path.name}</div>
                </div>
                <div class="info-card">
                    <h3>Test Date</h3>
                    <div class="value" style="font-size: 1.2em;">{self.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</div>
                </div>
                <div class="info-card">
                    <h3>Test Mode</h3>
                    <div class="value">{self.mode.upper()}</div>
                </div>
                <div class="info-card">
                    <h3>Execution Time</h3>
                    <div class="value">{self.elapsed_time:.2f}s</div>
                </div>
            </div>

            <div class="section">
                <h2>Quality Grade</h2>
                <div class="grade-badge">Grade: {grade}</div>
                <div class="progress-bar">
                    <div class="progress-fill">{pass_rate:.1f}% Pass Rate</div>
                </div>
            </div>

            <div class="section">
                <h2>Validation Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="number">{total:,}</div>
                        <div class="label">Total Elements</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{validated:,}</div>
                        <div class="label">Validated</div>
                    </div>
                    <div class="stat-card passed">
                        <div class="number">{passed:,}</div>
                        <div class="label">✓ Passed</div>
                    </div>
                    <div class="stat-card failed">
                        <div class="number">{failed:,}</div>
                        <div class="label">✗ Failed</div>
                    </div>
                </div>
            </div>

            {failure_breakdown}

            {failures_html}
        </div>

        <div class="footer">
            Generated by BonsaiTester v0.1.0 | Database: {self.db_path} | Size: {self.db_path.stat().st_size / (1024**2):.2f} MB
        </div>
    </div>
</body>
</html>
"""
        return html

    def _generate_failures_html(self) -> str:
        """Generate HTML for failure details"""
        if self.results['failed'] == 0:
            return ""

        failures = self.results['failures']

        html = '<div class="section">\n'
        html += '<h2>Failed Elements Details</h2>\n'
        html += '<div class="failure-list">\n'

        for i, failure in enumerate(failures, 1):
            html += '<div class="failure-item">\n'
            html += f'<div class="guid">{i}. {failure["guid"]}</div>\n'
            for error in failure['failures']:
                html += f'<div class="error">{error}</div>\n'
            html += '</div>\n'

        html += '</div>\n'
        html += '</div>\n'

        return html

    def _generate_failure_breakdown(self) -> str:
        """Generate failure type breakdown table"""
        if self.results['failed'] == 0:
            return ""

        # Count failure types
        failure_types = {}
        for failure in self.results['failures']:
            for error in failure['failures']:
                if error not in failure_types:
                    failure_types[error] = 0
                failure_types[error] += 1

        # Sort by count
        sorted_types = sorted(failure_types.items(), key=lambda x: x[1], reverse=True)

        html = '<div class="section">\n'
        html += '<h2>Failure Type Breakdown</h2>\n'
        html += '<table class="breakdown-table">\n'
        html += '<tr><th>Failure Type</th><th>Count</th><th>Percentage</th></tr>\n'

        for error_type, count in sorted_types:
            percentage = (count / self.results['failed'] * 100)
            html += f'<tr><td>{error_type}</td><td>{count:,}</td><td>{percentage:.1f}%</td></tr>\n'

        html += '</table>\n'
        html += '</div>\n'

        return html
