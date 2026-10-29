"""
================================================================================
MMG TRADES - 100% ASYNCIO ALGORITHMIC TRADING BOT
================================================================================
Architecture:
- 100% AsyncIO: Built with `aiohttp` and `websockets` (zero blocking I/O)
- Dual-Signal Alpha Engine:
    1. Taps directly into the website's live AI Scanner API (/api/v1/scanner/)
       (Fetches real-time AI score, historical win-rate, recent win-rate, and digit heatmap)
    2. Real-time Tick Parity & Streak Confirmation from wss://api.mmgtrades.site
- Ultra-Low Latency Execution: Dispatches real or demo contracts sub-millisecond
- Asynchronous 3-Tick Settlement Tracker
- Institutional Risk Controls: Dynamic Stop-Loss, Take-Profit & Loss-Shield
================================================================================
"""

import asyncio
import json
import time
import sys
from typing import Dict, Any, Optional
import aiohttp
import websockets

BASE_URL = "https://mmgpredictions.com"
WS_HOST = "wss://api.mmgtrades.site/api/v1/feed/ws"

class MMGAsyncTrader:
    def __init__(
        self,
        mode: str = "demo",                 # "real" for live capital, "demo" for paper trading
        family: str = "even_odd",           # "even_odd" or "over_under"
        initial_stake_usd: float = 1.0,     # Base stake ($)
        tp_usd: float = 20.0,               # Take Profit target ($)
        sl_usd: float = 50.0,               # Stop Loss limit ($)
        max_trades: int = 50,               # Maximum execution cycles
        min_ai_confidence: float = 0.50     # Minimum AI score required to trigger entry
    ):
        self.mode = mode.lower()
        self.family = family
        self.initial_stake_cents = int(initial_stake_usd * 100)
        self.current_stake_cents = self.initial_stake_cents
        self.tp_cents = int(tp_usd * 100)
        self.sl_cents = int(sl_usd * 100)
        self.max_trades = max_trades
        self.min_ai_confidence = min_ai_confidence

        self.session: Optional[aiohttp.ClientSession] = None
        self.user_data: Dict[str, Any] = {}
        self.wallet: Dict[str, Any] = {}
        self.ws_token: Optional[str] = None
        self.active_symbol: str = "volatility_10"

        # Trading Metrics
        self.trades_count = 0
        self.wins_count = 0
        self.losses_count = 0
        self.consec_losses = 0
        self.total_pnl_cents = 0

    async def init_session(self):
        """Initializes non-blocking aiohttp ClientSession with standard headers."""
        if not self.session or self.session.closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/json"
            }
            self.session = aiohttp.ClientSession(headers=headers)

    async def close_session(self):
        """Clean shutdown of network sessions."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def authenticate_demo(self):
        """Creates a live demo session with $10,000 balance."""
        await self.init_session()
        print("\n[*] Initializing Demo Session via /api/v1/auth/demo ...")
        async with self.session.post(f"{BASE_URL}/api/v1/auth/demo", json={}) as res:
            if res.status != 200:
                text = await res.text()
                raise RuntimeError(f"Demo auth failed ({res.status}): {text}")
            data = await res.json()
            self.user_data = data["user"]
            self.wallet = data["wallets"][0]
            balance = self.wallet.get("balance_cents", 0) / 100.0
            print(f"[+] Demo Account Active: {self.user_data.get('display_name')} | LoginID: {self.wallet.get('loginid')} | Balance: ${balance:.2f}")

        await self._fetch_ws_token()

    async def authenticate_real(self, email: str, password: str):
        """Authenticates a real live money account via /api/v1/auth/login."""
        await self.init_session()
        print(f"\n[*] Authenticating LIVE REAL Account for {email} ...")
        payload = {"email": email, "password": password}
        async with self.session.post(f"{BASE_URL}/api/v1/auth/login", json=payload) as res:
            if res.status != 200:
                text = await res.text()
                raise RuntimeError(f"Real login failed ({res.status}): {text}")
            print("[+] Real Account Authenticated successfully!")

        # Fetch wallets and select 'real'
        async with self.session.get(f"{BASE_URL}/api/v1/auth/me") as res:
            data = await res.json()
            self.user_data = data.get("user", {})
            real_wallets = [w for w in data.get("wallets", []) if w.get("kind") == "real"]
            if not real_wallets:
                raise RuntimeError("No 'real' wallet found on this account.")
            self.wallet = real_wallets[0]
            balance = self.wallet.get("balance_cents", 0) / 100.0
            print(f"[+] Live Real Wallet Selected: {self.wallet.get('loginid')} | Balance: ${balance:.2f} {self.wallet.get('currency', 'USD')}")
            print("\n" + "="*65)
            print("  >>> CAUTION: REAL MONEY LIVE EXECUTION ACTIVE <<<")
            print("="*65 + "\n")

        await self._fetch_ws_token()

    async def _fetch_ws_token(self):
        """Fetches signed WebSocket streaming ticket."""
        async with self.session.get(f"{BASE_URL}/api/v1/auth/ws-token") as res:
            if res.status != 200:
                raise RuntimeError("Failed to fetch WebSocket token.")
            data = await res.json()
            self.ws_token = data["token"]

    async def fetch_live_scanner_signal(self) -> Optional[Dict[str, Any]]:
        """
        Taps the website's AI Scanner API directly (/api/v1/scanner/?family=...)
        Returns the top-rated market, pattern, AI confidence, and side.
        """
        url = f"{BASE_URL}/api/v1/scanner/?family={self.family}"
        try:
            async with self.session.get(url) as res:
                if res.status == 200:
                    data = await res.json()
                    best = data.get("best", {})
                    return best
        except Exception as e:
            print(f"[!] Scanner fetch error: {e}")
        return None

    async def place_contract_async(self, side: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Submits contract order sub-millisecond to /api/v1/contracts/"""
        payload = {
            "contract_type": side,
            "stake_cents": self.current_stake_cents,
            "wallet_kind": self.wallet["kind"],
            "symbol": symbol,
            "loginid": self.wallet["loginid"],
            "params": {}
        }

        stake_usd = self.current_stake_cents / 100.0
        print(f"\n[>>> DISPATCHING {self.wallet['kind'].upper()} ORDER] Symbol: {symbol} | Side: {side.upper()} | Stake: ${stake_usd:.2f}")

        start_time = time.perf_counter()
        async with self.session.post(f"{BASE_URL}/api/v1/contracts/", json=payload) as res:
            latency_ms = (time.perf_counter() - start_time) * 1000
            if res.status != 200:
                text = await res.text()
                print(f"[!] Contract dispatch failed ({res.status}): {text}")
                return None
            data = await res.json()
            print(f"[+] Order Placed in {latency_ms:.1f}ms! Contract ID: {data.get('contract', {}).get('id')}")
            return data

    async def await_3tick_settlement(self, contract_id: str, ws: websockets.WebSocketClientProtocol) -> Optional[Dict[str, Any]]:
        """
        Monitors 3 incoming ticks from the WebSocket, then polls for settlement.
        Contracts on MMG Trades settle strictly after 3 ticks (~3s).
        """
        print(f"[*] Tracking 3 market ticks for contract settlement...")
        for tick_idx in range(1, 4):
            raw_msg = await ws.recv()
            msg = json.loads(raw_msg)
            if msg.get("type") == "tick":
                t = msg["tick"]
                print(f"    Settlement Tick {tick_idx}/3: {t['symbol']} @ {t['price']:.2f} (Digit: {t['digit']})")

        # Poll closed contracts with retry until status is won/lost
        url = f"{BASE_URL}/api/v1/contracts/?status=closed&limit=20"
        for attempt in range(8):
            await asyncio.sleep(0.5)
            async with self.session.get(url) as res:
                if res.status == 200:
                    data = await res.json()
                    for c in data.get("contracts", []):
                        if c.get("id") == contract_id:
                            if c.get("status") in ["won", "lost"]:
                                return c
        return None

    async def run(self):
        """Main 100% AsyncIO Execution Loop."""
        await self.init_session()
        if self.mode == "demo":
            await self.authenticate_demo()

        print(f"\n[*] Starting Scanner Engine & Market Tapper...")
        initial_scan = await self.fetch_live_scanner_signal()
        if initial_scan:
            self.active_symbol = initial_scan.get("symbol", "volatility_10")
            print(f"[+] Initial Scanner Analysis:")
            print(f"    - Target Market : {self.active_symbol} ({initial_scan.get('label')})")
            print(f"    - Recommended   : {initial_scan.get('contract_type', '').upper()} ({initial_scan.get('trade_label')})")
            print(f"    - AI Score      : {initial_scan.get('ai_score', 0):.4f}")
            print(f"    - 3k Win Rate   : {initial_scan.get('win_rate', 0)*100:.1f}%")
            print(f"    - Recent Rate   : {initial_scan.get('recent_rate', 0)*100:.1f}%")
            print(f"    - Pattern       : {initial_scan.get('pattern')}")

        ws_url = f"{WS_HOST}?token={self.ws_token}&symbols={self.active_symbol}"
        print(f"\n[*] Connecting to High-Speed WebSocket Gateway: {ws_url} ...")

        async with websockets.connect(ws_url, ssl=True) as ws:
            print("[+] WebSocket Feed Connected! 100% AsyncIO Algorithmic Loop Running.\n")

            while self.trades_count < self.max_trades:
                # 1. Check Take-Profit & Stop-Loss Limits
                if self.total_pnl_cents >= self.tp_cents:
                    print(f"\n[$$$] TAKE-PROFIT REACHED: +${self.total_pnl_cents/100:.2f}. Strategy Halting.")
                    break
                if self.total_pnl_cents <= -self.sl_cents:
                    print(f"\n[!!!] STOP-LOSS HIT: -${abs(self.total_pnl_cents)/100:.2f}. Strategy Halting.")
                    break

                # 2. Check Titan Alpha Loss-Shield
                if self.consec_losses >= 3:
                    print(f"\n[SHIELD ACTIVATED] 3 Consecutive Losses! Cooling down for 3 ticks to protect balance...")
                    for _ in range(3):
                        await ws.recv()
                    self.current_stake_cents = self.initial_stake_cents
                    self.consec_losses = 0
                    print(f"[SHIELD] Stake restored to base: ${self.initial_stake_cents/100:.2f}")

                # 3. Read Real-time Tick
                raw_tick = await ws.recv()
                tick_data = json.loads(raw_tick)
                if tick_data.get("type") != "tick":
                    continue

                tick = tick_data["tick"]
                price = tick["price"]
                digit = tick["digit"]
                is_even = (digit % 2 == 0)

                # 4. Fetch Live Signal from Website Scanner API
                scan_signal = await self.fetch_live_scanner_signal()
                ai_score = scan_signal.get("ai_score", 0.0) if scan_signal else 0.0
                recommended_side = scan_signal.get("contract_type", "even") if scan_signal else ("even" if is_even else "odd")

                print(f"[STREAM] {tick['symbol']} | Price: {price:.2f} | Digit: {digit} ({'EVEN' if is_even else 'ODD'}) | Scanner AI Score: {ai_score:.3f}")

                # 5. Signal Decision Matrix (Combining Website AI Scanner + Tick Parity Flow)
                if self.consec_losses == 0:
                    # In win/clean state: Follow highest probability between AI scanner and tick parity
                    if ai_score >= self.min_ai_confidence:
                        chosen_side = recommended_side
                    else:
                        chosen_side = "even" if is_even else "odd"
                elif self.consec_losses < 3:
                    # In loss recovery: Double stake and flip parity (Titan Alpha Invert rule)
                    chosen_side = "odd" if is_even else "even"
                else:
                    chosen_side = "even" if is_even else "odd"

                # 6. Execute Order Sub-millisecond
                order_result = await self.place_contract_async(chosen_side, self.active_symbol)
                if not order_result or "contract" not in order_result:
                    await asyncio.sleep(1.0)
                    continue

                contract_id = order_result["contract"]["id"]
                self.trades_count += 1

                # 7. Asynchronously Track 3-Tick Settlement
                settlement = await self.await_3tick_settlement(contract_id, ws)
                if settlement:
                    won = (settlement.get("status") == "won")
                    payout_cents = settlement.get("payout_cents", 0)
                    profit_cents = payout_cents - self.current_stake_cents if won else -self.current_stake_cents
                    self.total_pnl_cents += profit_cents

                    if won:
                        self.wins_count += 1
                        self.consec_losses = 0
                        print(f"[RESULT: WON] +${payout_cents/100:.2f} | Net Profit: ${self.total_pnl_cents/100:.2f} | Win Rate: {self.wins_count/self.trades_count*100:.1f}%")
                        self.current_stake_cents = self.initial_stake_cents
                    else:
                        self.losses_count += 1
                        self.consec_losses += 1
                        print(f"[RESULT: LOST] -${self.current_stake_cents/100:.2f} | Consec Losses: {self.consec_losses} | Net Profit: ${self.total_pnl_cents/100:.2f}")
                        if self.consec_losses < 3:
                            self.current_stake_cents *= 2  # 2x Martingale

        await self.close_session()
        print(f"\n================ SUMMARY ================")
        print(f"Total Trades: {self.trades_count} | Wins: {self.wins_count} | Losses: {self.losses_count}")
        print(f"Final Net P/L: ${self.total_pnl_cents/100:.2f}")
        print(f"=========================================")

if __name__ == "__main__":
    # Test Run Configuration
    bot = MMGAsyncTrader(
        mode="demo",              # Switch to "real" and call authenticate_real(...) for live money
        family="even_odd",
        initial_stake_usd=1.0,
        tp_usd=10.0,
        sl_usd=20.0,
        max_trades=5,
        min_ai_confidence=0.50
    )

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nBot halted by user.")
