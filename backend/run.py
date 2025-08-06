#!/usr/bin/env python3
"""
Run the FastAPI stock screener application.

This script starts the Uvicorn server with the FastAPI app.
"""

import uvicorn
import os
import sys
import socket

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "Unable to determine"

if __name__ == "__main__":
    # Print access information
    local_ip = get_local_ip()
    print("\n🚀 Stock Screener API Server")
    print("="*50)
    print("📡 Server is accessible from:")
    print(f"   - Localhost:  http://localhost:8000")
    print(f"   - Local IP:   http://{local_ip}:8000")
    print(f"   - Public IP:  http://34.125.88.131:8000")
    print("📚 API Docs:     http://localhost:8000/docs")
    print("="*50 + "\n")
    
    # Run with reload in development
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )