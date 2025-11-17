#!/usr/bin/env python3
"""
GUI Logger - BonsaiTester
==========================

Comprehensive logging system for GUI operations.
Logs to consolelogs/ folder for debugging and monitoring.

Author: Redhuan D. Oon <red1org@gmail.com>
License: LGPL-3.0
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class GUILogger:
    """Console logger for BonsaiTester GUI"""

    def __init__(self, log_dir: str = "consolelogs"):
        """
        Initialize GUI logger.

        Args:
            log_dir: Directory for log files (default: consolelogs)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"bonsai_tester_gui_{timestamp}.log"

        # Setup logger
        self.logger = logging.getLogger('BonsaiTesterGUI')
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers = []

        # File handler (detailed)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (less verbose)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Log startup
        self.info("=" * 70)
        self.info("BonsaiTester GUI Logger Initialized")
        self.info(f"Log file: {self.log_file}")
        self.info("=" * 70)

    def debug(self, message: str):
        """Log debug message (file only)"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message (file + console)"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)

    def error(self, message: str, exc_info=None):
        """Log error message with optional exception info"""
        self.logger.error(message, exc_info=exc_info)

    def section(self, title: str):
        """Log section header"""
        self.info("")
        self.info("=" * 70)
        self.info(title)
        self.info("=" * 70)

    def subsection(self, title: str):
        """Log subsection header"""
        self.info("")
        self.info(f"--- {title} ---")

    def log_database_selection(self, db_path: Path, size_mb: float):
        """Log database selection event"""
        self.section("DATABASE SELECTION")
        self.info(f"Database: {db_path}")
        self.info(f"Size: {size_mb:.1f} MB")
        self.debug(f"Absolute path: {db_path.absolute()}")
        self.debug(f"Exists: {db_path.exists()}")
        self.debug(f"Is file: {db_path.is_file()}")

    def log_test_start(self, mode: str, tiers: list):
        """Log test execution start"""
        self.section("TEST EXECUTION START")
        self.info(f"Mode: {mode.upper()}")
        self.info(f"Tiers enabled: {', '.join(tiers)}")
        self.debug(f"Timestamp: {datetime.now().isoformat()}")

    def log_test_end(self, elapsed_seconds: float, success: bool):
        """Log test execution end"""
        self.section("TEST EXECUTION END")
        self.info(f"Duration: {elapsed_seconds:.2f} seconds")
        self.info(f"Status: {'SUCCESS' if success else 'FAILED'}")
        self.debug(f"Timestamp: {datetime.now().isoformat()}")

    def log_validator_start(self, tier: str, validator_name: str):
        """Log validator start"""
        self.subsection(f"Validator Start: {tier} - {validator_name}")
        self.debug(f"Validator: {validator_name}")
        self.debug(f"Tier: {tier}")

    def log_validator_end(self, tier: str, validator_name: str, passed: int, failed: int):
        """Log validator end"""
        self.info(f"Validator Complete: {tier} - {validator_name}")
        self.info(f"  Passed: {passed:,}")
        self.info(f"  Failed: {failed:,}")
        status = "PASS" if failed == 0 else "FAIL"
        self.info(f"  Status: {status}")

    def log_3d_preview_start(self, element_guid: str, ifc_class: str):
        """Log 3D preview action"""
        self.subsection("3D PREVIEW")
        self.info(f"Extracting geometry for: {ifc_class}")
        self.debug(f"GUID: {element_guid}")

    def log_3d_preview_result(self, vertex_count: int, face_count: int, quality: str):
        """Log 3D preview result"""
        self.info(f"Geometry extracted successfully")
        self.info(f"  Vertices: {vertex_count:,}")
        self.info(f"  Faces: {face_count:,}")
        self.info(f"  Quality: {quality}")

    def log_visualization_update(self, tab_name: str):
        """Log visualization tab update"""
        self.debug(f"Updating visualization tab: {tab_name}")

    def log_error_with_context(self, error_msg: str, context: dict):
        """Log error with contextual information"""
        self.error(f"Error: {error_msg}")
        for key, value in context.items():
            self.debug(f"  {key}: {value}")

    def log_performance(self, operation: str, duration_ms: float):
        """Log performance metric"""
        self.debug(f"Performance - {operation}: {duration_ms:.1f}ms")

    def close(self):
        """Close logger and handlers"""
        self.info("=" * 70)
        self.info("BonsaiTester GUI Logger Closing")
        self.info("=" * 70)

        for handler in self.logger.handlers:
            handler.close()

        self.logger.handlers = []

    def get_log_file(self) -> Path:
        """Get current log file path"""
        return self.log_file


# Global logger instance (singleton pattern)
_global_logger = None


def get_logger() -> GUILogger:
    """Get or create global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = GUILogger()
    return _global_logger


def close_logger():
    """Close global logger"""
    global _global_logger
    if _global_logger is not None:
        _global_logger.close()
        _global_logger = None
