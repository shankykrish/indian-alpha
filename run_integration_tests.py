import os
import sys
import json
import shutil
import asyncio
from datetime import datetime, timedelta
from loguru import logger

# Inject project root path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from indian_alpha.config import BASE_STATE_DIR, HEARTBEAT_FILE
from indian_alpha.providers.loader import get_active_provider, reset_active_provider
from indian_alpha.providers.zerodha import ZerodhaProvider
from indian_alpha.observability.heartbeat import write_heartbeat

# Define temp backups directory to ensure absolute zero side-effects
BACKUP_DIR = os.path.join(BASE_STATE_DIR, "backups_temp")

def backup_state():
    """Backs up active production session files before running tests."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for filename in ["zerodha_session.json", "heartbeat.json"]:
        source = os.path.join(BASE_STATE_DIR, filename)
        if os.path.exists(source):
            shutil.copy(source, os.path.join(BACKUP_DIR, filename))
            logger.info(f"Backed up {filename} to temporary directory.")

def restore_state():
    """Restores active production session files after tests finish."""
    for filename in ["zerodha_session.json", "heartbeat.json"]:
        backup = os.path.join(BACKUP_DIR, filename)
        target = os.path.join(BASE_STATE_DIR, filename)
        if os.path.exists(backup):
            shutil.copy(backup, target)
            logger.info(f"Restored original {filename} successfully.")
        elif os.path.exists(target):
            os.remove(target)
            logger.info(f"Cleaned up temporary test {filename}.")
            
    if os.path.exists(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR)
        logger.info("Removed temporary backups directory.")

async def test_heartbeat_telemetry():
    """Test Case 1: Verifies that writing a heartbeat works and sleep updates are within threshold."""
    logger.info("Executing Test Case 1: Heartbeat Telemetry & Sleep Loop Simulation...")
    
    # 1. Write an initial heartbeat
    write_heartbeat("standby", "healthy")
    
    # Verify file exists
    assert os.path.exists(HEARTBEAT_FILE), "Heartbeat file was not created!"
    
    with open(HEARTBEAT_FILE, "r") as f:
        hb = json.load(f)
        
    assert hb.get("status") == "healthy", "Heartbeat status mismatch!"
    assert hb.get("mode") == "standby", "Heartbeat mode mismatch!"
    
    # 2. Simulate sleep tick logic (update heartbeat under 90s)
    hb_time = datetime.fromisoformat(hb.get("timestamp"))
    latency = (datetime.now() - hb_time).total_seconds()
    
    logger.info(f"Observed Heartbeat latency: {latency:.2f} seconds.")
    assert latency < 90, "Telemetry failure: Heartbeat timestamp latency exceeds 90-second threshold!"
    logger.success("✔ Test Case 1: Heartbeat Telemetry & Sleep Loop Simulation - PASSED")

async def test_zerodha_expiration():
    """Test Case 2: Verifies that Zerodha session is correctly flagged as EXPIRED when timestamp is old."""
    logger.info("Executing Test Case 2: Zerodha Cache Expiration Check...")
    
    session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
    
    # Write a simulated expired session (created 2 days ago)
    expired_time = (datetime.now() - timedelta(days=2)).isoformat()
    mock_data = {
        "access_token": "MOCK_EXPIRED_TOKEN_12345",
        "created_at": expired_time
    }
    with open(session_file, "w") as f:
        json.dump(mock_data, f, indent=2)
        
    # Instantiate provider and check status
    reset_active_provider()
    provider = ZerodhaProvider()
    
    is_conn = provider.is_connected()
    logger.info(f"Is connected returned: {is_conn} (Expected: False)")
    assert not is_conn, "Telemetry failure: Provider accepted an expired daily token!"
    logger.success("✔ Test Case 2: Zerodha Cache Expiration Check - PASSED")

async def test_zerodha_hot_reload():
    """Test Case 3: Verifies that the provider dynamically hot-reloads session on-demand once authenticated."""
    logger.info("Executing Test Case 3: Dynamic Session Hot-Reload & Sync Check...")
    
    session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
    
    # Start with an expired token
    expired_time = (datetime.now() - timedelta(days=2)).isoformat()
    mock_expired = {
        "access_token": "MOCK_EXPIRED_TOKEN_12345",
        "created_at": expired_time
    }
    with open(session_file, "w") as f:
        json.dump(mock_expired, f, indent=2)
        
    reset_active_provider()
    provider = ZerodhaProvider()
    
    # Confirm initially disconnected
    assert not provider.is_connected(), "Should be disconnected initially."
    
    # Simulate user logging in on Streamlit dashboard by overwriting the file with a fresh token!
    fresh_time = datetime.now().isoformat()
    mock_fresh = {
        "access_token": "MOCK_FRESH_ACTIVE_TOKEN_99999",
        "created_at": fresh_time
    }
    with open(session_file, "w") as f:
        json.dump(mock_fresh, f, indent=2)
        
    # Clear internal check cooldown to force dynamic reload
    if hasattr(provider, "_last_session_check"):
        provider._last_session_check = datetime.min
        
    # Trigger checking again and confirm dynamic hot-reload worked!
    is_conn = provider.is_connected()
    logger.info(f"Is connected after fresh login: {is_conn} (Expected: True)")
    assert is_conn, "Failure: Daemon failed to dynamically hot-reload newly created session token!"
    logger.success("✔ Test Case 3: Dynamic Session Hot-Reload & Sync Check - PASSED")

async def test_graceful_fallback():
    """Test Case 4: Verifies that provider gracefully falls back to Yahoo Finance feed when unauthenticated."""
    logger.info("Executing Test Case 4: Graceful Feed Fallback Verification...")
    
    # Ensure unauthenticated state
    session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
    if os.path.exists(session_file):
        os.remove(session_file)
        
    reset_active_provider()
    provider = get_active_provider()
    
    logger.info("Querying historical OHLCV data for RELIANCE.NS under unauthenticated status...")
    
    # Execute query
    now = datetime.now()
    start = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    
    df = await provider.fetch_ohlcv("RELIANCE.NS", start, end)
    
    assert not df.empty, "Feed failure: Reverted Yahoo fallback failed to return valid price data!"
    logger.info(f"Successfully retrieved {len(df)} candles for RELIANCE.NS via Yahoo fallback.")
    logger.success("✔ Test Case 4: Graceful Feed Fallback Verification - PASSED")

async def test_e2e_mock_loop():
    """Test Case 5: Runs a full simulated cycle of the background worker daemon in active market mode."""
    logger.info("Executing Test Case 5: End-to-End FAST_RUN Loop Verification...")
    
    from indian_alpha.run import IndianAlphaWorker
    
    # Set dry-run flags in environment
    os.environ["FAST_RUN"] = "true"
    
    worker = IndianAlphaWorker()
    
    logger.info("Starting mock worker execution cycle...")
    try:
        await worker.run()
        logger.success("✔ Test Case 5: End-to-End FAST_RUN Loop Verification - PASSED")
    except Exception as e:
        logger.error(f"E2E loop execution failed: {e}")
        raise e

async def main():
    logger.info("Initializing Indian-Alpha Integration & Simulation Test Suite...")
    
    # Backup active state to avoid any side-effects
    backup_state()
    
    tests_failed = 0
    try:
        # Run test blocks sequentially
        await test_heartbeat_telemetry()
        print("-" * 60)
        await test_zerodha_expiration()
        print("-" * 60)
        await test_zerodha_hot_reload()
        print("-" * 60)
        await test_graceful_fallback()
        print("-" * 60)
        await test_e2e_mock_loop()
        
        logger.success("\n============================================================")
        logger.success("🚀 ALL INTEGRATION AND SIMULATION TESTS COMPLETED SUCCESSFULLY!")
        logger.success("============================================================")
    except Exception as e:
        logger.critical(f"\n❌ Test suite execution failed: {e}")
        tests_failed = 1
    finally:
        # Restore active state
        restore_state()
        
    sys.exit(tests_failed)

if __name__ == "__main__":
    asyncio.run(main())
