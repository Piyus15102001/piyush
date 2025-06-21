import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from nsepython import nse_optionchain_scrapper
from retry import retry

# Page config
st.set_page_config(page_title="Groww-Like Market", layout="wide")
st.title("📈 Groww-Like Market Dashboard")
st_autorefresh(interval=5000, key="refresh")

# Stock tickers
tickers = {
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
    "ULTRACEMCO": "ULTRACEMCO.NS", "WIPRO": "WIPRO.NS", "HDFC BANK": "HDFCBANK.NS",
    "NIFTY 50": "^NSEI"
}

# Initialize session state
if "wallet_balance" not in st.session_state:
    st.session_state.wallet_balance = 100000.0
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["Stock", "Buy Price", "Qty", "Timestamp"])
if "option_trades" not in st.session_state:
    st.session_state.option_trades = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Sidebar controls
st.sidebar.header("💰 Wallet")
st.sidebar.metric("Balance", f"₹{st.session_state.wallet_balance:.2f}")
add_amt = st.sidebar.number_input("Add Money", min_value=0.0, step=100.0)
withdraw_amt = st.sidebar.number_input("Withdraw Money", min_value=0.0, step=100.0)
col1, col2 = st.sidebar.columns(2)
if col1.button("➕ Add"):
    st.session_state.wallet_balance += add_amt
    st.sidebar.success(f"₹{add_amt:.2f} added")
if col2.button("➖ Withdraw"):
    if withdraw_amt <= st.session_state.wallet_balance:
        st.session_state.wallet_balance -= withdraw_amt
        st.sidebar.success(f"₹{withdraw_amt:.2f} withdrawn")
    else:
        st.sidebar.error("Insufficient funds")
if st.sidebar.button("🔁 Reset Wallet"):
    st.session_state.wallet_balance = 100000.0
    st.sidebar.success("Balance reset to ₹100,000")

# Choose stock
st.sidebar.header("📌 Choose Stock")
stock_sel = st.sidebar.selectbox("Select", list(tickers.keys()))
symbol = tickers[stock_sel]

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Live Chart & Trade", "📘 Option Chain", "💼 Portfolio", "💬 Market Chat"
])

# Utility functions
@retry(tries=3, delay=1, backoff=2)
def get_intraday(symbol):
    df = yf.Ticker(symbol).history(period="1d", interval="1m")
    if df.empty:
        raise ValueError("No intraday data")
    return df

@retry(tries=3, delay=1, backoff=2)
def live_price(symbol):
    df = yf.Ticker(symbol).history(period="1d", interval="1m")
    if df.empty:
        raise ValueError("No data")
    return df["Close"].iloc[-1]

# -- Tab 1: Live Chart & Trading --
with tab1:
    st.subheader(f"📈 {stock_sel} - Live Chart & Trade")
    try:
        intraday = get_intraday(symbol)
        price_now = intraday["Close"].iloc[-1]
        st.metric("Current Price", f"₹{price_now:.2f}",
                  delta=f"{price_now - intraday['Open'].iloc[0]:.2f}")

        show_ind = st.toggle("Show Indicators")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=intraday.index, y=intraday["Close"], name="Close"))

        if show_ind:
            intraday['SMA20'] = intraday['Close'].rolling(window=20).mean()
            intraday['EMA20'] = intraday['Close'].ewm(span=20, adjust=False).mean()
            fig.add_trace(go.Scatter(x=intraday.index, y=intraday['SMA20'], name='SMA20'))
            fig.add_trace(go.Scatter(x=intraday.index, y=intraday['EMA20'], name='EMA20'))

        fig.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

        cols = st.columns([1,1,2])
        qty = cols[0].number_input("Quantity", min_value=1, step=1)
        action = cols[1].radio("Action", ["Buy", "Sell"], horizontal=True)
        if cols[2].button("Execute Trade"):
            df = st.session_state.portfolio.copy()
            if action == "Buy":
                df = pd.concat([df, pd.DataFrame([{
                    "Stock": symbol, "Buy Price": price_now,
                    "Qty": qty, "Timestamp": datetime.now()
                }])], ignore_index=True)
                st.session_state.wallet_balance -= price_now * qty
                st.success(f"Bought {qty} {stock_sel}")
            else:
                held = df[df["Stock"] == symbol]
                if held["Qty"].sum() >= qty:
                    rem = qty
                    for idx in held.index:
                        if rem == 0:
                            break
                        q = df.at[idx, "Qty"]
                        if q <= rem:
                            rem -= q
                            df.at[idx, "Qty"] = 0
                        else:
                            df.at[idx, "Qty"] = q - rem
                            rem = 0
                    df = df[df["Qty"] > 0]
                    st.session_state.wallet_balance += price_now * qty
                    st.success(f"Sold {qty} {stock_sel}")
                else:
                    st.error("Not enough shares")
            st.session_state.portfolio = df.reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")

# -- Tab 2: Option Chain --
with tab2:
    st.subheader("📘 Option Chain Trading")

    index_lot_sizes = {"NIFTY": 75, "BANKNIFTY": 30, "SENSEX": 20}
    idx = st.selectbox("Index", list(index_lot_sizes.keys()))
    lot_size = index_lot_sizes[idx]

    try:
        data = nse_optionchain_scrapper(idx)
        records = data["records"]
        exps = records["expiryDates"]

        if exps:
            exp = st.selectbox("Expiry", exps)
            strikes = sorted({r["strikePrice"] for r in records["data"] if r["expiryDate"] == exp})
            strike = st.selectbox("Strike", strikes)
            typ = st.radio("Option Type", ["CE", "PE"], horizontal=True)

            # ✅ Lot Size Selector
            lots = st.number_input("Number of Lots", min_value=1, value=1)
            total_qty = lots * lot_size

            st.markdown(f"🔢 **Lot Size**: {lot_size} × {lots} = {total_qty} units")

            cell = next((x for x in records["data"] if x["expiryDate"] == exp and x["strikePrice"] == strike), None)
            if cell and typ in cell:
                ltp = cell[typ]["lastPrice"]
                st.metric("LTP", f"₹{ltp:.2f}")

                col1, col2 = st.columns(2)

                if col1.button("✅ Buy Option"):
                    cost = ltp * total_qty
                    if st.session_state.wallet_balance >= cost:
                        st.session_state.option_trades.append({
                            "Index": idx, "Expiry": exp, "Strike": strike,
                            "Type": typ, "Qty": total_qty, "Lots": lots,
                            "Price": ltp, "Side": "Buy", "Timestamp": datetime.now()
                        })
                        st.session_state.wallet_balance -= cost
                        st.success(f"Bought {total_qty} units @ ₹{ltp:.2f}")
                    else:
                        st.error("Not enough wallet balance.")

                if col2.button("🛑 Sell Option"):
                    matched_trades = [
                        t for t in st.session_state.option_trades
                        if t["Index"] == idx and t["Expiry"] == exp and
                           t["Strike"] == strike and t["Type"] == typ and t["Side"] == "Buy"
                    ]

                    total_buy_qty = sum(t["Qty"] for t in matched_trades)
                    total_sell_qty = sum(
                        t["Qty"] for t in st.session_state.option_trades
                        if t["Index"] == idx and t["Expiry"] == exp and
                        t["Strike"] == strike and t["Type"] == typ and t["Side"] == "Sell"
                    )
                    net_available_qty = total_buy_qty - total_sell_qty

                    if net_available_qty >= total_qty:
                        # Realized P&L calculation for FIFO exit
                        qty_to_exit = total_qty
                        realized_pnl = 0
                        exit_logs = []

                        for buy_trade in matched_trades:
                            if qty_to_exit == 0:
                                break
                            available = buy_trade["Qty"] - buy_trade.get("SoldQty", 0)
                            exit_qty = min(available, qty_to_exit)
                            buy_price = buy_trade["Price"]
                            pnl = (ltp - buy_price) * exit_qty
                            realized_pnl += pnl
                            qty_to_exit -= exit_qty

                            # Update sold qty on the original trade
                            buy_trade["SoldQty"] = buy_trade.get("SoldQty", 0) + exit_qty

                            # Record exit trade
                            exit_logs.append({
                                "Index": idx, "Expiry": exp, "Strike": strike,
                                "Type": typ, "Qty": exit_qty, "Lots": exit_qty // lot_size,
                                "Price": ltp, "Side": "Sell", "Timestamp": datetime.now(),
                                "Realized_PnL": pnl
                            })

                        # Log sell trades
                        st.session_state.option_trades.extend(exit_logs)

                        st.session_state.wallet_balance += ltp * total_qty
                        st.success(f"Sold {total_qty} units @ ₹{ltp:.2f} | Realized P&L: ₹{realized_pnl:.2f}")
                    else:
                        st.error(f"❌ You only have {net_available_qty} units to sell.")

    except Exception as e:
        st.error(f"Error loading option data: {str(e)}")

    # 🧾 Show trades and P&L
    if st.session_state.option_trades:
        df = pd.DataFrame(st.session_state.option_trades)

        # 🔄 Fetch live LTP for each open position
        for i, row in df.iterrows():
            try:
                opt_cell = next(
                    (x for x in data["records"]["data"]
                     if x["expiryDate"] == row["Expiry"] and x["strikePrice"] == row["Strike"]), None)
                if opt_cell and row["Type"] in opt_cell:
                    df.at[i, "Current Price"] = opt_cell[row["Type"]]["lastPrice"]
            except:
                df.at[i, "Current Price"] = row["Price"]

        # 💹 Calculate P&L
        df["P&L"] = df.apply(lambda x:
            (x["Current Price"] - x["Price"]) * x["Qty"] if x["Side"] == "Buy"
            else (x["Price"] - x["Current Price"]) * x["Qty"], axis=1)
        open_pos = df[df["Side"] == "Buy"].groupby(["Index", "Expiry", "Strike", "Type"]).agg(
            Bought_Qty=("Qty", "sum"),
            Avg_Buy_Price=("Price", "mean")
        ).reset_index()

        sold_pos = df[df["Side"] == "Sell"].groupby(["Index", "Expiry", "Strike", "Type"]).agg(
            Sold_Qty=("Qty", "sum"),
        ).reset_index()

        net_pos = pd.merge(open_pos, sold_pos, on=["Index", "Expiry", "Strike", "Type"], how="left").fillna(0)
        net_pos["Net_Qty"] = net_pos["Bought_Qty"] - net_pos["Sold_Qty"]

        st.markdown("### 📊 Net Option Positions")
        st.dataframe(net_pos[["Index", "Expiry", "Strike", "Type", "Net_Qty", "Avg_Buy_Price"]])
        realized = df[df["Side"] == "Sell"]["Realized_PnL"].sum() if "Realized_PnL" in df else 0
        unrealized = df[df["Side"] == "Buy"]["P&L"].sum()

        st.markdown(f"💸 **Total Realized P&L**: ₹{realized:.2f}")
        st.markdown(f"📈 **Total Unrealized P&L**: ₹{unrealized:.2f}")
        st.download_button("📥 Download Trade History", data=df.to_csv(index=False),
                           file_name="option_trades.csv", mime="text/csv")

# -- Tab 3: Portfolio --
with tab3:
    st.subheader("💼 Portfolio")
    port = st.session_state.portfolio
    if not port.empty:
        port["Live Price"] = port["Stock"].apply(lambda s: live_price(s))
        port["P&L"] = (port["Live Price"] - port["Buy Price"]) * port["Qty"]
        st.dataframe(port.reset_index(drop=True))
        st.metric("Total P&L", f"₹{port['P&L'].sum():.2f}")
    else:
        st.info("No stocks held.")
    st.metric("Wallet Balance", f"₹{st.session_state.wallet_balance:.2f}")

# -- Tab 4: Market Chat --
with tab4:
    st.subheader("💬 Market Chat")

    # Display last 10 chat messages
    hist = st.session_state.chat_history
    for msg in hist[-10:]:
        st.markdown(f"- {msg}")

    # New message input
    with st.form(key="chat_form", clear_on_submit=True):
        new_msg = st.text_input("Enter your market view...")
        submitted = st.form_submit_button("Send")
        if submitted and new_msg.strip():
            # Simple sentiment tagging
            msg_lower = new_msg.lower()
            if "buy" in msg_lower or "bull" in msg_lower or "up" in msg_lower:
                emoji = "📈"
            elif "sell" in msg_lower or "bear" in msg_lower or "down" in msg_lower:
                emoji = "📉"
            else:
                emoji = "🤔"
            tagged_msg = f"{emoji} {new_msg.strip()}"
            st.session_state.chat_history.append(tagged_msg)
            st.success("Message sent!")
