#!/usr/bin/env python3
"""
Start both backend and frontend servers for the Stock Screener application
"""
import os
import sys
import subprocess
import time
import signal
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    END = '\033[0m'

def print_colored(message, color=Colors.BLUE):
    print(f"{color}{message}{Colors.END}")

def check_backend_deps():
    """Check if backend dependencies are installed"""
    try:
        import fastapi
        import numpy
        import httpx
        return True
    except ImportError:
        return False

def check_env_file():
    """Check if .env file exists in backend"""
    env_path = Path("backend/.env")
    if not env_path.exists():
        print_colored("Error: backend/.env file not found!", Colors.RED)
        print("Please create it from .env.example and add your Polygon API key:")
        print("  cd backend")
        print("  cp .env.example .env")
        print("  # Edit .env and add your POLYGON_API_KEY")
        return False
    return True

def install_backend_deps():
    """Install backend dependencies"""
    print_colored("Installing backend dependencies...", Colors.YELLOW)
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--user", 
        "--break-system-packages", "-r", "backend/requirements.txt"
    ])

def check_frontend_deps():
    """Check if frontend dependencies are installed"""
    return Path("frontend/node_modules").exists()

def install_frontend_deps():
    """Install frontend dependencies"""
    print_colored("Installing frontend dependencies...", Colors.YELLOW)
    subprocess.run(["npm", "install"], cwd="frontend")

def main():
    print_colored("🚀 Starting Stock Screener Application...\n", Colors.BLUE)
    
    # Check environment
    if not check_env_file():
        sys.exit(1)
    
    # Check and install dependencies if needed
    if not check_backend_deps():
        print_colored("Backend dependencies not found.", Colors.RED)
        install_backend_deps()
    
    if not check_frontend_deps():
        print_colored("Frontend dependencies not found.", Colors.RED)
        install_frontend_deps()
    
    # Store process references
    processes = []
    
    try:
        # Start backend
        print_colored("Starting backend server on http://localhost:8000...", Colors.GREEN)
        backend = subprocess.Popen(
            [sys.executable, "run.py"],
            cwd="backend",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(backend)
        
        # Wait for backend to start
        print_colored("Waiting for backend to initialize...", Colors.BLUE)
        time.sleep(5)
        
        # Start frontend
        print_colored("Starting frontend on http://localhost:5173...", Colors.GREEN)
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="frontend",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(frontend)
        
        # Print success message
        print_colored("\n✨ Stock Screener is running!", Colors.GREEN)
        print_colored("📊 Frontend:", Colors.GREEN)
        print_colored("   - Local: http://localhost:5173", Colors.GREEN)
        print_colored("   - Public: http://34.125.88.131:5173", Colors.GREEN)
        print_colored("🔧 Backend API:", Colors.GREEN)
        print_colored("   - Local: http://localhost:8000", Colors.GREEN)
        print_colored("   - Public: http://34.125.88.131:8000", Colors.GREEN)
        print_colored("📚 API Docs: http://34.125.88.131:8000/docs", Colors.GREEN)
        print_colored("\nPress Ctrl+C to stop all services\n", Colors.BLUE)
        
        # Wait for interrupt
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print_colored("\n\nShutting down services...", Colors.RED)
        
    finally:
        # Cleanup all processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
        
        print_colored("All services stopped.", Colors.YELLOW)

if __name__ == "__main__":
    main()