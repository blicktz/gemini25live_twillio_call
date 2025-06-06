#!/usr/bin/env python3
"""
Quick diagnostic to check what model name is being loaded from config.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.config import settings

print("🔍 Configuration Diagnostic:")
print(f"  - Environment GEMINI_MODEL: {os.getenv('GEMINI_MODEL')}")
print(f"  - Settings gemini_model: {settings.gemini_model}")
print(f"  - Project: {settings.google_cloud_project}")
print(f"  - Location: {settings.google_cloud_location}")
print(f"  - Working directory: {os.getcwd()}")
print(f"  - .env file exists: {os.path.exists('.env')}")

# Check if .env is being loaded
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'GEMINI_MODEL' in line and not line.strip().startswith('#'):
                print(f"  - .env line {i}: {line.strip()}")