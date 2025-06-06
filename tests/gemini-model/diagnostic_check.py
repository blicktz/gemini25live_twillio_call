#!/usr/bin/env python3
"""
Diagnostic script to check Gemini Live API setup requirements
"""
import os
import json
import subprocess
import sys

def check_credentials():
    """Check if credentials file exists and is valid JSON"""
    creds_path = "credentials.json"
    if not os.path.exists(creds_path):
        print("❌ credentials.json not found")
        return False
    
    try:
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        print("✅ credentials.json exists and is valid JSON")
        print(f"   Project ID: {creds.get('project_id')}")
        print(f"   Service Account: {creds.get('client_email')}")
        return True
    except Exception as e:
        print(f"❌ credentials.json is invalid: {e}")
        return False

def check_billing():
    """Check if billing is enabled for the project"""
    try:
        result = subprocess.run([
            'gcloud', 'billing', 'projects', 'describe', 'twilio-gemini25-live-api'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Billing is enabled for the project")
            return True
        else:
            print("❌ Billing is not enabled for the project")
            print("   Error:", result.stderr.strip())
            return False
    except Exception as e:
        print(f"❌ Could not check billing status: {e}")
        return False

def check_apis():
    """Check if required APIs are enabled"""
    required_apis = [
        'aiplatform.googleapis.com',
        'generativelanguage.googleapis.com'
    ]
    
    try:
        result = subprocess.run([
            'gcloud', 'services', 'list', '--enabled', '--format=value(name)'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            enabled_apis = result.stdout.strip().split('\n')
            enabled_apis = [api.split('/')[-1] for api in enabled_apis if api]
            
            for api in required_apis:
                if api in enabled_apis:
                    print(f"✅ {api} is enabled")
                else:
                    print(f"❌ {api} is not enabled")
        else:
            print("❌ Could not check API status")
            return False
    except Exception as e:
        print(f"❌ Could not check APIs: {e}")
        return False

def main():
    print("🔍 Gemini Live API Diagnostic Check")
    print("=" * 40)
    
    print("\n1. Checking credentials...")
    creds_ok = check_credentials()
    
    print("\n2. Checking billing...")
    billing_ok = check_billing()
    
    print("\n3. Checking APIs...")
    check_apis()
    
    print("\n" + "=" * 40)
    if creds_ok and billing_ok:
        print("✅ All checks passed! Ready to test Gemini Live API")
    else:
        print("❌ Issues found. Please resolve the above problems.")
        if not billing_ok:
            print("\n🔗 Enable billing at:")
            print("   https://console.developers.google.com/billing/enable?project=twilio-gemini25-live-api")

if __name__ == "__main__":
    main()