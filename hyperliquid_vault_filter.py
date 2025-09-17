import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

# API endpoint
API_URL = "https://api.hyperliquid.xyz/info"

@st.cache_data(ttl=300)  # Cache for 5 minutes to avoid hammering the API
def fetch_vault_data():
    # Step 1: Fetch all vault summaries
    summaries_req = {"type": "vaultSummaries"}
    summaries_resp = requests.post(API_URL, json=summaries_req)
    if summaries_resp.status_code != 200:
        st.error("Failed to fetch vault summaries. Check API status.")
        return pd.DataFrame()
    
    summaries = summaries_resp.json()
    
    if not summaries:
        st.warning("No vaults found.")
        return pd.DataFrame()
    
    # Step 2: Fetch details for each vault to get APR
    vault_data = []
    for vault in summaries:
        details_req = {
            "type": "vaultDetails",
            "vaultAddress": vault["vaultAddress"]
        }
        details_resp = requests.post(API_URL, json=details_req)
        if details_resp.status_code == 200:
            details = details_resp.json()
            apr = details.get("apr", 0) * 100  # Convert to %
            
            # Calculate age in days
            create_time = vault.get("createTimeMillis", 0) / 1000  # To seconds
            age_days = (time.time() - create_time) / (24 * 3600)
            
            # TVL from summaries (string, convert to float)
            tvl_usd = float(vault.get("tvl", 0))
            
            vault_data.append({
                "Name": vault.get("name", "N/A"),
                "Address": vault["vaultAddress"],
                "Leader": vault["leader"],
                "APR (%)": round(apr, 2),
                "TVL (USD)": tvl_usd,
                "Age (days)": round(age_days, 1),
                "Closed": vault.get("isClosed", False)
            })
        time.sleep(0.1)  # Rate limit politeness
    
    df = pd.DataFrame(vault_data)
    return df

# Streamlit UI
st.title("Hyperliquid Vault Filter")

# Fetch data
with st.spinner("Fetching vault data..."):
    df = fetch_vault_data()

if df.empty:
    st.stop()

# Filters
st.sidebar.header("Filters")
min_apr = st.sidebar.slider("Min APR (%)", 0.0, 100.0, 0.0)
max_apr = st.sidebar.slider("Max APR (%)", 0.0, 1000.0, 1000.0)
min_tvl = st.sidebar.number_input("Min TVL (USD)", 0, 10000000, 0)
min_age = st.sidebar.slider("Min Age (days)", 0, 1000, 0)
show_closed = st.sidebar.checkbox("Show Closed Vaults", value=False)

# Apply filters
filtered_df = df[
    (df["APR (%)"] >= min_apr) &
    (df["APR (%)"] <= max_apr) &
    (df["TVL (USD)"] >= min_tvl) &
    (df["Age (days)"] >= min_age) &
    (df["Closed"] == show_closed)
]

# Display
st.subheader(f"Filtered Vaults ({len(filtered_df)} results)")
if not filtered_df.empty:
    st.dataframe(filtered_df, use_container_width=True)
else:
    st.info("No vaults match your filters. Try adjusting them.")

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total Vaults", len(df))
col2.metric("Avg APR", f"{df['APR (%)'].mean():.2f}%")
col3.metric("Total TVL", f"${df['TVL (USD)'].sum():,.0f}")
