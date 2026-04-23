"""
Crypto Place Dashboard
Live cryptocurrency dashboard powered by CoinGecko public API.
"""

import time
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import streamlit as st
from datetime import datetime

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Place Dashboard",
    page_icon="💰",
    layout="wide",
)

# ─── Currency symbols ────────────────────────────────────────────────────────
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "INR": "₹"}

# ─── CoinGecko API helpers ───────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_top_coins(currency: str) -> pd.DataFrame:
    """Fetch top 10 coins by market cap from CoinGecko."""
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency={currency.lower()}&order=market_cap_desc"
        "&per_page=10&page=1&sparkline=false"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Failed to fetch coin data: {exc}")
        return pd.DataFrame()

    rows = []
    for item in data:
        rows.append({
            "Rank": item.get("market_cap_rank", "—"),
            "Coin Name": item.get("name", ""),
            "Symbol": item.get("symbol", "").upper(),
            "id": item.get("id", ""),
            "current_price": item.get("current_price", 0),
            "price_change_24h": item.get("price_change_percentage_24h", 0),
            "market_cap": item.get("market_cap", 0),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def fetch_price_history(coin_id: str, currency: str) -> pd.DataFrame:
    """Fetch 10-day daily price history for a single coin."""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        f"?vs_currency={currency.lower()}&days=10&interval=daily"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Failed to fetch price history: {exc}")
        return pd.DataFrame()

    prices = data.get("prices", [])
    df = pd.DataFrame(prices, columns=["timestamp_ms", "price"])
    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms").dt.date
    df = df[["date", "price"]]
    return df


# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.title("⚙️ Controls")

currency = st.sidebar.selectbox("Currency", ["USD", "EUR", "INR"])
sym = CURRENCY_SYMBOLS[currency]

search_query = st.sidebar.text_input("Filter coins by name", placeholder="e.g. Bitcoin")

refresh_clicked = st.sidebar.button("🔄 Refresh Now")
if refresh_clicked:
    st.cache_data.clear()
    st.rerun()

# Auto-refresh countdown
st.sidebar.markdown("---")
st.sidebar.markdown("**Auto-refresh every 60 s**")
countdown_placeholder = st.sidebar.empty()

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("💰 Crypto Place Dashboard")
st.caption(
    f"Currency: **{currency}** ({sym})  •  "
    f"Last fetched: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**"
)

st.markdown("---")

# ─── Fetch data ──────────────────────────────────────────────────────────────

df_raw = fetch_top_coins(currency)

if df_raw.empty:
    st.warning("No data available. Check your internet connection and try refreshing.")
    st.stop()

# ─── Apply search filter ──────────────────────────────────────────────────────

if search_query.strip():
    mask = df_raw["Coin Name"].str.contains(search_query.strip(), case=False, na=False)
    df_filtered = df_raw[mask].copy()
else:
    df_filtered = df_raw.copy()

if df_filtered.empty:
    st.info(f"No coins matching '{search_query}'. Showing full list.")
    df_filtered = df_raw.copy()

# ─── Summary stats row ───────────────────────────────────────────────────────

highest_price_row = df_raw.loc[df_raw["current_price"].idxmax()]
lowest_change_row = df_raw.loc[df_raw["price_change_24h"].idxmin()]
highest_mcap_row  = df_raw.loc[df_raw["market_cap"].idxmax()]

col1, col2, col3 = st.columns(3)

with col1:
    price_val = np.round(highest_price_row["current_price"], 2)
    st.metric(
        label=f"💎 Highest Priced — {highest_price_row['Coin Name']}",
        value=f"{sym}{price_val:,.2f}",
    )

with col2:
    change_val = np.round(lowest_change_row["price_change_24h"], 2)
    st.metric(
        label=f"📉 Lowest 24h Change — {lowest_change_row['Coin Name']}",
        value=f"{change_val:+.2f}%",
        delta=f"{change_val:.2f}%",
        delta_color="inverse",
    )

with col3:
    mcap_val = highest_mcap_row["market_cap"]
    # Format market cap in billions/trillions for readability
    if mcap_val >= 1e12:
        mcap_str = f"{sym}{np.round(mcap_val / 1e12, 2):.2f}T"
    else:
        mcap_str = f"{sym}{np.round(mcap_val / 1e9, 2):.2f}B"
    st.metric(
        label=f"🏆 Highest Market Cap — {highest_mcap_row['Coin Name']}",
        value=mcap_str,
    )

st.markdown("---")

# ─── Top 10 Coins Table ───────────────────────────────────────────────────────

st.subheader("📊 Top 10 Coins by Market Cap")

# Build display dataframe with formatted columns
df_display = df_filtered[["Rank", "Coin Name", "Symbol", "current_price", "price_change_24h", "market_cap"]].copy()
df_display["Current Price"] = df_display["current_price"].apply(
    lambda p: f"{sym}{np.round(p, 2):,.2f}"
)
df_display["24h Change %"] = df_display["price_change_24h"].apply(
    lambda c: f"{np.round(c, 2):+.2f}%"
)
df_display["Market Cap"] = df_display["market_cap"].apply(
    lambda m: f"{sym}{m:,.0f}"
)
df_display = df_display[["Rank", "Coin Name", "Symbol", "Current Price", "24h Change %", "Market Cap"]]

# Color-code 24h Change column using pandas Styler
def color_change(val: str):
    """Return CSS color based on whether change is positive or negative."""
    try:
        numeric = float(val.replace("%", "").replace("+", ""))
        color = "#00c853" if numeric >= 0 else "#d50000"
    except ValueError:
        color = "white"
    return f"color: {color}; font-weight: bold"

styled = df_display.style.map(color_change, subset=["24h Change %"])

st.dataframe(styled, use_container_width=True, hide_index=True)

st.markdown("---")

# ─── Price Chart ─────────────────────────────────────────────────────────────

st.subheader("📈 10-Day Price History")

coin_options = df_raw[["Coin Name", "id"]].set_index("Coin Name")["id"].to_dict()
selected_coin_name = st.selectbox("Select a coin", list(coin_options.keys()))
selected_coin_id   = coin_options[selected_coin_name]

df_history = fetch_price_history(selected_coin_id, currency)

if not df_history.empty:
    sns.set_style("darkgrid")
    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    # Plot line + shaded area under the curve
    dates  = pd.to_datetime(df_history["date"])
    prices = df_history["price"].values

    sns.lineplot(x=dates, y=prices, ax=ax, color="#00c853", linewidth=2.5)
    ax.fill_between(dates, prices, alpha=0.15, color="#00c853")

    # Format axes
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    plt.xticks(rotation=45, color="white", fontsize=9)
    plt.yticks(color="white", fontsize=9)
    ax.set_xlabel("Date", color="white", fontsize=11)
    ax.set_ylabel(f"Price ({sym})", color="white", fontsize=11)
    ax.set_title(
        f"{selected_coin_name} — 10-Day Price ({currency})",
        color="white",
        fontsize=14,
        pad=12,
    )
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")

    # Annotate min/max price points
    min_idx = np.argmin(prices)
    max_idx = np.argmax(prices)
    ax.annotate(
        f"Low\n{sym}{np.round(prices[min_idx], 2):,.2f}",
        xy=(dates.iloc[min_idx], prices[min_idx]),
        xytext=(10, 15), textcoords="offset points",
        color="#ff5252", fontsize=8,
        arrowprops=dict(arrowstyle="->", color="#ff5252", lw=1),
    )
    ax.annotate(
        f"High\n{sym}{np.round(prices[max_idx], 2):,.2f}",
        xy=(dates.iloc[max_idx], prices[max_idx]),
        xytext=(10, -25), textcoords="offset points",
        color="#69f0ae", fontsize=8,
        arrowprops=dict(arrowstyle="->", color="#69f0ae", lw=1),
    )

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
else:
    st.warning("Could not load price history for this coin.")

st.markdown("---")

# ─── Auto-refresh countdown ───────────────────────────────────────────────────
# Count down 60 s then rerun the entire script to pull fresh data.

for remaining in range(60, 0, -1):
    countdown_placeholder.info(f"Next refresh in **{remaining}s**")
    time.sleep(1)

st.cache_data.clear()
st.rerun()
