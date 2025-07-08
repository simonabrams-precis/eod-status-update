#!/usr/bin/env python3
"""
Test script to verify fallback developer list functionality.
Run this to check if your fallback developer IDs are configured correctly.
"""

import os
import asyncio
from dotenv import load_dotenv
from app.utils.developers import get_fallback_developer_ids, get_developer_user_ids

# Load environment variables
load_dotenv()

async def test_fallback():
    """Test the fallback developer list functionality."""
    print("🔍 Testing Fallback Developer List Configuration")
    print("=" * 50)
    
    # Test 1: Check environment variable
    fallback_ids = os.environ.get("FALLBACK_DEVELOPER_IDS", "")
    print(f"📋 FALLBACK_DEVELOPER_IDS from environment: {fallback_ids}")
    
    # Test 2: Test the fallback function
    developer_ids = get_fallback_developer_ids()
    print(f"👥 Parsed developer IDs: {developer_ids}")
    print(f"📊 Number of developers in fallback list: {len(developer_ids)}")
    
    # Test 3: Test the main function (without Slack client)
    print("\n🔄 Testing main developer fetch function...")
    try:
        # This will fail to get usergroup but should fall back to our list
        all_developer_ids = await get_developer_user_ids()
        print(f"✅ Successfully got {len(all_developer_ids)} developers")
        print(f"📝 Developer IDs: {all_developer_ids}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Validation
    print("\n✅ Validation:")
    if developer_ids:
        print("   ✓ Fallback developer list is configured")
        for i, dev_id in enumerate(developer_ids, 1):
            print(f"   {i}. {dev_id}")
    else:
        print("   ⚠️  No fallback developers configured")
        print("   💡 Set FALLBACK_DEVELOPER_IDS in your .env file")
        print("   📝 Format: FALLBACK_DEVELOPER_IDS=U1234567890,U0987654321")

if __name__ == "__main__":
    asyncio.run(test_fallback()) 