import os
import requests
import yfinance as yf
import pandas as pd
import ccxt
from datetime import datetime

# --- 設定 Telegram 參數 (從環境變數讀取) ---
TG_TOKEN = os.environ.get('TG_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

def get_data():
    print("正在抓取數據...")
    
    # 1. 抓取 Yahoo 數據 (新增 DXY 美元指數)
    tickers = ["^VIX", "^VVIX", "BTC-USD", "DX-Y.NYB"]
    
    try:
        data = yf.download(tickers, period="5d", progress=False)
    except Exception as e:
        print(f"Yahoo 下載失敗: {e}")
        return None

    # 輔助函數：安全提取數據
    def get_last_val(ticker):
        try:
            if 'Close' in data.columns:
                df = data['Close']
            else:
                df = data
            
            series = df[ticker] if ticker in df.columns else df.iloc[:, 0]
            valid_series = series.dropna()
            return float(valid_series.iloc[-1]) if not valid_series.empty else 0.0
        except:
            return 0.0

    cur_vix = get_last_val("^VIX")
    cur_vvix = get_last_val("^VVIX")
    cur_btc = get_last_val("BTC-USD")
    cur_dxy = get_last_val("DX-Y.NYB") # 美元指數

    # 2. 計算 Mayer Multiple
    try:
        btc_hist = yf.download("BTC-USD", period="1y", progress=False)['Close']
        if isinstance(btc_hist, pd.DataFrame): btc_hist = btc_hist.iloc[:, 0]
        ma200 = float(btc_hist.rolling(window=200).mean().iloc[-1])
        mayer = cur_btc / ma200 if ma200 > 0 else 0
    except:
        mayer = 0

    # 3. 抓取幣安數據 (資金費率)
    binance = ccxt.binance()
    try:
        funding = binance.fapiPublic_get_premiumindex({'symbol': 'BTCUSDT'})
        fr = float(funding['lastFundingRate']) * 100
    except:
        fr = 0.0

    # 4. 抓取 恐慌貪婪指數 (Alternative.me API)
    fng_val = 50 # 預設中性
    fng_text = "Neutral"
    try:
        fng_resp = requests.get("https://api.alternative.me/fng/").json()
        fng_data = fng_resp['data'][0]
        fng_val = int(fng_data['value'])
        fng_text = fng_data['value_classification']
    except:
        pass

    return {
        "vix": cur_vix, "vvix": cur_vvix, "btc": cur_btc, 
        "dxy": cur_dxy, "mayer": mayer, "fr": fr,
        "fng_val": fng_val, "fng_text": fng_text
    }

def analyze_and_send():
    d = get_data()
    if not d: return

    # --- 智能策略判讀 ---
    # 預設狀態
    signal = "⚖️ **震盪觀望**"
    action = "網格交易 / 觀望"

    # 判斷邏輯
    # 1. 鑽石底：估值便宜 + 市場恐慌
    if d['mayer'] < 0.8 and d['vix'] > 30:
        signal = "🚀 **鑽石買點 (Diamond Buy)**"
        action = "大資金分批抄底 (勝率極高)"
    
    # 2. 黃金坑：估值便宜 (但市場不一定恐慌，適合定投)
    elif d['mayer'] < 0.8:
        signal = "💎 **價值低估區 (Deep Value)**"
        action = "開啟定投 / 囤幣模式"
    
    # 3. 恐慌拋售：VIX 炸裂 (可能有更低點，但也適合左側)
    elif d['vix'] > 30:
        signal = "🔥 **恐慌拋售 (Panic Sell)**"
        action = "分批接刀 (注意 DXY 是否過高)"
    
    # 4. 短線機會：資金費率負值 (軋空)
    elif d['fr'] < -0.01:
        signal = "⚡ **短線軋空 (Squeeze)**"
        action = "短線做多博反彈"

    # 5. 風險提示：頂部特徵
    elif d['mayer'] > 2.4:
        signal = "🔴 **頂部風險 (Top Risk)**"
        action = "分批止盈，切勿追高"

    # --- 組合 Telegram 訊息 ---
    msg = f"""
📊 **Phyrex 宏觀狙擊日報**
📅 {datetime.now().strftime("%Y-%m-%d")}
-------------------------------
**{signal}**
💡 策略：{action}
-------------------------------
**1. 資金與宏觀 (Fuel)**
• 美元指數 (DXY): `{d['dxy']:.2f}`
  *(>105 壓制幣價 / <100 利好)*
• VIX 恐慌指數: `{d['vix']:.2f}`
  *(>30 恐慌 / <15 貪婪)*

**2. 比特幣估值 (Value)**
• 價格: `${d['btc']:,.0f}`
• Mayer 倍數: `{d['mayer']:.2f}`
  *(<0.8 抄底區 / >2.4 逃頂區)*

**3. 市場情緒 (Sentiment)**
• 恐慌貪婪指數: `{d['fng_val']}` ({d['fng_text']})
• 資金費率: `{d['fr']:.4f}%`
-------------------------------
_Powered by GitHub Actions_
"""

    # 發送
    if TG_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            print("✅ 訊息發送成功")
        except Exception as e:
            print(f"❌ 發送失敗: {e}")
    else:
        print("❌ 請設定環境變數")

if __name__ == "__main__":
    analyze_and_send()
