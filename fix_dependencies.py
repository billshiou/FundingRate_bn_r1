#!/usr/bin/env python3
"""
Dependency fix script for the funding rate trading bot
This script fixes the aiohttp/aiohappyeyeballs import issue
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{description}...")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("=== Funding Rate Bot Dependency Fix Script ===")
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Warning: Not running in a virtual environment")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Please activate your virtual environment first")
            return
    
    # Step 1: Uninstall problematic packages
    print("\nStep 1: Removing problematic packages...")
    
    packages_to_remove = [
        "aiohttp",
        "aiohappyeyeballs", 
        "python-binance"
    ]
    
    for package in packages_to_remove:
        run_command(f"pip uninstall -y {package}", f"Uninstalling {package}")
    
    # Step 2: Install compatible aiohttp version
    print("\nStep 2: Installing compatible aiohttp version...")
    if not run_command("pip install aiohttp==3.8.6", "Installing aiohttp 3.8.6"):
        print("Failed to install aiohttp, trying alternative approach...")
        if not run_command("pip install aiohttp==3.7.4", "Installing aiohttp 3.7.4"):
            print("Failed to install aiohttp. Please check your internet connection.")
            return
    
    # Step 3: Install python-binance
    print("\nStep 3: Installing python-binance...")
    if not run_command("pip install python-binance>=1.0.16", "Installing python-binance"):
        print("Failed to install python-binance")
        return
    
    # Step 4: Install other requirements
    print("\nStep 4: Installing other requirements...")
    if not run_command("pip install -r requirements.txt", "Installing requirements"):
        print("Failed to install requirements")
        return
    
    # Step 5: Test the import
    print("\nStep 5: Testing imports...")
    test_script = """
import sys
try:
    from binance.client import Client
    print("✓ python-binance import successful")
except ImportError as e:
    print(f"✗ python-binance import failed: {e}")
    sys.exit(1)

try:
    import aiohttp
    print("✓ aiohttp import successful")
except ImportError as e:
    print(f"✗ aiohttp import failed: {e}")
    sys.exit(1)

try:
    import ccxt
    print("✓ ccxt import successful")
except ImportError as e:
    print(f"✗ ccxt import failed: {e}")
    sys.exit(1)

print("✓ All critical imports successful!")
"""
    
    with open("test_imports.py", "w") as f:
        f.write(test_script)
    
    if run_command("python test_imports.py", "Testing imports"):
        print("\n=== Dependency fix completed successfully! ===")
        print("You can now run your trading bot.")
    else:
        print("\n=== Dependency fix failed ===")
        print("Please check the error messages above.")
    
    # Clean up
    if os.path.exists("test_imports.py"):
        os.remove("test_imports.py")

if __name__ == "__main__":
    main() 