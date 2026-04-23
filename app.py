"""
Crypto Place Dashboard
Live cryptocurrency dashboard powered by CoinGecko public API.
"""

import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import streamlit as st
from datetime import datetime
import time

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Place Dashboard",
    page_icon="💰",
    layout="wide",
)

# ─── Currency symbols ────────────────────────────────────────────────────────
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "INR": "₹"}

# ─── API helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_top_coins(currency: str) -> pd.DataFrame:
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
        st.error(f"API Error: {exc}")
        return pd.DataFrame()

    rows = []
    for item in data:
        rows.append({
            "Rank": item.get("market_cap_rank", "—"),
            "Coin Name": item.get("name", ""),
            "Symbol": item.get("symbol", "").upper(),
            "id": item.get("id", ""),
            "current_price": item.get("current_price") or 0,
            "price_change_24h": item.get("price_change_percentage_24h") or 0,
            "market_cap": item.get("market_cap") or 0,
        })

    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def fetch_price_history(coin_id: str, currency: str) -> pd.DataFrame:
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        f"?vs_currency={currency.lower()}&days=10&interval=daily"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"History Error: {exc}")
        return pd.DataFrame()

    prices = data.get("prices", [])
    df = pd.DataFrame(prices, columns=["timestamp", "price"])

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df[["date", "price"]]


# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.title("⚙️ Controls")

currency = st.sidebar.selectbox("Currency", ["USD", "EUR", "INR"])
sym = CURRENCY_SYMBOLS[currency]

search_query = st.sidebar.text_input("Search coin")

refresh_clicked = st.sidebar.button("🔄 Refresh Now")
if refresh_clicked:
    st.cache_data.clear()
    st.rerun()

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("💰 Crypto Place Dashboard")
st.caption(f"{currency} ({sym}) • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown("---")

# ─── Fetch Data ──────────────────────────────────────────────────────────────

df_raw = fetch_top_coins(currency)

if df_raw.empty:
    st.warning("No data available")
    st.stop()

# ─── Filter ──────────────────────────────────────────────────────────────────

if search_query:
    df_filtered = df_raw[df_raw["Coin Name"].str.contains(search_query, case=False)]
else:
    df_filtered = df_raw

if df_filtered.empty:
    st.info("No results found, showing all coins")
    df_filtered = df_raw

# ─── Summary Metrics ─────────────────────────────────────────────────────────

def safe_row(df, column, func):
    if df[column].isna().all():
        return df.iloc[0]
    return df.loc[func(df[column])]

highest_price_row = safe_row(df_raw, "current_price", lambda x: x.idxmax())
lowest_change_row = safe_row(df_raw, "price_change_24h", lambda x: x.idxmin())
highest_mcap_row  = safe_row(df_raw, "market_cap", lambda x: x.idxmax())

col1, col2, col3 = st.columns(3)

with col1:
    val = highest_price_row["current_price"]
    st.metric(
        f"💎 Highest Price — {highest_price_row['Coin Name']}",
        f"{sym}{val:,.2f}" if np.isfinite(val) else "—"
    )

with col2:
    val = lowest_change_row["price_change_24h"]
    st.metric(
        f"📉 Lowest 24h — {lowest_change_row['Coin Name']}",
        f"{val:+.2f}%" if np.isfinite(val) else "—",
        delta=f"{val:.2f}%" if np.isfinite(val) else None,
        delta_color="inverse",
    )

with col3:
    val = highest_mcap_row["market_cap"]
    if val >= 1e12:
        mcap = f"{sym}{val/1e12:.2f}T"
    else:
        mcap = f"{sym}{val/1e9:.2f}B"

    st.metric(
        f"🏆 Market Cap — {highest_mcap_row['Coin Name']}",
        mcap if np.isfinite(val) else "—"
    )

st.markdown("---")

# ─── Table ───────────────────────────────────────────────────────────────────

st.subheader("📊 Top 10 Coins")

def safe_format(val, fmt):
    return fmt(val) if np.isfinite(val) else "—"

df_display = df_filtered.copy()

df_display["Price"] = df_display["current_price"].apply(
    lambda x: safe_format(x, lambda v: f"{sym}{v:,.2f}")
)

df_display["Change"] = df_display["price_change_24h"].apply(
    lambda x: safe_format(x, lambda v: f"{v:+.2f}%")
)

df_display["Market Cap"] = df_display["market_cap"].apply(
    lambda x: safe_format(x, lambda v: f"{sym}{v:,.0f}")
)

df_display = df_display[["Rank", "Coin Name", "Symbol", "Price", "Change", "Market Cap"]]

def color_change(val):
    try:
        num = float(val.replace("%", "").replace("+", ""))
        return f"color: {'green' if num >= 0 else 'red'}; font-weight:bold"
    except:
        return ""

st.dataframe(df_display.style.map(color_change, subset=["Change"]), use_container_width=True)

st.markdown("---")

# ─── Chart ───────────────────────────────────────────────────────────────────

st.subheader("📈 10-Day Price Chart")

coin_map = df_raw.set_index("Coin Name")["id"].to_dict()
coin_name = st.selectbox("Select Coin", list(coin_map.keys()))
coin_id = coin_map[coin_name]

df_hist = fetch_price_history(coin_id, currency)

if not df_hist.empty:
    sns.set_style("darkgrid")
    fig, ax = plt.subplots(figsize=(12, 4))

    dates = df_hist["date"]
    prices = df_hist["price"]

    ax.plot(dates, prices)
    ax.fill_between(dates, prices, alpha=0.2)

    ax.set_title(f"{coin_name} Price")
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Price ({sym})")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.xticks(rotation=45)

    st.pyplot(fig)
    plt.close(fig)

else:
    st.warning("Chart data not available")

# ─── Simple Auto Refresh (safe fallback) ─────────────────────────────────────

st.markdown("---")
placeholder = st.empty()

for i in range(60, 0, -1):
    placeholder.info(f"🔄 Refreshing in {i} sec...")
    time.sleep(1)

st.cache_data.clear()
st.rerun()
