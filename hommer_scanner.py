import yfinance as yf
import pandas as pd
import streamlit as st
import requests
import io
import os
import time
import random
import pytz
from datetime import datetime, timedelta

tw_tz = pytz.timezone('Asia/Taipei')

# ─────────────────────────────────────────────────────────────────
# 🔧 雙引擎資料抓取：stooq 優先（不封鎖雲端）→ yfinance 備援
# ─────────────────────────────────────────────────────────────────
def to_stooq_symbol(symbol: str) -> str:
    """將 yfinance 代號轉為 stooq 格式"""
    if symbol == '^TWII':
        return '^twii'          # 加權指數：stooq 使用小寫
    if symbol == 'TX=F':
        return None             # 台指期：stooq 不支援
    return symbol.replace('.TW', '.tw')  # 2330.TW → 2330.tw

def fetch_weekly_data(symbol: str, session: requests.Session) -> pd.DataFrame:
    """
    雙引擎 K 線抓取：
    層一：stooq CSV 直接 HTTP 呼叫 — 不需額外套件、不封鎖雲端 IP
    層二：yfinance — 本地環境備援
    """
    # ─── 層一：stooq CSV API（直接 HTTP，無需 pandas_datareader）───
    stooq_sym = to_stooq_symbol(symbol)
    if stooq_sym is not None:
        try:
            url = f"https://stooq.com/q/d/l/?s={stooq_sym}&i=w"
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 50:
                df = pd.read_csv(io.StringIO(resp.text))
                df.columns = [c.strip() for c in df.columns]
                if 'Date' in df.columns and 'Close' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.sort_values('Date').set_index('Date')
                    df = df[['Open', 'High', 'Low', 'Close']].dropna()
                    if len(df) >= 1:
                        return df.tail(8)  # 最近 8 週
        except Exception:
            pass

    # ─── 層二：yfinance（備援，雲端可能被封）───────────────────
    try:
        ticker = yf.Ticker(symbol, session=session)
        df = ticker.history(period='1mo', interval='1wk')
        if df is not None and not df.empty:
            return df[['Open', 'High', 'Low', 'Close']].dropna()
    except Exception:
        pass

    return pd.DataFrame()  # 兩層都失敗

# 網頁環境設定
st.set_page_config(page_title="AI 投資理財助手", layout="wide")
st.title("🛡️ 台灣 50 + 大盤風向球 - 週線長腿雷達")
now_tw = datetime.now(tw_tz)
st.write(f"� 目前雲端掃描時間 (台灣): {now_tw.strftime('%Y-%m-%d %H:%M:%S')}")

# ✨ 升級：建立「商品名稱字典」，加入加權指數與台指期
symbol_dict = {
    "^TWII": "加權指數", "TX=F": "台指近全",
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2308.TW": "台達電", "2382.TW": "廣達",
    "2395.TW": "研華", "2412.TW": "中華電", "2881.TW": "富邦金", "2882.TW": "國泰金", "2891.TW": "中信金",
    "1216.TW": "統一", "1301.TW": "台塑", "1303.TW": "南亞", "1326.TW": "台化", "2002.TW": "中鋼",
    "2207.TW": "和泰車", "2301.TW": "光寶科", "2303.TW": "聯電", "2324.TW": "仁寶", "2345.TW": "智邦",
    "2357.TW": "華碩", "2379.TW": "瑞昱", "2408.TW": "南亞科", "2603.TW": "長榮", "2880.TW": "華南金",
    "2883.TW": "開發金", "2884.TW": "玉山金", "2885.TW": "元大金", "2886.TW": "兆豐金", "2887.TW": "台新金",
    "2890.TW": "永豐金", "2892.TW": "第一金", "2912.TW": "統一超", "3008.TW": "大立光", "3034.TW": "聯詠",
    "3045.TW": "台灣大", "3231.TW": "緯創", "3711.TW": "日月光投控", "4904.TW": "遠傳", "4938.TW": "和碩",
    "5871.TW": "中租-KY", "5876.TW": "上海商銀", "5880.TW": "合庫金", "6505.TW": "台塑化", "6669.TW": "緯穎",
    "9904.TW": "寶成", "9910.TW": "豐泰", "2609.TW": "陽明", "2615.TW": "萬海"
}

# 🔧 壓力測試：先只掃 3 檔，確認雲端能抓到資料後再恢復全量
# scan_list = list(symbol_dict.keys())  # ← 全量，確認可用後再解除注解
scan_list = ['^TWII', '2330.TW', '2317.TW']  # ← 壓力測試 3 檔（含大盤）

# 建立記憶體
if 'scan_result' not in st.session_state:
    st.session_state.scan_result = pd.DataFrame()

if st.button('🚀 啟動掃描 (含大盤、期貨與中文名稱)'):
    with st.spinner('正在掃描台股標的（雙引擎模式：yfinance + stooq）...'):
        # 共用的 requests Session，使用較少見的舊版 UA 避免被需
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'python-requests/2.28.2',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

        results = []
        for symbol in scan_list:
            try:
                # ✅ 呼叫雙引擎函式（yfinance 先，stooq 備援）
                df_stock = fetch_weekly_data(symbol, session)

                # ✨ 特權防呆：大盤與期貨即使資料不足也絕對顯示
                is_index = symbol in ("^TWII", "TX=F")
                if df_stock.empty or len(df_stock) < 1:
                    st.warning(f"⚠️ 無法取得資料：{symbol}")
                    if not is_index:
                        time.sleep(random.uniform(0.3, 0.7))
                        continue
                    change_pct, body, lower_shadow, ratio = 0, 0, 0, 0
                    curr = {"Close": 0, "Open": 0, "Low": 0, "High": 0}
                elif len(df_stock) < 2:
                    curr = df_stock.iloc[-1]
                    if is_index:
                        change_pct = 0
                    else:
                        st.warning(f"⚠️ 資料筆數不足（僅 1 筆）：{symbol}")
                        time.sleep(random.uniform(0.3, 0.7))
                        continue
                    body = abs(curr['Open'] - curr['Close'])
                    lower_shadow = min(curr['Open'], curr['Close']) - curr['Low']
                    ratio = lower_shadow / body if body > 0 else lower_shadow
                else:
                    curr, prev = df_stock.iloc[-1], df_stock.iloc[-2]
                    body = abs(curr['Open'] - curr['Close'])
                    lower_shadow = min(curr['Open'], curr['Close']) - curr['Low']
                    ratio = lower_shadow / body if body > 0 else lower_shadow
                    change_pct = (curr['Close'] - prev['Close']) / prev['Close'] * 100

                # ✨ TradingView 連結
                if symbol == "^TWII":
                    stock_num = "大盤"
                    tv_url = "https://tw.tradingview.com/chart/?symbol=TWSE%3ATAIEX"
                elif symbol == "TX=F":
                    stock_num = "期貨"
                    tv_url = "https://tw.tradingview.com/chart/?symbol=TAIFEX%3ATX1!"
                else:
                    stock_num = symbol.replace(".TW", "")
                    tv_url = f"https://tw.tradingview.com/chart/?symbol=TWSE%3A{stock_num}"

                stock_name = symbol_dict.get(symbol, "未知商品")

                results.append({
                    "代號": stock_num,
                    "商品名稱": stock_name,
                    "現價": round(curr['Close'], 2),
                    "漲跌幅(%)": round(change_pct, 2),
                    "下影線倍數": round(ratio, 2),
                    "訊號": "✅ 長腿出現" if ratio >= 1.5 and lower_shadow > 0 else "---",
                    "看盤連結": tv_url
                })

                # 隨機延遲 0.5 ± 0.2 秒，避免抓太快被封鎖
                time.sleep(random.uniform(0.3, 0.7))

            except Exception as e:
                st.warning(f"⚠️ 例外錯誤：{symbol} → {e}")
                continue

        st.session_state.scan_result = pd.DataFrame(results)
        if not results:
            st.info("ℹ️ 目前抓取結果為空，请確認 yfinance 版本與雲端網路連線是否正常。")

# 顯示介面與過濾邏輯
if not st.session_state.scan_result.empty:
    df_res = st.session_state.scan_result
    st.write("### 📊 掃描報表")
    
    show_only_hammers = st.checkbox("🎯 只顯示『長腿出現』的標的，並依照下影線長度排序", value=False)
    display_df = df_res.copy()
    
    if show_only_hammers:
        display_df = display_df[display_df['訊號'] == "✅ 長腿出現"]
        display_df = display_df.sort_values(by="下影線倍數", ascending=False)
        
    st.dataframe(
        display_df.style.highlight_max(axis=0, subset=['下影線倍數'], color='#FFD700'),
        column_config={
            "現價": st.column_config.NumberColumn(format="%.2f"),
            "漲跌幅(%)": st.column_config.NumberColumn(format="%.2f"),
            "下影線倍數": st.column_config.NumberColumn(format="%.2f"),
            "看盤連結": st.column_config.LinkColumn("📈 TradingView", display_text="點我看圖 🔍")
        },
        use_container_width=True
    )