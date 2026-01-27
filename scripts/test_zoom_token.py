#!/usr/bin/env python3
"""Quick test to check if Zoom token can be fetched (tests VPN/network connectivity)"""
import sys
sys.path.insert(0, '.')

from scripts.zoom_fetcher import get_zoom_access_token

print("Testing Zoom token fetch...")
token = get_zoom_access_token()

if token:
    print(f"✓ Success! Got token: {token[:20]}...")
else:
    print("✗ Failed to get Zoom token")
    sys.exit(1)
