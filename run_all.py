import subprocess
import sys
import time
import os
import shutil
from loguru import logger

def initialize_volume_state():
    """Self-healing setup: Initializes default config files in the persistent state volume if missing."""
    logger.info("Initializing persistent state directory...")
    
    # 1. Determine the active state directory (usually /app/state in Docker/Railway)
    state_dir = "/app/state"
    if not os.path.exists(state_dir) and os.name == 'nt':
        # Local Windows fallback for development
        state_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "state"))
        
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(os.path.join(state_dir, "snapshots"), exist_ok=True)
    os.makedirs(os.path.join(state_dir, "history"), exist_ok=True)
    
    # 2. Resolve default source files
    defaults_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "indian_alpha", "defaults"))
    
    for filename in ["strategy.yaml", "goal.yaml"]:
        target_path = os.path.join(state_dir, filename)
        source_path = os.path.join(defaults_dir, filename)
        
        if not os.path.exists(target_path):
            if os.path.exists(source_path):
                shutil.copy(source_path, target_path)
                logger.info(f"Successfully copied default config {filename} -> {target_path}")
            else:
                logger.error(f"Default config source file not found at {source_path}!")
        else:
            # Check version upgrade to support seamless cloud upgrades on persistent volumes
            if filename == "strategy.yaml" and os.path.exists(source_path):
                try:
                    import yaml
                    with open(source_path, "r") as sf:
                        src_data = yaml.safe_load(sf)
                    with open(target_path, "r") as tf:
                        tgt_data = yaml.safe_load(tf)
                    
                    src_ver = int(src_data.get("version", "0"))
                    tgt_ver = int(tgt_data.get("version", "0"))
                    
                    if src_ver > tgt_ver:
                        # Archive current target file
                        history_dir = os.path.join(state_dir, "history")
                        os.makedirs(history_dir, exist_ok=True)
                        backup_name = f"strategy_v{tgt_data.get('version', '01')}.yaml"
                        backup_path = os.path.join(history_dir, backup_name)
                        shutil.copy(target_path, backup_path)
                        
                        # Copy new version
                        shutil.copy(source_path, target_path)
                        logger.info(f"Upgraded {filename} from v{tgt_ver:02d} to v{src_ver:02d} (Archived previous config to {backup_name})")
                    else:
                        logger.info(f"Config file {filename} already exists at {target_path} (Version v{tgt_ver:02d} is up to date)")
                except Exception as ve:
                    logger.error(f"Error checking version upgrade for {filename}: {ve}")
                    logger.info(f"Config file {filename} already exists at {target_path}")
            else:
                logger.info(f"Config file {filename} already exists at {target_path}")

def main():
    logger.info("Starting Indian-Alpha Orchestrator...")
    
    # Run the self-healing initialization
    initialize_volume_state()

    # 1. Start the quant background worker daemon
    logger.info("Launching worker daemon: python -m indian_alpha.run")
    worker = subprocess.Popen(
        [sys.executable, "-m", "indian_alpha.run"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    # 2. Start the Streamlit dashboard service
    logger.info("Launching Streamlit dashboard...")
    port = os.getenv("PORT", "8501")
    dashboard = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "indian_alpha/dashboard/app.py",
            "--server.port",
            port,
            "--server.address",
            "0.0.0.0"
        ],
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    logger.info(f"Processes started. Worker PID: {worker.pid}, Dashboard PID: {dashboard.pid}")

    try:
        while True:
            # Check status of both processes
            worker_code = worker.poll()
            dashboard_code = dashboard.poll()

            if worker_code is not None:
                logger.error(f"Worker process terminated unexpectedly with exit code {worker_code}. Shutting down orchestrator...")
                dashboard.terminate()
                sys.exit(worker_code)

            if dashboard_code is not None:
                logger.error(f"Dashboard process terminated unexpectedly with exit code {dashboard_code}. Shutting down orchestrator...")
                worker.terminate()
                sys.exit(dashboard_code)

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Shutting down processes gracefully...")
        worker.terminate()
        dashboard.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
