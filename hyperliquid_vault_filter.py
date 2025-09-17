import streamlit as st
import pandas as pd
import requests
import time
import re

# API endpoint (fallback)
API_URL = "https://api.hyperliquid.xyz/info"

@st.cache_data(ttl=300)
def fetch_vault_data():
    try:
        summaries_req = {"type": "vaultSummaries"}
        summaries_resp = requests.post(API_URL, json=summaries_req, timeout=10)
        summaries_resp.raise_for_status()
        summaries = summaries_resp.json()
        
        if not summaries or not isinstance(summaries, list):
            return []
        
        vault_data = []
        for vault in summaries:
            details_req = {"type": "vaultDetails", "vaultAddress": vault.get("vaultAddress", "")}
            details_resp = requests.post(API_URL, json=details_req, timeout=10)
            if details_resp.status_code == 200:
                details = details_resp.json()
                apr = details.get("apr", 0) * 100
                
                create_time = vault.get("createTimeMillis", 0) / 1000
                age_days = (time.time() - create_time) / (24 * 3600) if create_time > 0 else 0
                
                tvl_str = str(vault.get("tvl", "0"))
                tvl_clean = re.sub(r'[^\d.]', '', tvl_str)
                tvl_usd = float(tvl_clean) if tvl_clean else 0
                
                vault_data.append({
                    "Name": vault.get("name", "N/A"),
                    "Address": vault.get("vaultAddress", ""),
                    "Leader": vault.get("leader", ""),
                    "APR (%)": round(apr, 2),
                    "TVL (USD)": tvl_usd,
                    "Age (days)": round(age_days, 1),
                    "Closed": vault.get("isClosed", False)
                })
            time.sleep(0.1)
        return vault_data
    except Exception as e:
        st.warning(f"API fetch failed (expected, as endpoint may be deprecated): {e}")
        return []

# Static data from your screenshot (for reliable filtering)
static_vaults = [
    {"Name": "Hyperliquidity Provider (HLP)", "Address": "N/A", "Leader": "0x087d3847", "APR (%)": 74.0, "TVL (USD)": 5096759, "Age (days)": 866, "Closed": False},
    {"Name": "Liquidator", "Address": "N/A", "Leader": "0xf1380c9", "APR (%)": 0.0, "TVL (USD)": 16178, "Age (days)": 933, "Closed": False},
    {"Name": "CASTLE Vault", "Address": "N/A", "Leader": "0xa227ee5", "APR (%)": 2.14, "TVL (USD)": 69, "Age (days)": 55, "Closed": False},
    {"Name": "SOL", "Address": "N/A", "Leader": "0x4480d5", "APR (%)": 2.03, "TVL (USD)": 2706, "Age (days)": 233, "Closed": False},
    {"Name": "Gargantuan", "Address": "0xdac48b58", "Leader": "0x6bcdb16", "APR (%)": 1.82, "TVL (USD)": 5808, "Age (days)": 4, "Closed": False},
    {"Name": "Long Good – Short Bad", "Address": "N/A", "Leader": "0xebc6a0d", "APR (%)": 1.73, "TVL (USD)": 28609, "Age (days)": 116, "Closed": False},
    {"Name": "BTC MADWR LD channel", "Address": "N/A", "Leader": "0x774471", "APR (%)": 1.65, "TVL (USD)": 46, "Age (days)": 142, "Closed": False},
    {"Name": "Market Efficiency Assistance", "Address": "N/A", "Leader": "0x957700", "APR (%)": 1.54, "TVL (USD)": 1232652, "Age (days)": 146, "Closed": False},
    {"Name": "ETHFI Efficiency Assistance", "Address": "N/A", "Leader": "0x4480d5", "APR (%)": 1.38, "TVL (USD)": 17495, "Age (days)": 61, "Closed": False},
    {"Name": "Barv A", "Address": "N/A", "Leader": "0x490af5", "APR (%)": 1.35, "TVL (USD)": 72915, "Age (days)": 216, "Closed": False},
    {"Name": "10Kx", "Address": "N/A", "Leader": "0x87ff68", "APR (%)": 1.31, "TVL (USD)": 89388, "Age (days)": 169, "Closed": False},
    {"Name": "1000x", "Address": "N/A", "Leader": "0xf5b3e8", "APR (%)": 1.07, "TVL (USD)": 83287, "Age (days)": 169, "Closed": False},
    {"Name": "Elsewhere", "Address": "N/A", "Leader": "0x5b3eb", "APR (%)": 1.17, "TVL (USD)": 232716, "Age (days)": 438, "Closed": False},
    {"Name": "mktbuy", "Address": "N/A", "Leader": "0xe593f6", "APR (%)": 1.12, "TVL (USD)": 30871, "Age (days)": 137, "Closed": False},
    {"Name": "ETH 50xLong", "Address": "N/A", "Leader": "0x28316d", "APR (%)": 1.03, "TVL (USD)": 37987, "Age (days)": 271, "Closed": False},
]

# Streamlit UI
st.title("Hyperliquid Vault Filter")

show_debug = st.sidebar.checkbox("Show Debug Info", value=False)

# Load data: static + API fallback
with st.spinner("Loading vault data..."):
    api_vaults = fetch_vault_data()
    all_vaults = static_vaults.copy()
    if api_vaults:
        # Append API vaults if not duplicate (by name)
        for v in api_vaults:
            if not any(existing["Name"] == v["Name"] for existing in all_vaults):
                all_vaults.append(v)
    df = pd.DataFrame(all_vaults)
    df = df[(df["APR (%)"] >= 0) & (df["TVL (USD)"] >= 0)]

if df.empty:
    st.error("No data available.")
    st.stop()

if show_debug:
    st.sidebar.subheader("Data Source")
    st.sidebar.info("Static from screenshot + API fallback")

# Filters
st.sidebar.header("Filters")
col1, col2 = st.sidebar.columns(2)
min_apr = col1.slider("Min APR (%)", 0.0, 100.0, 0.0)
max_apr = col2.slider("Max APR (%)", 0.0, 2000.0, 2000.0)
col3, col4 = st.sidebar.columns(2)
min_tvl = col3.number_input("Min TVL (USD)", 0, 10000000, 0)
min_age = col4.slider("Min Age (days)", 0, 1000, 0)
show_closed = st.sidebar.checkbox("Show Closed Vaults", value=False)

if st.sidebar.button("Clear All Filters"):
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
    st.info("No matches. Try loosening filters.")
    st.subheader("All Available Vaults")
    st.dataframe(df.sort_values("APR (%)", ascending=False), use_container_width=True)
else:
    st.dataframe(filtered_df.sort_values("APR (%)", ascending=False), use_container_width=True)

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total Vaults", len(df))
col2.metric("Avg APR", f"{df['APR (%)'].mean():.2f}%")
col3.metric("Total TVL", f"${df['TVL (USD)'].sum():,.0f}")

if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()
