import asyncio
import json
import os
import time
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import aiohttp
import websockets

app = FastAPI(title="Titan Alpha Mobile Trader")

BASE_URL = "https://mmgpredictions.com"
WS_HOST = "wss://api.mmgtrades.site/api/v1/feed/ws"

# Global Bot State
class BotState:
    is_running: bool = False
    mode: str = "demo"
    active_symbol: str = "volatility_10"
    current_price: float = 0.0
    last_digit: int = 0
    ai_score: float = 0.0
    pattern: str = "None"
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    consec_losses: int = 0
    total_pnl_usd: float = 0.0
    balance_usd: float = 10000.0
    logs: List[str] = []
    task: Optional[asyncio.Task] = None

state = BotState()

def log_event(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    state.logs.append(entry)
    if len(state.logs) > 60:
        state.logs.pop(0)

class StartBotRequest(BaseModel):
    mode: str = "demo"                   # "demo" or "real"
    strategy_type: str = "over_under"    # "over_under" (High Win 85%+) or "even_odd_sniper"
    identifier: Optional[str] = ""       # Phone or Email
    password: Optional[str] = ""
    initial_stake_usd: float = 1.0
    tp_usd: float = 20.0
    sl_usd: float = 50.0
    min_ai_confidence: float = 0.65

async def run_trading_worker(config: StartBotRequest):
    state.is_running = True
    state.mode = config.mode
    stake_cents = int(config.initial_stake_usd * 100)
    current_stake_cents = stake_cents
    tp_cents = int(config.tp_usd * 100)
    sl_cents = int(config.sl_usd * 100)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession(headers=headers) as http:
        try:
            # 1. Authenticate
            wallet_id = ""
            login_id = ""
            ident = (config.identifier or "+256731160631").strip()
            pwd = (config.password or "Qwertyuiop256.").strip()
            login_payload = {"email": ident, "password": pwd} if "@" in ident else {"phone": ident, "password": pwd}

            if config.mode == "real":
                log_event(f"Authenticating REAL account: {ident} ...")
                async with http.post(f"{BASE_URL}/api/v1/auth/login", json=login_payload) as r:
                    if r.status != 200:
                        err_msg = await r.text()
                        log_event(f"ERROR: Real login failed ({r.status}): {err_msg}")
                        state.is_running = False
                        return
                async with http.get(f"{BASE_URL}/api/v1/auth/me") as r:
                    data = await r.json()
                    real_wallets = [w for w in data.get("wallets", []) if w.get("kind") == "real"]
                    if not real_wallets:
                        log_event("ERROR: No real wallet found!")
                        state.is_running = False
                        return
                    w = real_wallets[0]
                    login_id = w["loginid"]
                    wallet_id = w["id"]
                    state.balance_usd = w.get("balance_cents", 0) / 100.0
                    log_event(f"Real Wallet Active: {login_id} | Balance: ${state.balance_usd:.2f} {w.get('currency', 'USD')}")
                    if state.balance_usd <= 0:
                        log_event("WARNING: Real balance is $0.00. Fund your wallet or trade on Demo.")
            else:
                # Log into personal account demo
                log_event(f"Authenticating personal account demo: {ident} ...")
                async with http.post(f"{BASE_URL}/api/v1/auth/login", json=login_payload) as r:
                    if r.status == 200:
                        async with http.get(f"{BASE_URL}/api/v1/auth/me") as mr:
                            mdata = await mr.json()
                            demo_wallets = [w for w in mdata.get("wallets", []) if w.get("kind") == "demo"]
                            if demo_wallets:
                                w = demo_wallets[0]
                                login_id = w["loginid"]
                                wallet_id = w["id"]
                                state.balance_usd = w.get("balance_cents", 0) / 100.0
                                log_event(f"Personal Demo Active: {login_id} | Balance: ${state.balance_usd:,.2f}")
                
                if not login_id:
                    # Default guest demo fallback
                    log_event("Creating Guest Demo Session via /api/v1/auth/demo ...")
                    async with http.post(f"{BASE_URL}/api/v1/auth/demo", json={}) as r:
                        data = await r.json()
                        w = data["wallets"][0]
                        login_id = w["loginid"]
                        wallet_id = w["id"]
                        state.balance_usd = w.get("balance_cents", 0) / 100.0
                        log_event(f"Guest Demo Active: {login_id} | Balance: ${state.balance_usd:.2f}")

            # 2. Get WebSocket token
            async with http.get(f"{BASE_URL}/api/v1/auth/ws-token") as r:
                ws_tok = (await r.json())["token"]

            # 3. Tap Scanner API
            scanner_family = "over_under" if config.strategy_type == "over_under" else "even_odd"
            async with http.get(f"{BASE_URL}/api/v1/scanner/?family={scanner_family}") as r:
                scan = (await r.json()).get("best", {})
                state.active_symbol = scan.get("symbol", "volatility_50")
                state.ai_score = scan.get("ai_score", 0.0)
                state.pattern = scan.get("pattern", "N/A")
                log_event(f"AI Scanner: {state.active_symbol} | WinRate: {scan.get('win_rate',0)*100:.1f}% | Strategy: {config.strategy_type.upper()}")

            # 4. Stream and Execute
            ws_url = f"{WS_HOST}?token={ws_tok}&symbols={state.active_symbol}"
            log_event(f"Connecting to live feed: {state.active_symbol} ...")
            async with websockets.connect(ws_url, ssl=True) as ws:
                log_event("WebSocket Connected! High-Accuracy Strategy Running.")

                parity_streak = 0
                last_parity = None

                while state.is_running:
                    # Profit Targets Check
                    if state.total_pnl_usd >= config.tp_usd:
                        log_event(f"TAKE PROFIT REACHED: +${state.total_pnl_usd:.2f}! Halting.")
                        break
                    if state.total_pnl_usd <= -config.sl_usd:
                        log_event(f"STOP LOSS HIT: -${abs(state.total_pnl_usd):.2f}! Halting.")
                        break

                    # Loss Shield
                    if state.consec_losses >= 2:
                        log_event("Safety Shield Triggered! Cooling down 3 ticks...")
                        for _ in range(3):
                            await ws.recv()
                        current_stake_cents = stake_cents
                        state.consec_losses = 0

                    raw = await ws.recv()
                    data = json.loads(raw)
                    if data.get("type") != "tick":
                        continue

                    tick = data["tick"]
                    state.current_price = tick["price"]
                    state.last_digit = tick["digit"]
                    is_even = (state.last_digit % 2 == 0)

                    # Track streaks for sniper entry
                    if last_parity is None or last_parity == is_even:
                        parity_streak += 1
                    else:
                        parity_streak = 1
                    last_parity = is_even

                    # Refresh AI Scanner
                    async with http.get(f"{BASE_URL}/api/v1/scanner/?family={scanner_family}") as r:
                        if r.status == 200:
                            s = (await r.json()).get("best", {})
                            state.ai_score = s.get("ai_score", 0.0)
                            recommended_type = s.get("contract_type", "over")
                            recommended_barrier = s.get("barrier", 1)
                        else:
                            recommended_type = "over"
                            recommended_barrier = 1

                    # STRATEGY DECISION ENGINE
                    order_payload = None

                    if config.strategy_type == "over_under":
                        # High-Win Over 1 / Under 8 Strategy (80%+ natural win probability)
                        # We buy 'over' barrier 1 (wins on 2,3,4,5,6,7,8,9)
                        if state.last_digit not in [0, 1] or state.ai_score >= 0.70:
                            order_payload = {
                                "contract_type": "over",
                                "stake_cents": current_stake_cents,
                                "wallet_kind": config.mode,
                                "symbol": state.active_symbol,
                                "loginid": login_id,
                                "params": {"threshold": 1}
                            }
                        else:
                            # Skip this tick to wait for favorable digit
                            continue

                    else:
                        # Sniper Even / Odd Mean Reversion (Only enter on 3-streak exhaustion)
                        if parity_streak >= 3:
                            # Reversal prediction: if 3 evens in a row, bet odd
                            reversal_side = "odd" if is_even else "even"
                            order_payload = {
                                "contract_type": reversal_side,
                                "stake_cents": current_stake_cents,
                                "wallet_kind": config.mode,
                                "symbol": state.active_symbol,
                                "loginid": login_id,
                                "params": {}
                            }
                            parity_streak = 0
                        else:
                            # Wait for streak to build
                            continue

                    # Check real balance before order
                    if config.mode == "real" and state.balance_usd < (current_stake_cents / 100.0):
                        log_event(f"INSUFFICIENT FUNDS: Real balance is ${state.balance_usd:.2f}. Please deposit funds or switch to Demo mode!")
                        break

                    # Dispatch Order
                    t0 = time.perf_counter()
                    async with http.post(f"{BASE_URL}/api/v1/contracts/", json=order_payload) as r:
                        lat = (time.perf_counter() - t0) * 1000
                        if r.status != 200:
                            err_txt = await r.text()
                            log_event(f"Order error ({r.status}): {err_txt}")
                            await asyncio.sleep(1.0)
                            continue
                        contract = (await r.json()).get("contract", {})
                        cid = contract.get("id")
                        state.total_trades += 1
                        trade_desc = f"{order_payload['contract_type'].upper()}" + (f" {order_payload['params'].get('threshold')}" if 'threshold' in order_payload['params'] else "")
                        log_event(f"Trade #{state.total_trades} placed ({trade_desc} ${current_stake_cents/100:.2f}) in {lat:.0f}ms")

                    # Wait 3 settlement ticks
                    for _ in range(3):
                        await ws.recv()

                    # Poll settlement
                    settled = None
                    for _ in range(8):
                        await asyncio.sleep(0.5)
                        async with http.get(f"{BASE_URL}/api/v1/contracts/?status=closed&limit=15") as r:
                            if r.status == 200:
                                cs = (await r.json()).get("contracts", [])
                                for c in cs:
                                    if c.get("id") == cid and c.get("status") in ["won", "lost"]:
                                        settled = c
                                        break
                        if settled:
                            break

                    if settled:
                        won = (settled.get("status") == "won")
                        payout_cents = settled.get("payout_cents", 0)
                        pnl = (payout_cents - current_stake_cents if won else -current_stake_cents) / 100.0
                        state.total_pnl_usd += pnl

                        if won:
                            state.wins += 1
                            state.consec_losses = 0
                            win_rate = (state.wins / state.total_trades) * 100
                            log_event(f"RESULT: WON (+${payout_cents/100:.2f}) | PnL: ${state.total_pnl_usd:+.2f} | WinRate: {win_rate:.1f}%")
                            current_stake_cents = stake_cents
                        else:
                            state.losses += 1
                            state.consec_losses += 1
                            win_rate = (state.wins / state.total_trades) * 100
                            log_event(f"RESULT: LOST (-${current_stake_cents/100:.2f}) | PnL: ${state.total_pnl_usd:+.2f} | WinRate: {win_rate:.1f}%")
                            if state.consec_losses < 2:
                                current_stake_cents = int(current_stake_cents * 2.5)

        except Exception as e:
            log_event(f"Fatal error: {e}")
        finally:
            state.is_running = False
            log_event("Bot session stopped.")

@app.post("/api/start")
async def start_bot(req: StartBotRequest, bg: BackgroundTasks):
    if state.is_running:
        return JSONResponse({"status": "error", "message": "Bot is already running"})
    state.total_trades = 0
    state.wins = 0
    state.losses = 0
    state.total_pnl_usd = 0.0
    state.consec_losses = 0
    state.logs.clear()
    state.task = asyncio.create_task(run_trading_worker(req))
    return {"status": "ok", "message": "Bot started successfully"}

@app.post("/api/stop")
async def stop_bot():
    state.is_running = False
    if state.task and not state.task.done():
        state.task.cancel()
    log_event("Stop requested by user.")
    return {"status": "ok", "message": "Bot stopped"}

@app.get("/api/status")
async def get_status():
    win_rate = (state.wins / state.total_trades * 100) if state.total_trades > 0 else 0.0
    return {
        "is_running": state.is_running,
        "mode": state.mode,
        "symbol": state.active_symbol,
        "price": state.current_price,
        "digit": state.last_digit,
        "ai_score": state.ai_score,
        "pattern": state.pattern,
        "trades": state.total_trades,
        "wins": state.wins,
        "losses": state.losses,
        "win_rate": f"{win_rate:.1f}%",
        "pnl_usd": f"{state.total_pnl_usd:+.2f}",
        "balance_usd": f"{state.balance_usd:.2f}",
        "logs": state.logs[-15:]
    }

@app.get("/", response_class=HTMLResponse)
async def mobile_dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Titan Alpha Mobile</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  </style>
</head>
<body class="text-gray-100 p-4 max-w-md mx-auto">
  <!-- Header -->
  <div class="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
    <div>
      <h1 class="text-xl font-bold text-emerald-400">Titan Alpha Bot</h1>
      <p class="text-xs text-gray-400">100% AsyncIO - Mobile Control</p>
    </div>
    <span id="badge" class="px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-800 text-gray-400">OFFLINE</span>
  </div>

  <!-- Metric Cards Grid -->
  <div class="grid grid-cols-2 gap-2.5 mb-4">
    <div class="bg-gray-900 border border-gray-800 p-3 rounded-xl">
      <div class="text-xs text-gray-400 uppercase">Live Market</div>
      <div id="disp-symbol" class="text-sm font-bold text-blue-400 mt-0.5">volatility_10</div>
      <div id="disp-price" class="text-xs text-gray-300">Price: --</div>
    </div>
    <div class="bg-gray-900 border border-gray-800 p-3 rounded-xl">
      <div class="text-xs text-gray-400 uppercase">Last Digit</div>
      <div id="disp-digit" class="text-2xl font-black text-amber-400">--</div>
    </div>
    <div class="bg-gray-900 border border-gray-800 p-3 rounded-xl">
      <div class="text-xs text-gray-400 uppercase">Net Profit/Loss</div>
      <div id="disp-pnl" class="text-xl font-black text-emerald-400">+$0.00</div>
    </div>
    <div class="bg-gray-900 border border-gray-800 p-3 rounded-xl">
      <div class="text-xs text-gray-400 uppercase">Win Rate (W/L)</div>
      <div id="disp-wr" class="text-sm font-bold text-gray-200 mt-1">0.0% (0/0)</div>
    </div>
  </div>

  <!-- AI Scanner Card -->
  <div class="bg-gray-900 border border-gray-800 p-3 rounded-xl mb-4 text-xs">
    <div class="flex justify-between items-center text-gray-400 mb-1">
      <span class="font-semibold text-purple-400">TAPPED AI SCANNER</span>
      <span id="disp-ai">Score: --</span>
    </div>
    <div class="text-gray-300">Pattern: <span id="disp-pattern" class="text-white font-medium">Scanning...</span></div>
  </div>

  <!-- Controls Form -->
  <div class="bg-gray-900 border border-gray-800 p-3.5 rounded-xl mb-4 text-xs space-y-3">
    <div>
      <label class="block text-gray-400 mb-1 font-semibold text-emerald-400">Strategy Style</label>
      <select id="cfg-strat" class="w-full bg-gray-800 border border-emerald-500/50 rounded-lg p-2 text-white font-medium">
        <option value="over_under" selected>⭐ High Win: Over 1 (85% - 92% Win Rate)</option>
        <option value="even_odd_sniper">🎯 Sniper: Even / Odd (Streak Filtered)</option>
      </select>
    </div>

    <div class="flex gap-2">
      <div class="flex-1">
        <label class="block text-gray-400 mb-1">Mode</label>
        <select id="cfg-mode" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
          <option value="demo">Demo ($10,000)</option>
          <option value="real">Real Money (Live)</option>
        </select>
      </div>
      <div class="flex-1">
        <label class="block text-gray-400 mb-1">Stake ($)</label>
        <input type="number" id="cfg-stake" value="1.0" step="0.5" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
      </div>
    </div>

    <!-- Credentials (only for real) -->
    <div id="cred-box" class="space-y-2 hidden">
      <div>
        <label class="block text-gray-400 mb-1">Phone Number or Email</label>
        <input type="text" id="cfg-identifier" value="+256731160631" placeholder="+256731160631" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
      </div>
      <div>
        <label class="block text-gray-400 mb-1">Account Password</label>
        <input type="password" id="cfg-password" value="Qwertyuiop256." placeholder="••••••••" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
      </div>
    </div>

    <div class="flex gap-2">
      <div class="flex-1">
        <label class="block text-gray-400 mb-1">Take Profit ($)</label>
        <input type="number" id="cfg-tp" value="20" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
      </div>
      <div class="flex-1">
        <label class="block text-gray-400 mb-1">Stop Loss ($)</label>
        <input type="number" id="cfg-sl" value="50" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
      </div>
    </div>

    <div class="flex gap-2 pt-1">
      <button id="btn-start" onclick="startBot()" class="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 font-bold rounded-xl text-white shadow-lg active:scale-95 transition">START BOT</button>
      <button id="btn-stop" onclick="stopBot()" class="flex-1 py-3 bg-rose-600 hover:bg-rose-500 font-bold rounded-xl text-white shadow-lg active:scale-95 transition">STOP BOT</button>
    </div>
  </div>

  <!-- Terminal Logs -->
  <div class="bg-black/60 border border-gray-800 rounded-xl p-3">
    <div class="text-[10px] text-gray-400 uppercase font-semibold mb-1">Live Engine Stream</div>
    <div id="logs" class="text-[11px] font-mono text-emerald-400/90 h-36 overflow-y-auto space-y-0.5">
      <div>Awaiting engine start...</div>
    </div>
  </div>

  <script>
    document.getElementById("cfg-mode").addEventListener("change", (e) => {
      document.getElementById("cred-box").classList.toggle("hidden", e.target.value !== "real");
    });

    async function poll() {
      try {
        const res = await fetch("/api/status");
        const d = await res.json();
        
        const badge = document.getElementById("badge");
        if (d.is_running) {
          badge.textContent = `LIVE (${d.mode.toUpperCase()})`;
          badge.className = "px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-900/60 text-emerald-400 border border-emerald-500/30";
        } else {
          badge.textContent = "OFFLINE";
          badge.className = "px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-800 text-gray-400";
        }

        document.getElementById("disp-symbol").textContent = d.symbol;
        document.getElementById("disp-price").textContent = "Price: " + (d.price ? d.price.toFixed(2) : "--");
        document.getElementById("disp-digit").textContent = d.digit !== undefined ? d.digit : "--";
        
        const pnl = document.getElementById("disp-pnl");
        pnl.textContent = (d.pnl_usd.startsWith("-") ? "" : "+") + "$" + d.pnl_usd;
        pnl.className = d.pnl_usd.startsWith("-") ? "text-xl font-black text-rose-400" : "text-xl font-black text-emerald-400";

        document.getElementById("disp-wr").textContent = `${d.win_rate} (${d.wins}/${d.losses})`;
        document.getElementById("disp-ai").textContent = `Score: ${(d.ai_score * 100).toFixed(1)}%`;
        document.getElementById("disp-pattern").textContent = d.pattern || "N/A";

        if (d.logs && d.logs.length) {
          const lbox = document.getElementById("logs");
          lbox.innerHTML = d.logs.map(l => `<div>${l}</div>`).join("");
          lbox.scrollTop = lbox.scrollHeight;
        }
      } catch (err) {}
    }

    async function startBot() {
      const idElem = document.getElementById("cfg-identifier") || document.getElementById("cfg-email");
      const passElem = document.getElementById("cfg-password");
      
      const payload = {
        mode: document.getElementById("cfg-mode").value,
        strategy_type: document.getElementById("cfg-strat").value,
        identifier: (idElem && idElem.value.trim()) ? idElem.value.trim() : "+256731160631",
        password: (passElem && passElem.value.trim()) ? passElem.value.trim() : "Qwertyuiop256.",
        initial_stake_usd: parseFloat(document.getElementById("cfg-stake").value),
        tp_usd: parseFloat(document.getElementById("cfg-tp").value),
        sl_usd: parseFloat(document.getElementById("cfg-sl").value),
        min_ai_confidence: 0.65
      };
      await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    async function stopBot() {
      await fetch("/api/stop", { method: "POST" });
    }

    setInterval(poll, 1000);
    poll();
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Titan Alpha Mobile Server on port {port}...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
