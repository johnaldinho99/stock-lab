"""Minimal Alpaca client: live snapshots (market data) and paper-account status.

Keys are read from .env and only ever used server-side. Without keys the
endpoints report `enabled: false` and the UI falls back to the latest close.
"""

from __future__ import annotations

import time

import httpx

from . import config

_snap_cache: dict[str, tuple[float, dict]] = {}
SNAP_TTL = 10  # seconds


def _headers() -> dict:
    return {"APCA-API-KEY-ID": config.ALPACA_KEY_ID, "APCA-API-SECRET-KEY": config.ALPACA_SECRET}


def to_alpaca(ticker: str) -> str:
    return ticker.replace("-", ".")  # BRK-B -> BRK.B


def from_alpaca(symbol: str) -> str:
    return symbol.replace(".", "-")


async def snapshots(tickers: list[str]) -> dict:
    if not config.alpaca_enabled():
        return {"enabled": False, "quotes": {}}
    now = time.time()
    fresh = {t: v for t, (ts, v) in _snap_cache.items() if t in tickers and now - ts < SNAP_TTL}
    missing = [t for t in tickers if t not in fresh and t != "CASH"]
    error = None
    if missing:
        try:
            async with httpx.AsyncClient(timeout=10, headers=_headers()) as client:
                for i in range(0, len(missing), 100):
                    batch = missing[i : i + 100]
                    r = await client.get(
                        f"{config.ALPACA_DATA_URL}/v2/stocks/snapshots",
                        params={"symbols": ",".join(to_alpaca(t) for t in batch), "feed": config.ALPACA_FEED},
                    )
                    r.raise_for_status()
                    for sym, snap in r.json().items():
                        q = _parse(snap)
                        if q:
                            t = from_alpaca(sym)
                            _snap_cache[t] = (now, q)
                            fresh[t] = q
        except httpx.HTTPStatusError as exc:
            error = f"Alpaca svarade {exc.response.status_code}: {exc.response.text[:200]}"
        except httpx.HTTPError as exc:
            error = f"Kunde inte nå Alpaca: {exc}"
    return {"enabled": True, "feed": config.ALPACA_FEED, "quotes": fresh, "error": error}


def _parse(snap: dict) -> dict | None:
    if not snap:
        return None
    trade = snap.get("latestTrade") or {}
    daily = snap.get("dailyBar") or {}
    prev = snap.get("prevDailyBar") or {}
    price = trade.get("p") or daily.get("c")
    if price is None:
        return None
    ref = prev.get("c")
    return {
        "price": float(price),
        "time": trade.get("t") or daily.get("t"),
        "prev_close": ref,
        "change": (float(price) / float(ref) - 1) if ref else None,
    }


async def account() -> dict:
    if not config.alpaca_enabled():
        return {"enabled": False}
    try:
        async with httpx.AsyncClient(timeout=10, headers=_headers()) as client:
            r = await client.get(f"{config.ALPACA_PAPER_URL}/v2/account")
            r.raise_for_status()
            a = r.json()
            c = await client.get(f"{config.ALPACA_PAPER_URL}/v2/clock")
            clock = c.json() if c.status_code == 200 else {}
        return {
            "enabled": True,
            "ok": True,
            "status": a.get("status"),
            "equity": float(a.get("equity", 0)),
            "cash": float(a.get("cash", 0)),
            "buying_power": float(a.get("buying_power", 0)),
            "market_open": clock.get("is_open"),
            "next_open": clock.get("next_open"),
            "feed": config.ALPACA_FEED,
        }
    except httpx.HTTPStatusError as exc:
        return {"enabled": True, "ok": False, "error": f"Alpaca svarade {exc.response.status_code} – kontrollera nycklarna i .env"}
    except httpx.HTTPError as exc:
        return {"enabled": True, "ok": False, "error": f"Kunde inte nå Alpaca: {exc}"}
