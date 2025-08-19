#!/usr/bin/env python3
"""Clean up malformed screener result JSON files."""

import json
import os
from pathlib import Path

def is_valid_json(filepath):
    """Check if a file contains valid JSON."""
    try:
        with open(filepath, 'r') as f:
            json.load(f)
        return True
    except:
        return False

def main():
    results_dir = Path("/home/ahmed/TheUltimate/backend/screener_results")
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return
    
    json_files = list(results_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")
    
    valid_count = 0
    invalid_files = []
    
    for filepath in json_files:
        if is_valid_json(filepath):
            valid_count += 1
        else:
            invalid_files.append(filepath)
    
    print(f"\nValid JSON files: {valid_count}")
    print(f"Invalid JSON files: {len(invalid_files)}")
    
    if invalid_files:
        print("\nInvalid files:")
        for f in invalid_files[:10]:  # Show first 10
            print(f"  - {f.name}")
        
        if len(invalid_files) > 10:
            print(f"  ... and {len(invalid_files) - 10} more")
        
        print("\nDeleting invalid JSON files...")
        for f in invalid_files:
            f.unlink()
            print(f"Deleted: {f.name}")
        print(f"\nDeleted {len(invalid_files)} invalid files")

if __name__ == "__main__":
    main()