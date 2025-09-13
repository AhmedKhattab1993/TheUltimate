#!/usr/bin/env python3
"""
Remove Polygon references from LEAN configuration
"""
import json
import sys
from pathlib import Path

def main():
    lean_json_path = Path("/home/ahmed/TheUltimate/backend/lean/lean.json")
    
    # Read the current config
    with open(lean_json_path, 'r') as f:
        config = json.load(f)
    
    # Remove or update Polygon references
    config["polygon-api-key"] = ""
    config["id"] = "LocalDataFeed"
    
    # Remove data-downloader if it's Polygon
    if "data-downloader" in config and "Polygon" in config["data-downloader"]:
        del config["data-downloader"]
    
    # Remove polygon-license-type
    if "polygon-license-type" in config:
        del config["polygon-license-type"]
    
    # Write back the updated config
    with open(lean_json_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    print("Successfully removed Polygon references from lean.json")

if __name__ == "__main__":
    main()