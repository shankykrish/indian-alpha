# Indian-Alpha 🎯

A production-grade, self-learning Indian equities research, analytics, visualization, and paper trading platform optimized specifically for NSE and BSE equities.

## System Architecture

```
24x7 scheduler
↓
time-aware execution modes (Active, Post-Market, Standby)
↓
market-aware workloads (PSU cycles, Defense breakouts, Circuit Breakers)
↓
regime-aware reflections (Goal targets vs Performance metrics)
↓
visual analytics + Streamlit dashboards
```

---

## Features & Indian Market Customization

- **Indian Market Scheduling Engine**: Fully timezone-aware (`Asia/Kolkata`), NSE Holiday-aware, and Muhurat-trading-ready.
- **Cognitive Self-Learning Engine**: Analyzes simulated paper trade performance over a rolling cadence (default: 10 trades), compares outcomes against targets defined in `goal.yaml` per market regime, formulates hypotheses, and alters **exactly one** variable in `strategy.yaml` at a time. Updates are fully archived with high auditability.
- **PSU & Heavy Industries Specialization**: Detects specific momentum expansion in PSU, Defense, Capital Goods, and Railway thematic cycles.
- **Execution Simulation**: Models bid-ask slippage, market gap opens, exchange & government regulatory fees (STT, SEBI, GST, stamp duty), and rejects trades hitting **upper or lower circuits** (price bands).
- **Multi-Factor Ranking Score (0-100)**: Computes a composite score based on Relative Strength vs NIFTY, Relative Strength vs Sector, momentum persistence, delivery volume spikes, and breakout quality.
- **Dual-Service Railway Architecture**: Seamlessly deploys to Railway using a single multi-stage `Dockerfile`. Runs `worker-service` (daemon loop) and `dashboard-service` (Streamlit interface) in parallel, sharing state via the persistent volume `/app/state`.

---

## Workspace Directory Map

```
indian-alpha/
├── pyproject.toml              # Build settings & UV packages dependencies
├── Dockerfile                  # Multi-service build image configuration
├── docker-compose.yml          # Local multi-service orchestrator
├── README.md                   # Platform documentation
├── railway.json                # Railway build parameters
│
├── indian_alpha/
│   ├── run.py                  # Daemon background worker loop
│   ├── scheduler.py            # Timezone & holiday scheduling engine
│   ├── reflection.py           # Self-learning cognitive reflection engine
│   ├── ranking_engine.py       # Composite scoring engine (0-100)
│   ├── execution.py            # Slippage/Circuits/Brokerage simulator
│   ├── portfolio.py            # Account, sizing, and sector cap manager
│   ├── walk_forward.py         # Out-of-sample & Monte Carlo validation
│   │
│   ├── dashboard/              # Streamlit interactive application
│   │   ├── app.py              # Main dashboard entrypoint & styling
│   │   ├── charts.py           # Reusable Plotly chart draw methods
│   │   ├── portfolio_views.py  # Sizing, holdings, and sector allocations
│   │   ├── regime_views.py     # Current regime and breadth analytics
│   │   ├── rankings_views.py   # Composite ranking filters and tables
│   │   ├── reflection_views.py # Parameter evolution timeline and log
│   │   ├── strategy_views.py   # Active strategy.yaml reader and YAML view
│   │   ├── health_views.py     # Heartbeat telemetry and system resources
│   │   └── trade_views.py      # Trade journal chronological ledger
│   │
│   ├── providers/              # Critical abstraction data layer
│   │   ├── base.py             # MarketDataProvider Protocol
│   │   ├── yahoo.py            # YahooFinanceProvider (with threads/retries)
│   │   └── zerodha.py          # ZerodhaProvider Kite Stub
│   │
│   ├── strategies/             # Strategic trading scripts
│   │   ├── momentum_breakout.py# Primary breakout strategy
│   │   ├── trend_following.py  # Secondary trend crossovers
│   │   ├── relative_strength.py# Benchmarked relative returns
│   │   └── mean_reversion.py   # Oversold Bollinger pulls
│   │
│   ├── regimes/                # Market Regime classifier modules
│   │   ├── classifier.py       # Primary multi-factor regime classifier
│   │   ├── volatility_regime.py# Volatility annualizer
│   │   ├── breadth_regime.py   # Breadth & AD analyzer
│   │   └── sector_rotation.py  # Sector momentum ranker
│   │
│   ├── observability/          # Monitoring & heartbeats
│   │   ├── logging.py          # Loguru structured file rotators
│   │   ├── metrics.py          # API tracking & performance metric counters
│   │   ├── heartbeat.py        # Periodic heartbeat.json atomic writer
│   │   └── alerts.py           # Alerts and webhook dispatch stub
│   │
│   └── storage/                # Persistence I/O read/write layers
│       ├── trades.py           # atomic JSONL append trade logs
│       ├── rankings.py         # JSON rankings & hourly snapshot writer
│       ├── hypotheses.py       # atomic JSONL append hypotheses logs
│       ├── strategy_store.py   # yaml strategy loader and archiver
│       ├── market_regimes.py   # classified regimes history tracker
│       └── snapshots.py        # portfolio state snapshot manager
│
└── state/                      # Mount volume state persistence files
    ├── goal.yaml               # Regime-aware target performance limits
    ├── strategy.yaml           # Active momentum breakout variables
    ├── rankings.json           # Active composite score scans
    ├── trades.jsonl            # simulated trades log
    ├── hypotheses.jsonl        # learning hypotheses log
    ├── market_regimes.json     # classified regimes history database
    ├── snapshots/              # hourly portfolio status files
    └── history/                # archived strategy revisions (.yaml)
```

---

## Setup & Running Locally

Ensure you have Python 3.11 and the modern `uv` tool installed.

### 1. Fast Local Installation
To resolve and install all dependencies rapidly:
```bash
uv pip install -e .
```

### 2. Fast Dry-Run Smoke Test
To verify the system executes and fetches data correctly in a single mock session:
```bash
# Sets FAST_RUN environment variable to run all loop parts once instantly
$env:FAST_RUN="true"
uv run python -m indian_alpha.run
```

### 3. Running via Docker Compose
To run both the background quant worker and the Streamlit dashboard:
```bash
docker-compose up --build
```
The Streamlit dashboard will bind to `http://localhost:8501`.
The worker daemon will run 24x7 in the background, updating state files in `./state`.

---

## Railway Deployment Parameters

Railway detects the `Dockerfile` at the root and builds a single image that powers both connected services:

1. **worker-service**:
   - Start Command: `python -m indian_alpha.run`
   - Volume Mount: Mount a Railway Persistent Volume at `/app/state` to save trading history.

2. **dashboard-service**:
   - Start Command: `streamlit run indian_alpha/dashboard/app.py`
   - Port Bind: Bind port `8501`.
   - Volume Mount: Mount the same Persistent Volume at `/app/state` to share data.
