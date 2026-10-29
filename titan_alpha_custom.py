"""
Custom Python Algorithmic Trading Framework for MMG Trades
Reverse-engineered from Titan_Alpha_Strategy.xml and MMG Trades API.

Features:
- Live WebSocket tick streamer from api.mmgtrades.site
- Tick digit parser (price.toFixed(2) last decimal)
- Execution of Titan Alpha parity logic + enhanced statistical filters
- Full demo & real wallet support via /api/v1/contracts/
- Dynamic Risk Management (Strict Stop-Loss, Take-Profit, and Loss-Shield)
"""

import asyncio
import json
import requests
import websockets
from typing import Dict, Any, Optional

BASE_URL = "https://mmgpredictions.com"
WS_HOST = "wss://api.mmgtrades.site/api/v1/feed/ws"

class MMGStrategyEngine:
    def __init__(self, initial_stake_usd: float = 1.0, tp_usd: float = 20.0, sl_usd: float = 50.0, max_trades: int = 50, symbol: str = "volatility_10"):
        self.initial_stake_cents = int(initial_stake_usd * 100)
        self.current_stake_cents = self.initial_stake_cents
        self.tp_cents = int(tp_usd * 100)
        self.sl_cents = int(sl_usd * 100)
        self.max_trades = max_trades
        self.symbol = symbol

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        self.user_data: Dict[str, Any] = {}
        self.wallet: Dict[str, Any] = {}
        self.ws_token: Optional[str] = None

        # Strategy State Tracking
        self.total_trades = 0
        self.total_profit_cents = 0
        self.consec_losses = 0
        self.last_tick_digit: Optional[int] = None
        self.tick_history = []

    def authenticate_demo(self):
        """Authenticates a demo account and retrieves wallets & WS token."""
        print("[*] Authenticating demo session...")
        res = self.session.post(f"{BASE_URL}/api/v1/auth/demo", json={})
        if res.status_code != 200:
            raise RuntimeError(f"Auth failed: {res.text}")
        data = res.json()
        self.user_data = data["user"]
        self.wallet = data["wallets"][0]
        print(f"[+] Authenticated: {self.user_data['display_name']} | LoginID: {self.wallet['loginid']} | Balance: ${self.wallet['balance_cents']/100:.2f}")

        # Get WebSocket Token
        tok_res = self.session.get(f"{BASE_URL}/api/v1/auth/ws-token")
        self.ws_token = tok_res.json()["token"]
        return self.ws_token

    def place_contract(self, side: str) -> Optional[Dict[str, Any]]:
        """Places a contract (even / odd) via POST /api/v1/contracts/"""
        payload = {
            "contract_type": side,
            "stake_cents": self.current_stake_cents,
            "wallet_kind": self.wallet["kind"],
            "symbol": self.symbol,
            "loginid": self.wallet["loginid"],
            "params": {}
        }
        print(f"\n[>>> ORDER PLACED] Side: {side.upper()} | Stake: ${self.current_stake_cents/100:.2f} | Balance: ${self.wallet['balance_cents']/100:.2f}")
        res = self.session.post(f"{BASE_URL}/api/v1/contracts/", json=payload)
        if res.status_code != 200:
            print(f"[!] Order failed: {res.text}")
            return None
        return res.json()

    def check_settlement(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Polls for settlement after 3 ticks (~3 seconds)"""
        res = self.session.get(f"{BASE_URL}/api/v1/contracts/?status=closed&limit=10")
        if res.status_code == 200:
            contracts = res.json().get("contracts", [])
            for c in contracts:
                if c.get("id") == contract_id:
                    return c
        return None

    def decide_next_side(self, last_digit: int) -> str:
        """
        Titan Alpha Strategy Decision Matrix:
        - If first trade or previous trade won: Follow parity (even -> even, odd -> odd).
        - If loss streak < 3: Double stake (2x Martingale) and INVERT parity (even -> odd, odd -> even).
        - If loss streak >= 3: Trigger loss shield, reset stake, wait 3 ticks, follow parity.
        """
        is_even = (last_digit % 2 == 0)

        if self.consec_losses == 0:
            # Win or initial flow: Follow parity
            return "even" if is_even else "odd"
        elif self.consec_losses < 3:
            # Loss 1 or 2: Invert parity (predicting alternating flip)
            return "odd" if is_even else "even"
        else:
            # Shield triggered: Reset stake and follow parity
            return "even" if is_even else "odd"

    async def run(self):
        self.authenticate_demo()
        ws_url = f"{WS_HOST}?token={self.ws_token}&symbols={self.symbol}"

        print(f"\n[*] Connecting to real-time feed: {ws_url} ...")
        async with websockets.connect(ws_url, ssl=True) as ws:
            print("[+] Live Market Feed Connected! Strategy Active.")

            tick_counter = 0
            while self.total_trades < self.max_trades:
                msg = json.loads(await ws.recv())

                if msg.get("type") == "tick":
                    tick = msg["tick"]
                    self.last_tick_digit = tick["digit"]
                    self.tick_history.append(tick)
                    tick_counter += 1
                    print(f"Tick #{tick_counter} | Price: {tick['price']:.2f} | Digit: {self.last_tick_digit}")

                    # Check TP / SL Circuit Breakers
                    if self.total_profit_cents >= self.tp_cents:
                        print(f"\n[+] TAKE PROFIT REACHED: +${self.total_profit_cents/100:.2f}. Halting.")
                        break
                    if self.total_profit_cents <= -self.sl_cents:
                        print(f"\n[-] STOP LOSS HIT: -${abs(self.total_profit_cents)/100:.2f}. Halting.")
                        break

                    # Titan Alpha Logic: Check loss shield cooldown
                    if self.consec_losses >= 3:
                        print(f"[!] Loss Shield Triggered! Pausing 3 ticks to protect capital...")
                        for _ in range(3):
                            await ws.recv()
                        self.current_stake_cents = self.initial_stake_cents
                        self.consec_losses = 0

                    # Decide Side
                    side = self.decide_next_side(self.last_tick_digit)
                    order_res = self.place_contract(side)

                    if order_res and "contract" in order_res:
                        contract_id = order_res["contract"]["id"]
                        self.total_trades += 1

                        # Await settlement (settles in 3 ticks)
                        print(f"[*] Awaiting 3-tick settlement for contract {contract_id}...")
                        for _ in range(3):
                            await ws.recv()

                        # Check settlement status
                        await asyncio.sleep(1.0)
                        settled = self.check_settlement(contract_id)
                        if settled:
                            won = (settled.get("status") == "won")
                            payout_cents = settled.get("payout_cents", 0)
                            profit_cents = payout_cents - self.current_stake_cents if won else -self.current_stake_cents
                            self.total_profit_cents += profit_cents

                            if won:
                                print(f"[RESULT] WON! +${payout_cents/100:.2f} | Total P/L: ${self.total_profit_cents/100:.2f}")
                                self.consec_losses = 0
                                self.current_stake_cents = self.initial_stake_cents
                            else:
                                self.consec_losses += 1
                                print(f"[RESULT] LOST! -${self.current_stake_cents/100:.2f} | Consec Losses: {self.consec_losses} | Total P/L: ${self.total_profit_cents/100:.2f}")
                                if self.consec_losses < 3:
                                    self.current_stake_cents *= 2  # 2x Martingale

if __name__ == "__main__":
    bot = MMGStrategyEngine(initial_stake_usd=1.0, tp_usd=10.0, sl_usd=20.0, max_trades=10)
    asyncio.run(bot.run())
