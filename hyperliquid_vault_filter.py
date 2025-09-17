import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time
import re  # For TVL cleaning

# API endpoint
API_URL = "https://api.hyperliquid.xyz/info"

@st.cache_data(ttl=60)  # Cache for 1 minute for fresher data
def fetch_vault_data():
    try:
        # Step 1: Fetch all vault summaries
        summaries_req = {"type": "vaultSummaries"}
        summaries_resp = requests.post(API_URL, json=summaries_req)
        summaries_resp.raise_for_status()
        summaries = summaries_resp.json()
        
        if not summaries:
            return pd.DataFrame()
        
        # Step 2: Fetch details for each vault to get APR
        vault_data = []
        for vault in summaries:
            try:
                details_req = {
                    "type": "vaultDetails",
                    "vaultAddress": vault["vaultAddress"]
                }
                details_resp = requests.post(API_URL, json=details_req)
                details_resp.raise_for_status()
                details = details_resp.json()
                apr = details.get("apr", 0) * 100  # Convert to %
                
                # Calculate age in days
                create_time = vault.get("createTimeMillis", 0) / 1000  # To seconds
                age_days = (time.time() - create_time) / (24 * 3600) if create_time > 0 else 0
                
                # TVL: Clean string like "$5,808" or "5808" to float
                tvl_str = str(vault.get("tvl", "0"))
                tvl_clean = re.sub(r'[^\d.]', '', tvl_str)  # Remove $, commas, etc.
                tvl_usd = float(tvl_clean) if tvl_clean else 0
                
                vault_data.append({
                    "Name": vault.get("name", "N/A"),
                    "Address": vault["vaultAddress"],
                    "Leader": vault["leader"],
                    "APR (%)": round(apr, 2),
                    "TVL (USD)": tvl_usd,
                    "Age (days)": round(age_days, 1),
                    "Closed": vault.get("isClosed", False)
                })
            except Exception as e:
                st.warning(f"Error fetching details for vault {vault.get('vaultAddress', 'unknown')}: {e}")
            time.sleep(0.1)  # Rate limit
        
        df = pd.DataFrame(vault_data)
        # Filter out invalid rows (e.g., APR < 0 or TVL < 0)
        df = df[(df["APR (%)"] >= 0) & (df["TVL (USD)"] >= 0)]
        return df
    except Exception as e:
        st.error(f"API fetch failed: {e}")
        return pd.DataFrame()

# Streamlit UI
st.title("Hyperliquid Vault Filter")

# Sidebar for debug (optional)
show_debug = st.sidebar.checkbox("Show Debug Info", value=False)

# Fetch data
with st.spinner("Fetching vault data from Hyperliquid API..."):
    df = fetch_vault_data()

if df.empty:
    st.error("No vault data available. Check API status or try later.")
    st.stop()

if show_debug:
    st.sidebar.subheader("Debug: Raw Data Preview")
    st.sidebar.write(df.head())
    st.sidebar.write(f"Total fetched: {len(df)}")

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
    # Show top 5 unfiltered for reference
    st.subheader("Top 5 Recent Vaults (Unfiltered)")
    top5 = df.nlargest(5, "Age (days)").head()  # Or sort by TVL: df.nlargest(5, "TVL (USD)")
    st.dataframe(top5, use_container_width=True)
else:
    # Sortable table
    st.dataframe(filtered_df, use_container_width=True)

# Metrics (only on full dataset)
col1, col2, col3 = st.columns(3)
total_vaults = len(df)
avg_apr = df['APR (%)'].mean()
total_tvl = df['TVL (USD)'].sum()
col1.metric("Total Vaults", total_vaults)
col2.metric("Avg APR", f"{avg_apr:.2f}%")
col3.metric("Total TVL", f"${total_tvl:,.0f}")

# Add a refresh button
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()
