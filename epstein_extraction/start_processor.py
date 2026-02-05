"""
Quick start script for continuous processor with SQLite support
This is a simplified version that works with SQLite
"""
import sys
import os
from pathlib import Path

# Set environment to use simple SQLite schema
os.environ['DB_TYPE'] = 'sqlite'
os.environ['USE_SIMPLE_SCHEMA'] = 'true'

# Now import and run
from continuous_processor import main

if __name__ == "__main__":
    print("=" * 70)
    print("EPSTEIN DOCUMENT EXTRACTION - CONTINUOUS PROCESSOR")
    print("=" * 70)
    print()
    print("Using SQLite database (simplified schema)")
    print("Processing files from: DataSet_9")
    print("Scans every 30 seconds, processes in batches of 50")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    main()
