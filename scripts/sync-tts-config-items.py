#!/usr/bin/env python3
"""
Sync TTS worker config_items to pick up new fields from expanded model.

This script manually triggers sync_config_items() for tts-worker to populate
the config_items table with all 24 fields from the expanded TTSWorkerConfig model.
"""

import asyncio
import sys
from pathlib import Path

# Add tars-core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "tars-core" / "src"))

from tars.config.database import ConfigDatabase
from tars.config.models import TTSWorkerConfig
from tars.config.metadata import extract_field_metadata


async def main():
    """Sync TTS worker config items."""
    db_path = Path("/data/config/config.db")
    
    # For local testing, use a test path
    if not db_path.exists():
        db_path = Path("./config.db.test")
        print(f"⚠️  Production DB not found, using test path: {db_path}")
    
    print(f"📦 Connecting to database: {db_path}")
    db = ConfigDatabase(str(db_path))
    await db.connect()
    
    try:
        # Get current tts-worker config
        print("📖 Reading current tts-worker configuration...")
        config_data = await db.get_service_config("tts-worker")
        
        if not config_data:
            print("❌ tts-worker configuration not found in database")
            return 1
        
        print(f"   Found config version {config_data.version} with {len(config_data.config)} fields")
        
        # Get current field keys from database
        items = await db.search_config_items(service_filter="tts-worker")
        current_keys = {item.key for item in items}
        print(f"   Current config_items: {len(current_keys)} fields")
        print(f"   Keys: {sorted(current_keys)}")
        
        # Expand config to include all model fields with defaults
        print("\n🔧 Expanding configuration with new fields from model...")
        model = TTSWorkerConfig()
        full_config = model.model_dump()
        
        # Preserve existing values
        for key, value in config_data.config.items():
            full_config[key] = value
        
        print(f"   Expanded config: {len(full_config)} fields")
        
        # Extract metadata for all fields
        print("📝 Extracting field metadata...")
        metadata = extract_field_metadata(TTSWorkerConfig, "tts-worker")
        print(f"   Metadata entries: {len(metadata)}")
        
        # Sync config_items (this deletes old items and inserts all fields)
        print("\n🔄 Syncing config_items table...")
        await db.sync_config_items("tts-worker", full_config, metadata)
        
        # Update service config with expanded values
        print("💾 Updating service config...")
        new_version = await db.update_service_config(
            service="tts-worker",
            config=full_config,
            expected_version=config_data.version,
        )
        
        # Verify
        print("\n✅ Verification:")
        items_after = await db.search_config_items(service_filter="tts-worker")
        after_keys = {item.key for item in items_after}
        print(f"   Config items after sync: {len(items_after)} fields")
        print(f"   Keys: {sorted(after_keys)}")
        print(f"   New version: {new_version}")
        
        added = after_keys - current_keys
        if added:
            print(f"   ➕ Added: {sorted(added)}")
        
        removed = current_keys - after_keys
        if removed:
            print(f"   ➖ Removed: {sorted(removed)}")
        
        print("\n🎉 TTS worker config_items synced successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
