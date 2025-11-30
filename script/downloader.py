#!/usr/bin/env python3
"""Wrapper script kept for backward compatibility.

This module delegates to the refactored `bili_downloader` package.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path when running the script directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from bili_downloader.cli import main


if __name__ == '__main__':
    main()

