import os

# Self-healing helper: Dynamically parse and load local .env variables into os.environ
env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(env_file):
    try:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ[key] = val
    except Exception as e:
        pass

# Dynamic path resolution to support both local development and Railway production
if os.path.exists("/app/state") and os.name != 'nt':
    # In Docker container (Railway)
    BASE_STATE_DIR = "/app/state"
else:
    # Local Windows workspace path
    BASE_STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "state"))

# Individual State Paths
HEARTBEAT_FILE = os.path.join(BASE_STATE_DIR, "heartbeat.json")
TRADES_FILE = os.path.join(BASE_STATE_DIR, "trades.jsonl")
RANKINGS_FILE = os.path.join(BASE_STATE_DIR, "rankings.json")
HYPOTHESES_FILE = os.path.join(BASE_STATE_DIR, "hypotheses.jsonl")
STRATEGY_FILE = os.path.join(BASE_STATE_DIR, "strategy.yaml")
GOALS_FILE = os.path.join(BASE_STATE_DIR, "goal.yaml")
REGIMES_FILE = os.path.join(BASE_STATE_DIR, "market_regimes.json")
FUNDAMENTALS_CACHE_FILE = os.path.join(BASE_STATE_DIR, "fundamentals_cache.json")
SNAPSHOTS_DIR = os.path.join(BASE_STATE_DIR, "snapshots")
SNAPSHOT_DIR = SNAPSHOTS_DIR
HISTORY_DIR = os.path.join(BASE_STATE_DIR, "history")

# Standard configuration
DEFAULT_RATE_LIMIT_DELAY = 0.5
