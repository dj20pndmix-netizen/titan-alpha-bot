"""
MMG Trades - Production Real-Time & Live Trading Engine
Reverse-engineered for Real Money Trading on MMG Trades (https://mmgpredictions.com).

REAL TRADING ARCHITECTURE:
- Auth Gateway: POST /api/v1/auth/login (email/password) or session cookie `ap_session`
- Account Profiles: GET /api/v1/auth/me (extracts real wallet loginid 'CR...')
- Feed Token: GET /api/v1/auth/ws-token
- Live WebSocket Feed: wss://api.mmgtrades.site/api/v1/feed/ws?token=...&symbols=...
- Real Contract Placement: POST /api/v1/contracts/ with `wallet_kind: "real"`
- 3-Tick Settlement: GET /api/v1/contracts/?status=closed
"""

import asyncio
import json
import requests
import websockets
import sys
from typing import Dict, Any, Optional

BASE_URL = "https://mmgpredictions.com"
WS_HOST = "wss://api.mmgtrades.site/api/v1/feed/ws"

class MMGProductionEngine:
    def __init__(
        self,
        mode: str = "real",  # "real" for live money, "demo" for practice
        symbol: str = "volatility_10",
        initial_stake_usd: float = 1.0,
        tp_usd: float = 20.0,
        sl_usd: float = 50.0,
        max_trades: int = 50
    ):
        self.mode = mode.lower()
        if self.mode not in ["real", "demo"]:
            raise ValueError("Mode must be either 'real' or 'demo'")

        self.symbol = symbol
        self.initial_stake_cents = int(initial_stake_usd * 100)
        self.current_stake_cents = self.initial_stake_cents
        self.tp_cents = int(tp_usd * 100)
        self.sl_cents = int(sl_usd * 100)
        self.max_trades = max_trades

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        })

        self.user_data: Dict[str, Any] = {}
        self.wallet: Dict[str, Any] = {}
        self.ws_token: Optional[str] = None

        # Strategy State Tracking
        self.total_trades = 0
        self.total_profit_cents = 0
        self.consec_losses = 0
        self.last_tick_digit: Optional[int] = None

    def login_with_credentials(self, email: str, password: str):
        """Authenticates a real live user account via POST /api/v1/auth/login."""
        print(f"\n[*] Authenticating LIVE REAL account for: {email} ...")
        res = self.session.post(f"{BASE_URL}/api/v1/auth/login", json={"email": email, "password": password})
        if res.status_code != 200:
            raise RuntimeError(f"Login failed ({res.status_code}): {res.text}")
        print("[+] Logged in successfully!")
        self._load_account_profile()

    def login_with_session_cookie(self, ap_session_cookie: str):
        """Authenticates using an existing browser session cookie (ap_session)."""
        print("\n[*] Authenticating via existing 'ap_session' cookie...")
        self.session.cookies.set("ap_session", ap_session_cookie, domain="mmgpredictions.com")
        self._load_account_profile()

    def _load_account_profile(self):
        """Loads account info and selects the target wallet ('real' or 'demo')."""
        res = self.session.get(f"{BASE_URL}/api/v1/auth/me")
        if res.status_code != 200:
            raise RuntimeError(f"Failed to fetch profile: {res.text}")
        data = res.json()
        self.user_data = data.get("user", {})
        wallets = data.get("wallets", [])

        # Filter wallet by mode ('real' or 'demo')
        selected = [w for w in wallets if w.get("kind") == self.mode]
        if not selected:
            available = [w.get("kind") for w in wallets]
            raise RuntimeError(f"Requested '{self.mode}' wallet, but found only: {available}")

        self.wallet = selected[0]
        balance_usd = self.wallet.get("balance_cents", 0) / 100.0
        print(f"[+] Active Account: {self.user_data.get('display_name')} ({self.user_data.get('email', 'No Email')})")
        print(f"[+] Active Wallet : [{self.wallet.get('kind').upper()}] {self.wallet.get('loginid')} | Balance: ${balance_usd:.2f} {self.wallet.get('currency', 'USD')}")

        if self.mode == "real":
            print("\n" + "=" * 60)
            print("  >>> CAUTION: REAL MONEY LIVE TRADING MODE IS ACTIVE <<<")
            print("=" * 60 + "\n")

        # Fetch WebSocket feed ticket
        tok_res = self.session.get(f"{BASE_URL}/api/v1/auth/ws-token")
        if tok_res.status_code != 200:
            raise RuntimeError("Failed to obtain feed token.")
        self.ws_token = tok_res.json()["token"]

    def place_real_contract(self, side: str) -> Optional[Dict[str, Any]]:
        """
        Executes a real trade on the MMG contracts engine.
        POST /api/v1/contracts/
        """
        payload = {
            "contract_type": side,                       # "even" | "odd" | "over" | "under" | "match" | "diff"
            "stake_cents": self.current_stake_cents,     # Stake in cents ($1.00 = 100)
            "wallet_kind": self.wallet["kind"],          # "real"
            "symbol": self.symbol,                       # e.g. "volatility_10"
            "loginid": self.wallet["loginid"],           # Real wallet login ID (e.g. CR...)
            "params": {}
        }

        print(f"\n[>>> REAL ORDER] Side: {side.upper()} | Stake: ${self.current_stake_cents/100:.2f} | Wallet: {self.wallet['kind']}")
        res = self.session.post(f"{BASE_URL}/api/v1/contracts/", json=payload)
        if res.status_code != 200:
            print(f"[!] Order failed ({res.status_code}): {res.text}")
            return None
        return res.json()

    def check_settlement(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Queries closed contracts to get the exact profit/loss outcome."""
        wallet_id = self.wallet.get("id", "")
        url = f"{BASE_URL}/api/v1/contracts/?status=closed&limit=10&wallet_id={wallet_id}"
        res = self.session.get(url)
        if res.status_code == 200:
            for c in res.json().get("contracts", []):
                if c.get("id") == contract_id:
                    return c
        return None

    def decide_next_side(self, last_digit: int) -> str:
        """
        Titan Alpha Strategy Decision Matrix:
        - If first trade or previous win: Follow parity (even -> even, odd -> odd).
        - If loss streak < 3: Double stake (2x Martingale) and INVERT parity (even -> odd).
        - If loss streak >= 3: Cooldown shield, reset stake to $1.00, follow parity.
        """
        is_even = (last_digit % 2 == 0)

        if self.consec_losses == 0:
            return "even" if is_even else "odd"
        elif self.consec_losses < 3:
            return "odd" if is_even else "even"
        else:
            return "even" if is_even else "odd"

    async def run(self):
        ws_url = f"{WS_HOST}?token={self.ws_token}&symbols={self.symbol}"
        print(f"[*] Connecting to live market feed: {ws_url} ...")

        async with websockets.connect(ws_url, ssl=True) as ws:
            print("[+] WebSocket Feed Connected! Real-time Strategy Running.\n")

            while self.total_trades < self.max_trades:
                msg = json.loads(await ws.recv())

                if msg.get("type") == "tick":
                    tick = msg["tick"]
                    self.last_tick_digit = tick["digit"]
                    print(f"[TICK] {self.symbol} | Price: {tick['price']:.2f} | Last Digit: {self.last_tick_digit}")

                    # Check TP / SL Limits
                    if self.total_profit_cents >= self.tp_cents:
                        print(f"\n[+] TARGET REACHED: Profit +${self.total_profit_cents/100:.2f}. Halting.")
                        break
                    if self.total_profit_cents <= -self.sl_cents:
                        print(f"\n[-] STOP LOSS HIT: Loss -${abs(self.total_profit_cents)/100:.2f}. Halting.")
                        break

                    # Loss Shield Check
                    if self.consec_losses >= 3:
                        print(f"[!] 3 Consecutive Losses! Triggering Shield: Pausing 3 ticks...")
                        for _ in range(3):
                            await ws.recv()
                        self.current_stake_cents = self.initial_stake_cents
                        self.consec_losses = 0

                    # Decide Side & Place Real Order
                    side = self.decide_next_side(self.last_tick_digit)
                    order_res = self.place_real_contract(side)

                    if order_res and "contract" in order_res:
                        contract_id = order_res["contract"]["id"]
                        self.total_trades += 1

                        # Contracts settle 3 ticks after entry (~3 seconds)
                        print(f"[*] Awaiting 3-tick settlement for contract: {contract_id} ...")
                        for _ in range(3):
                            await ws.recv()

                        await asyncio.sleep(1.0)
                        settled = self.check_settlement(contract_id)
                        if settled:
                            won = (settled.get("status") == "won")
                            payout_cents = settled.get("payout_cents", 0)
                            pnl_cents = payout_cents - self.current_stake_cents if won else -self.current_stake_cents
                            self.total_profit_cents += pnl_cents

                            if won:
                                print(f"[RESULT] WON! +${payout_cents/100:.2f} | Net P/L: ${self.total_profit_cents/100:.2f}")
                                self.consec_losses = 0
                                self.current_stake_cents = self.initial_stake_cents
                            else:
                                self.consec_losses += 1
                                print(f"[RESULT] LOST! -${self.current_stake_cents/100:.2f} | Consec Losses: {self.consec_losses} | Net P/L: ${self.total_profit_cents/100:.2f}")
                                if self.consec_losses < 3:
                                    self.current_stake_cents *= 2

if __name__ == "__main__":
    print("=" * 60)
    print("  MMG TRADES - REAL / LIVE TRADING ENGINE")
    print("=" * 60)

    # To run on your REAL LIVE account:
    # 1. engine = MMGProductionEngine(mode="real", initial_stake_usd=1.0, tp_usd=10.0, sl_usd=20.0)
    # 2. engine.login_with_credentials(email="your_email@example.com", password="your_password")
    #    OR engine.login_with_session_cookie("your_ap_session_cookie_from_browser")
    # 3. asyncio.run(engine.run())
    
    print("\nEngine configured and ready for live execution.")
    print("See code in c:\\my strategy\\titan_alpha_real.py for credential configuration.")
