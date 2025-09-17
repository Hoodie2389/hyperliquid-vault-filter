"""
Streamlit application to explore and filter Hyperliquid vaults.

This script fetches vault metadata from Hyperliquid's public API and
displays it in an interactive table.  Users can filter the results by
annual percentage rate (APR), total value locked (TVL) and the age of
the vault in days.  Age is estimated from the creation timestamp
included in each vault record when available.

To run this app locally install the dependencies listed in
``requirements.txt`` and start Streamlit::

    pip install -r requirements.txt
    streamlit run hyperliquid_vaults_app.py

This will start a local web server and open your default browser.  The
filter controls live in the sidebar and update the results in real
time.  If the API call fails, an error message is shown instead.

Note: The Hyperliquid info endpoint expects POST requests with a JSON
body.  Some hosting environments may restrict HTTP methods; if that
applies to you replace the fetch logic with a GET request to a proxy
or mirror that exposes vault data as JSON.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st


def fetch_vault_summaries() -> List[Dict[str, Any]]:
    """Fetch vault summaries from the Hyperliquid API.

    Returns a list of dictionaries where each dictionary describes a
    single vault.  The API returns many fields beyond what this app
    displays; the full record is kept in each row under the ``raw``
    column so that advanced users can inspect it via the JSON viewer.

    If the request fails for any reason the function returns an empty
    list.
    """
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "vaultSummaries"}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        # The API returns a JSON array of objects.
        data = response.json()
        if not isinstance(data, list):
            return []
        return data  # type: ignore[return-value]
    except Exception as exc:  # noqa: broad-except
        # Log the error to Streamlit and return empty list
        st.error(f"Failed to fetch vault summaries: {exc}")
        return []


def process_vaults(raw_vaults: List[Dict[str, Any]]) -> pd.DataFrame:
    """Normalize raw vault records into a DataFrame for display.

    The function extracts a handful of fields from each vault record:

    - ``name``: human‑readable name for the vault if provided.  If
      absent, the last 6 characters of the leader address are used.
    - ``leader``: address of the vault owner/leader.
    - ``apr``: annual percentage rate as a percentage (0–100).  Many
      records express APR as a fraction (e.g. 0.12 for 12%), so the
      value is multiplied by 100 if ``apr`` is between 0 and 1.  If
      both ``apr`` and ``apy`` fields are missing the app defaults to
      zero.
    - ``tvl``: total value locked in the vault (in USD).  Some APIs
      use the key ``totalDeposits``; that is supported as a fallback.
    - ``age_days``: approximate age of the vault in days.  If the
      record contains one of the timestamp fields ``createdTs``,
      ``createdTime`` or ``startTimestamp`` the age is computed from
      now.
    - ``raw``: the original unmodified vault record (useful for
      inspection in the UI).
    """
    now_ts = datetime.now(timezone.utc).timestamp()
    records = []
    for v in raw_vaults:
        # Determine name
        name: Optional[str] = (
            v.get("vaultName")
            or v.get("name")
            or (v.get("leader")[-6:] if isinstance(v.get("leader"), str) else None)
        )

        # Extract APR or APY.  If the value is between 0 and 1 treat it
        # as a fraction and convert to percentage.  Some vaults may
        # express APR already as a percentage.
        apr_value: Optional[float] = None
        for key in ("apr", "apy"):
            val = v.get(key)
            if val is not None:
                try:
                    apr_value = float(val)
                    break
                except (TypeError, ValueError):
                    continue
        if apr_value is None:
            apr_perc = 0.0
        elif 0 <= apr_value <= 1:
            apr_perc = apr_value * 100
        else:
            apr_perc = apr_value

        # Extract TVL; fallback if key names differ
        tvl_val: Optional[float] = None
        for key in ("tvl", "totalDeposits", "tvlUsd"):
            val = v.get(key)
            if val is not None:
                try:
                    tvl_val = float(val)
                    break
                except (TypeError, ValueError):
                    continue
        if tvl_val is None:
            tvl_val = 0.0

        # Age calculation: look for several possible timestamp keys
        age_days: Optional[float] = None
        for key in ("createdTs", "createdTime", "startTimestamp", "createdAt"):
            ts = v.get(key)
            if ts:
                try:
                    # Some APIs return milliseconds; if so divide by 1e3
                    ts_float = float(ts)
                    if ts_float > 1e12:
                        ts_float /= 1e3
                    age_days = (now_ts - ts_float) / 86400
                    break
                except (TypeError, ValueError):
                    continue

        records.append(
            {
                "name": name or "Unknown",
                "leader": v.get("leader"),
                "apr": apr_perc,
                "tvl": tvl_val,
                "age_days": age_days,
                "raw": v,
            }
        )

    df = pd.DataFrame.from_records(records)
    return df


def main() -> None:
    st.set_page_config(page_title="Hyperliquid Vault Explorer", layout="wide")
    st.title("Hyperliquid Vault Explorer")
    st.markdown(
        """
        Use the controls in the sidebar to filter vaults by annual
        percentage rate (APR), total value locked (TVL) and age in
        days.  The underlying data comes from Hyperliquid's public
        ``vaultSummaries`` info endpoint.  Records that do not have a
        creation timestamp are assigned ``None`` for age and are
        included regardless of the age filter.
        """
    )

    with st.sidebar:
        st.header("Filters")
        min_apr = st.number_input("Minimum APR (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
        max_apr = st.number_input("Maximum APR (%)", min_value=0.0, max_value=100.0, value=100.0, step=0.1)
        min_tvl = st.number_input(
            "Minimum TVL (USD)", min_value=0.0, value=0.0, step=1.0, help="Only include vaults with TVL ≥ this value"
        )
        max_tvl = st.number_input(
            "Maximum TVL (USD)", min_value=0.0, value=1e9, step=1.0, help="Only include vaults with TVL ≤ this value"
        )
        min_age = st.number_input(
            "Minimum Age (days)", min_value=0.0, value=0.0, step=1.0, help="Only include vaults at least this old"
        )
        max_age = st.number_input(
            "Maximum Age (days)", min_value=0.0, value=10000.0, step=1.0, help="Only include vaults no older than this"
        )

    raw_data = fetch_vault_summaries()
    df = process_vaults(raw_data)

    if df.empty:
        st.warning("No vault data available.")
        return

    # Apply filters.  Convert APR filter values to percent as APR values in the
    # DataFrame are already percentages.
    filtered_df = df[(df["apr"] >= min_apr) & (df["apr"] <= max_apr)]
    filtered_df = filtered_df[(filtered_df["tvl"] >= min_tvl) & (filtered_df["tvl"] <= max_tvl)]

    # Age filter: include rows with ``None`` age in results regardless of filters.
    def age_filter(val: Optional[float]) -> bool:
        return val is None or (min_age <= val <= max_age)

    filtered_df = filtered_df[filtered_df["age_days"].apply(age_filter)]

    st.subheader(f"Filtered results (showing {len(filtered_df)} vaults)")
    st.dataframe(
        filtered_df.drop(columns=["raw"])  # hide raw column in the table
        .rename(columns={"apr": "APR (%)", "tvl": "TVL (USD)", "age_days": "Age (days)"})
    )

    # Show JSON for the selected row
    st.subheader("Inspect a vault record")
    if not filtered_df.empty:
        selected = st.selectbox(
            "Select a vault to inspect its full record",
            options=list(filtered_df.index),
            format_func=lambda idx: filtered_df.loc[idx, "name"],
        )
        st.json(filtered_df.loc[selected, "raw"])
    else:
        st.write("No vaults match the selected filters.")


if __name__ == "__main__":
    main()
