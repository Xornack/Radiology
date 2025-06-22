#!/usr/bin/env python3
"""
Setup script for Video from Pictures Python application.
Handles virtual environment creation and dependency installation.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return False

def main():
    """Main setup function."""
    project_root = Path(__file__).parent
    venv_path = project_root / "venv"
    
    print("🔧 Setting up Video from Pictures Python application...")
    print(f"Project root: {project_root}")
    
    # Check if virtual environment exists
    if not venv_path.exists():
        print("Creating virtual environment...")
        if not run_command(f"python -m venv {venv_path}", "Virtual environment creation"):
            return False
    else:
        print("✅ Virtual environment already exists")
    
    # Activate virtual environment and install dependencies
    if sys.platform == "win32":
        activate_script = venv_path / "Scripts" / "activate.bat"
        pip_path = venv_path / "Scripts" / "pip"
    else:
        activate_script = venv_path / "bin" / "activate"
        pip_path = venv_path / "bin" / "pip"
    
    # Install dependencies
    requirements_file = project_root / "requirements.txt"
    if requirements_file.exists():
        install_cmd = f"{pip_path} install -r {requirements_file}"
        if not run_command(install_cmd, "Dependencies installation"):
            return False
    else:
        print("❌ requirements.txt not found")
        return False
    
    # Run tests to verify setup
    pytest_path = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "pytest"
    test_cmd = f"{pytest_path} tests/ -v"
    if not run_command(test_cmd, "Running tests"):
        print("⚠️  Tests failed, but setup may still be functional")
    
    print("\n🎉 Setup completed successfully!")
    print(f"To activate the virtual environment:")
    if sys.platform == "win32":
        print(f"  {venv_path}\\Scripts\\activate")
    else:
        print(f"  source {venv_path}/bin/activate")
    print(f"To run the application:")
    print(f"  python src/main.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
