#!/usr/bin/env python3
"""
Fix LEAN configuration to use local data only
"""
import json
import sys
from pathlib import Path

def main():
    lean_json_path = Path("/home/ahmed/TheUltimate/backend/lean/lean.json")
    
    # Read the current config
    with open(lean_json_path, 'r') as f:
        config = json.load(f)
    
    # Update configuration for local data
    config["polygon-api-key"] = ""
    config["id"] = "LocalDataFeed"
    
    # Set data provider to default file system provider
    config["data-provider"] = "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider"
    
    # Remove Polygon-specific entries
    if "data-downloader" in config and "Polygon" in str(config.get("data-downloader", "")):
        del config["data-downloader"]
    
    if "polygon-license-type" in config:
        del config["polygon-license-type"]
    
    # Ensure backtesting environment uses FileSystemDataFeed
    if "environments" in config and "backtesting" in config["environments"]:
        config["environments"]["backtesting"]["data-feed-handler"] = "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed"
        # Remove any Polygon history providers
        if "history-provider" in config["environments"]["backtesting"]:
            providers = config["environments"]["backtesting"]["history-provider"]
            if isinstance(providers, list):
                config["environments"]["backtesting"]["history-provider"] = [
                    p for p in providers if "Polygon" not in p
                ]
                # Ensure we have at least one provider
                if not config["environments"]["backtesting"]["history-provider"]:
                    config["environments"]["backtesting"]["history-provider"] = [
                        "QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider"
                    ]
    
    # Write back the updated config
    with open(lean_json_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    print("Successfully configured LEAN for local data only")
    print(f"- Set data-provider to: {config.get('data-provider')}")
    print(f"- Set id to: {config.get('id')}")
    print(f"- Removed Polygon references")

if __name__ == "__main__":
    main()