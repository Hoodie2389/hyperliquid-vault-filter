import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time
import re  # For TVL cleaning
import json  # For pretty-printing raw data

# API endpoint
API_URL = "https://api.hyperliquid.xyz/info"

@st.cache_data(ttl=60, show_spinner="Fetching vault data from Hyperliquid API...")
def fetch_vault_data():
    st.cache_data.clear()  # Force refresh each run for debugging
    try:
        # Step 1: Fetch all vault summaries
        summaries_req = {"type": "vaultSummaries"}
        summaries_resp = requests.post(API_URL, json=summaries_req, timeout=10)
        summaries_resp.raise_for_status()
        summaries = summaries_resp.json()
        
        if not summaries or not isinstance(summaries, list):
            st.warning(f"Invalid summaries response: {summaries}")
            return pd.DataFrame()
        
        # Step 2: Fetch details for each vault to get APR
        vault_data = []
        for vault in summaries:
            try:
                details_req = {
                    "type": "vaultDetails",
                    "vaultAddress": vault.get("vaultAddress", "")
                }
                details_resp = requests.post(API_URL, json=details_req, timeout=10)
                details_resp.raise_for_status()
                details = details_resp.json()
                
                # Extract APR (handle nested or missing)
                apr = 0
                if isinstance(details, dict) and "portfolio" in details:
                    for period in details["portfolio"]:
                        if isinstance(period[1], dict) and "apr" in period[1]:
                            apr = period[1]["apr"] * 100  # Convert to %
                            break
                
                # Calculate age in days
                create_time = vault.get("createTimeMillis", 0) / 1000  # To seconds
                age_days = (time.time() - create_time) / (24 * 3600) if create_time > 0 else 0
                
                # TVL: Handle nested or string formats
                tvl = vault.get("tvl", {})
                tvl_usd = 0
                if isinstance(tvl, (int, float)):
                    tvl_usd = float(tvl)
                elif isinstance(tvl, str):
                    tvl_clean = re.sub(r'[^\d.]', '', tvl)
                    tvl_usd = float(tvl_clean) if tvl_clean else 0
                elif isinstance(tvl, dict) and "usdValue" in tvl:
                    tvl_usd = float(tvl.get("usdValue", 0))
                
                vault_data.append({
                    "Name": vault.get("name", "N/A"),
                    "Address": vault.get("vaultAddress", ""),
                    "Leader": vault.get("leader", ""),
                    "APR (%)": round(apr, 2),
                    "TVL (USD)": tvl_usd,
                    "Age (days)": round(age_days, 1),
                    "Closed": vault.get("isClosed", False)
                })
            except Exception as e:
                st.warning(f"Error fetching details for {vault.get('vaultAddress', 'unknown')}: {e}")
            time.sleep(0.1)  # Rate limit
        
        df = pd.DataFrame(vault_data)
        # Filter out invalid rows
        df = df[(df["APR (%)"] >= 0) & (df["TVL (USD)"] >= 0) & (df["Age (days)"] >= 0)]
        if show_debug:
            st.sidebar.subheader("Raw Summaries Response")
            st.sidebar.json(summaries)
            st.sidebar.subheader("Raw Details Sample")
            st.sidebar.json(details)
        return df
    except Exception as e:
        st.error(f"API fetch failed: {e}. Check network or API status.")
        return pd.DataFrame()

# Streamlit UI
st.title("Hyperliquid Vault Filter")

# Sidebar for debug
show_debug = st.sidebar.checkbox("Show Debug Info", value=True)

# Fetch data
df = fetch_vault_data()

if df.empty:
    st.error("No vault data available. Check API status or try later.")
    st.stop()

# Filters in sidebar
st.sidebar.header("Filters")
col1, col2 = st.sidebar.columns(2)
with col1:
    min_apr = st.slider("Min APR (%)", 0.0, 100.0, 0.0)
with col2:
    max_apr = st.slider("Max APR (%)", 0.0, 2000.0, 2000.0)
col3, col4 = st.sidebar.columns(2)
with col3:
    min_tvl = st.number_input("Min TVL (USD)", 0, 10000000, 0)
with col4:
    min_age = st.slider("Min Age (days)", 0, 1000, 0)
show_closed = st.sidebar.checkbox("Show Closed Vaults", value=False)

# Clear filters button
if st.sidebar.button("Clear All Filters"):
    min_apr, max_apr, min_tvl, min_age = 0.0, 2000.0, 0, 0
    st.rerun()

# Apply filters
filtered_df = df[
    (df["APR (%)"] >= min_apr) &
    (df["APR (%)"] <= max_apr) &
    (df["TVL (USD)"] >= min_tvl) &
    (df["Age (days)"] >= min_age)
]
if not show_closed:
    filtered_df = filtered_df[~filtered_df["Closed"]]

# Display
st.subheader(f"Filtered Vaults ({len(filtered_df)} results)")
if filtered_df.empty:
    st.info("No vaults match your filters. Try adjusting them or clearing filters.")
    st.subheader("Top 5 Recent Vaults (Unfiltered)")
    top5 = df.nlargest(5, "Age (days)").head()
    st.dataframe(top5, use_container_width=True)
else:
    st.dataframe(filtered_df, use_container_width=True)

# Metrics
col1, col2, col3 = st.columns(3)
total_vaults = len(df)
avg_apr = df['APR (%)'].mean() if not df.empty else 0
total_tvl = df['TVL (USD)'].sum() if not df.empty else 0
col1.metric("Total Vaults", total_vaults)
col2.metric("Avg APR", f"{avg_apr:.2f}%")
col3.metric("Total TVL", f"${total_tvl:,.0f}")

# Refresh button
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()
