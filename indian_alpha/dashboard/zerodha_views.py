import streamlit as st
from indian_alpha.providers.loader import get_active_provider, reset_active_provider
from indian_alpha.providers.zerodha import ZerodhaProvider
from indian_alpha.storage.strategy_store import load_strategy

def render_zerodha_auth_sidebar():
    """
    Renders a professional, beautifully styled Zerodha Kite authorization panel
    directly inside Streamlit's sidebar or main viewport.
    """
    # Load configuration
    strat_cfg = load_strategy()
    provider_name = strat_cfg.get("market_data", {}).get("provider", "yahoo").lower()
    
    # Render component header
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔌 Zerodha Kite Connect")
    
    if provider_name != "zerodha":
        st.sidebar.info("💡 **Active Feed:** Yahoo Finance (Free)\n\nSwitch strategy config to `zerodha` to activate professional feeds.")
        return

    # Load active provider (guaranteed to be ZerodhaProvider)
    provider = get_active_provider()
    if not isinstance(provider, ZerodhaProvider):
        st.sidebar.error("Failed to load Zerodha provider instance.")
        return
        
    # --- AUTOMATIC REQUEST_TOKEN CAPTURE FLOW (Premium UX) ---
    query_params = st.query_params
    if "request_token" in query_params:
        request_token = query_params["request_token"]
        
        # Check if we have already processed this token to prevent concurrent double-exchange calls
        if st.session_state.get("processed_request_token") == request_token:
            return
            
        st.session_state["processed_request_token"] = request_token
        st.sidebar.info("🔄 Capturing login redirect...")
        
        # Authenticate and cache access token
        success = provider.generate_session(request_token)
        if success:
            st.sidebar.toast("🎉 Zerodha connection successful!", icon="🟢")
            reset_active_provider() # Clear cache to instantiate newly connected client
            
            # Clear request token from browser address bar to prevent reuse loops
            st.query_params.clear()
            st.rerun()
        else:
            st.sidebar.error("❌ Authentication failed. Check your API Secret.")
            st.query_params.clear()

    # --- RENDER CONNECTION STATE ---
    if provider.is_connected():
        st.sidebar.success("🟢 Zerodha Connected")
        st.sidebar.caption("API Session is active and authenticated for today. Enjoy genuine EOD delivery & institutional breakout data.")
        
        if st.sidebar.button("🔄 Disconnect / Reset", use_container_width=True):
            from indian_alpha.config import BASE_STATE_DIR
            import os
            session_file = os.path.join(BASE_STATE_DIR, "zerodha_session.json")
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception:
                    pass
            reset_active_provider()
            st.rerun()
    else:
        st.sidebar.error("🔴 Zerodha Session Expired / Inactive")
        st.sidebar.markdown("To resume systematic screening and validation cycles, authenticate with Zerodha:")
        
        login_url = provider.get_login_url()
        if login_url:
            st.sidebar.link_button("🔑 Log in with Zerodha", login_url, use_container_width=True)
            
            # Manual fallback input
            with st.sidebar.expander("Or enter token manually"):
                manual_token = st.text_input("Request Token", key="zerodha_manual_token")
                if st.button("Connect Token", use_container_width=True):
                    if manual_token.strip():
                        success = provider.generate_session(manual_token.strip())
                        if success:
                            st.toast("🎉 Connected manually!", icon="🟢")
                            reset_active_provider()
                            st.rerun()
                        else:
                            st.error("Manual connection failed.")
        else:
            st.sidebar.warning("⚠️ Credentials Missing! Please set your ZERODHA_API_KEY and ZERODHA_API_SECRET in your `.env` file.")
