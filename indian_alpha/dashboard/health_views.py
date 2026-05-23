import streamlit as st
import os
import json
import psutil
from datetime import datetime
from typing import Dict, Any

def render_health_panel(heartbeat_path: str = "/app/state/heartbeat.json"):
    """Displays background scheduler loop heartbeat and system operational parameters."""
    st.header("🩺 System Health & Loop Telemetry")
    
    # 1. Heartbeat File Reader
    if not os.path.exists(heartbeat_path):
        st.error("Heartbeat file not detected. Background worker might not be running or mounting the persistent volume correctly.")
        return
        
    try:
        with open(heartbeat_path, "r") as f:
            hb = json.load(f)
            
        hb_time = datetime.fromisoformat(hb.get("timestamp"))
        latency = (datetime.now() - hb_time).total_seconds()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if latency < 90:
                st.success("Worker Daemon: ACTIVE")
            else:
                st.error("Worker Daemon: OFFLINE")
            st.write(f"*Last Heartbeat: {hb.get('timestamp')}*")
        with col2:
            st.metric("Active Execution Mode", hb.get("mode", "standby").upper())
        with col3:
            st.metric("Daemon Loop Status", hb.get("status", "unknown").upper())
            
        st.write("---")
        
        # Metrics Table
        st.subheader("📊 Operational Metrics")
        metrics = hb.get("metrics", {})
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("YFinance API Requests", metrics.get("api_calls", 0))
        with m_col2:
            st.metric("API Errors & Retries", metrics.get("api_errors", 0))
        with m_col3:
            st.metric("State Database Writes", metrics.get("db_writes", 0))
            
    except Exception as e:
        st.error(f"Failed to read or parse system heartbeat logs: {e}")
        
    st.write("---")
    
    # 2. Disk & Memory usage on volume
    st.subheader("🖥️ Host System Resource Metrics")
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/app/state" if os.path.exists("/app/state") else ".")
    
    res1, res2 = st.columns(2)
    with res1:
        st.metric("Host Memory Usage", f"{mem.percent}% Used", f"Available: {mem.available / (1024*1024):.1f} MB")
    with res2:
        st.metric("State Volume Storage Space", f"{disk.percent}% Used", f"Available: {disk.free / (1024*1024*1024):.2f} GB")
