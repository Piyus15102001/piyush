import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
import requests
from streamlit_autorefresh import st_autorefresh
from nsepython import nse_optionchain_scrapper
from datetime import datetime
import time
from retry import retry
from functools import wraps

# Set page config
st.set_page_config(page_title="Groww-Like Market App", layout="wide")
st.title("📈 Groww-Like Stock Market Dashboard")

# Auto-refresh every 6 seconds
st_autorefresh(interval=5000, key="refresh")

# Stock list
nifty_50_tickers = {
    "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS", "APOLLOHOSP": "APOLLOHOSP.NS",
    "ASIANPAINT": "ASIANPAINT.NS", "AXISBANK": "AXISBANK.NS", "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
    "BAJFINANCE": "BAJFINANCE.NS", "BAJAJFINSV": "BAJAJFINSV.NS", "BPCL": "BPCL.NS",
    "BHARTIARTL": "BHARTIARTL.NS", "BRITANNIA": "BRITANNIA.NS", "CIPLA": "CIPLA.NS",
    "COALINDIA": "COALINDIA.NS", "DIVISLAB": "DIVISLAB.NS", "DRREDDY": "DRREDDY.NS",
    "EICHERMOT": "EICHERMOT.NS", "GRASIM": "GRASIM.NS", "HCLTECH": "HCLTECH.NS",
    "HDFCBANK": "HDFCBANK.NS", "HDFCLIFE": "HDFCLIFE.NS", "HEROMOTOCO": "HEROMOTOCO.NS",
    "HINDALCO": "HINDALCO.NS", "HINDUNILVR": "HINDUNILVR.NS", "ICICIBANK": "ICICIBANK.NS",
    "ITC": "ITC.NS", "INDUSINDBK": "INDUSINDBK.NS", "INFY": "INFY.NS", "JSWSTEEL": "JSWSTEEL.NS",
    "KOTAKBANK": "KOTAKBANK.NS", "LT": "LT.NS", "M&M": "M&M.NS", "MARUTI": "MARUTI.NS",
    "NTPC": "NTPC.NS", "NESTLEIND": "NESTLEIND.NS", "ONGC": "ONGC.NS", "POWERGRID": "POWERGRID.NS",
    "RELIANCE": "RELIANCE.NS", "SBILIFE": "SBILIFE.NS", "SBIN": "SBIN.NS", "SUNPHARMA": "SUNPHARMA.NS",
    "TCS": "TCS.NS", "TATACONSUM": "TATACONSUM.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "TATASTEEL": "TATASTEEL.NS", "TECHM": "TECHM.NS", "TITAN": "TITAN.NS", "UPL": "UPL.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS", "WIPRO": "WIPRO.NS" ,"HDFC BANK": "HDFCBANK.NS",
    "NIFTY 50": "^NSEI"
}

# Initialize session state
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["Stock", "Buy Price", "Qty", "Timestamp"])
if "option_trades" not in st.session_state:
    st.session_state.option_trades = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Sidebar selection
st.sidebar.header("📌 Select Stock")
selected_name = st.sidebar.selectbox("Stock", list(nifty_50_tickers.keys()))
symbol = nifty_50_tickers[selected_name]

# Tabs
live_tab, option_tab, portfolio_tab, chat_tab = st.tabs([
    "📉 Live Chart & Trade", "📘 Option Chain", "💼 Portfolio", "💬 Market Chat"
])

# Helper Functions
@retry(tries=3, delay=2, backoff=2)
def fetch_data(symbol):
    try:
        data = yf.Ticker(symbol).history(period="1d", interval="1m", actions=False)
        if data.empty:
            return None, f"No data available for {symbol}."
        return data, None
    except Exception as e:
        return None, f"Failed to fetch data for {symbol}: {str(e)}"

@retry(tries=3, delay=2, backoff=2)
def get_live_price(ticker):
    try:
        price = yf.Ticker(ticker).history(period="1d", interval="1m")["Close"].iloc[-1]
        return price, None
    except Exception as e:
        return 0.0, f"Failed to fetch price for {ticker}: {str(e)}"

# Live Tab
with live_tab:
    st.subheader(f"📉 {selected_name} - Live Chart & Trading")
    with st.spinner("Fetching live data..."):
        df, error = fetch_data(symbol)

    if error or df is None:
        st.error(f"⚠️ {error}")
    else:
        current_price = df["Close"].iloc[-1]
        st.metric("💰 Current Price", f"₹{current_price:.2f}")
        fig = go.Figure(data=[
            go.Scatter(x=df.index, y=df['Close'], mode='lines', name="Close Price", line=dict(color="#00ff00"))
        ])
        fig.update_layout(
            title=f"{selected_name} Intraday Chart",
            xaxis_title="Time",
            yaxis_title="Price (₹)",
            template="plotly_dark",
            height=400,
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.form("trade_form"):
            qty = st.number_input("Quantity", min_value=1, step=1, value=1)
            action = st.radio("Action", ["Buy", "Sell"], horizontal=True)
            submitted = st.form_submit_button("Execute Trade")

            if submitted:
                if qty <= 0:
                    st.error("❌ Quantity must be positive.")
                else:
                    if action == "Buy":
                        new_trade = pd.DataFrame([{ "Stock": symbol, "Buy Price": current_price, "Qty": qty, "Timestamp": datetime.now() }])
                        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_trade], ignore_index=True)
                        st.success(f"✅ Bought {qty} of {selected_name} @ ₹{current_price:.2f}")
                    elif action == "Sell":
                        match = st.session_state.portfolio[st.session_state.portfolio["Stock"] == symbol]
                        if not match.empty:
                            total_qty = match["Qty"].sum()
                            if qty <= total_qty:
                                remaining_qty = qty
                                for idx in match.index:
                                    held_qty = st.session_state.portfolio.at[idx, "Qty"]
                                    if remaining_qty >= held_qty:
                                        st.session_state.portfolio.at[idx, "Qty"] = 0
                                        remaining_qty -= held_qty
                                    else:
                                        st.session_state.portfolio.at[idx, "Qty"] -= remaining_qty
                                        remaining_qty = 0
                                    if st.session_state.portfolio.at[idx, "Qty"] == 0:
                                        st.session_state.portfolio.drop(index=idx, inplace=True)
                                st.session_state.portfolio.reset_index(drop=True, inplace=True)
                                st.success(f"✅ Sold {qty} of {selected_name} @ ₹{current_price:.2f}")
                            else:
                                st.error(f"❌ Only {total_qty} shares available to sell.")
                        else:
                            st.error("❌ You do not hold this stock.")

# Option Tab
with option_tab:
    st.subheader("📘 Option Chain - NIFTY / BANKNIFTY / SENSEX")
    index_symbol = st.selectbox("Select Index", ["NIFTY", "BANKNIFTY", "SENSEX"])

    with st.spinner(f"Loading {index_symbol} options..."):
        try:
            payload = nse_optionchain_scrapper(index_symbol)
            records = payload.get("records", {})
            all_data = records.get("data", [])
            expiry_dates = records.get("expiryDates", [])
        except Exception as e:
            st.error(f"❌ Failed to load {index_symbol} option data: {str(e)}")
            all_data, expiry_dates = [], []

    if expiry_dates:
        selected_expiry = st.selectbox("Select Expiry", expiry_dates)
        filtered = [d for d in all_data if d.get("expiryDate") == selected_expiry]
        strikes = sorted({d["strikePrice"] for d in filtered if "strikePrice" in d})

        if strikes:
            col1, col2 = st.columns(2)
            with col1:
                selected_strike = st.selectbox("Strike Price", strikes)
            with col2:
                option_type = st.radio("Option Type", ["CE", "PE"], horizontal=True)

            qty = st.number_input("Quantity", min_value=1, step=1, value=1)
            action = st.radio("Action", ["Buy", "Sell"], horizontal=True)

            selected = next((item for item in filtered if item.get("strikePrice") == selected_strike), None)
            if selected:
                opt = selected.get(option_type, {})
                ltp = opt.get("lastPrice", 0.0)
                st.metric("Live Premium (LTP)", f"₹{ltp:.2f}")

                if st.button(f"{action} {option_type}"):
                    st.session_state.option_trades.append({
                        "Index": index_symbol,
                        "Expiry": selected_expiry,
                        "Strike": selected_strike,
                        "Type": option_type,
                        "Action": action,
                        "Qty": qty,
                        "Price": ltp,
                        "Timestamp": datetime.now()
                    })
                    st.success(f"✅ {action} {qty} of {index_symbol} {selected_strike} {option_type} @ ₹{ltp:.2f}")

        # ✅ Group trades and show P&L
        if st.session_state.option_trades:
            st.subheader("📊 Option Positions & P&L")
            df = pd.DataFrame(st.session_state.option_trades)

            def compute_pnl(group):
                net_qty = 0
                avg_buy = 0
                avg_sell = 0
                buy_qty = 0
                sell_qty = 0
                for _, row in group.iterrows():
                    if row["Action"] == "Buy":
                        avg_buy = ((avg_buy * buy_qty) + (row["Price"] * row["Qty"])) / (buy_qty + row["Qty"])
                        buy_qty += row["Qty"]
                        net_qty += row["Qty"]
                    else:
                        avg_sell = ((avg_sell * sell_qty) + (row["Price"] * row["Qty"])) / (sell_qty + row["Qty"])
                        sell_qty += row["Qty"]
                        net_qty -= row["Qty"]
                live_price = ltp if net_qty != 0 else avg_sell
                if net_qty > 0:
                    pnl = (live_price - avg_buy) * net_qty
                elif net_qty < 0:
                    pnl = (avg_sell - live_price) * abs(net_qty)
                else:
                    pnl = (avg_sell - avg_buy) * min(buy_qty, sell_qty)
                return pd.Series({
                    "Net Qty": net_qty,
                    "Avg Buy": round(avg_buy, 2),
                    "Avg Sell": round(avg_sell, 2),
                    "Live Price": round(live_price, 2),
                    "P&L": round(pnl, 2)
                })

            grouped = df.groupby(["Index", "Expiry", "Strike", "Type"]).apply(compute_pnl).reset_index()
            st.dataframe(grouped, use_container_width=True)
    else:
        st.info("Option chain not available. Try again later.")


# Portfolio Tab
with portfolio_tab:
    st.subheader("💼 Portfolio & P&L")
    portfolio_df = st.session_state.portfolio.copy()
    if not portfolio_df.empty:
        portfolio_df["Current Price"] = 0.0
        portfolio_df["PnL"] = 0.0
        with st.spinner("Fetching live prices..."):
            for idx, row in portfolio_df.iterrows():
                price, error = get_live_price(row["Stock"])
                if error:
                    st.warning(f"⚠️ {error}")
                portfolio_df.at[idx, "Current Price"] = price
                portfolio_df.at[idx, "PnL"] = (price - row["Buy Price"]) * row["Qty"]

        st.dataframe(portfolio_df, use_container_width=True)
        total_pnl = portfolio_df["PnL"].sum()
        st.metric("📊 Total P&L", f"₹{total_pnl:.2f}", delta="Positive" if total_pnl >= 0 else "Negative")
    else:
        st.info("No trades yet. Start trading!")

# Chat Tab
with chat_tab:
    st.subheader("💬 Live Market Chat")
    if st.session_state.chat_history:
        for msg in st.session_state.chat_history:
            timestamp = msg.get("timestamp", datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
            st.markdown(f"**🗣️ {msg['user']} ({timestamp}):** {msg['message']}")

        if st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()

    with st.form("chat_form"):
        user = st.text_input("Your Name", max_chars=50)
        message = st.text_area("Message", max_chars=500)
        send = st.form_submit_button("Send")

        if send:
            if not user.strip() or not message.strip():
                st.error("❌ Name and message cannot be empty.")
            else:
                st.session_state.chat_history.append({
                    "user": user.strip(),
                    "message": message.strip(),
                    "timestamp": datetime.now()
                })
                st.rerun()
