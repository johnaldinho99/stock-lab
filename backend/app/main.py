"""FastAPI app: JSON API + static frontend."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import alpaca, config, service
from .data.store import DataMissing
from .strategies.registry import STRATEGIES

app = FastAPI(title="Aktielabbet", version="0.1")


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DataMissing as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/strategies")
async def list_strategies():
    return await asyncio.to_thread(_guard, service.strategy_list)


@app.get("/api/strategies/{strategy_id}")
async def strategy(strategy_id: str, request: Request, start: str | None = None):
    if strategy_id not in STRATEGIES:
        raise HTTPException(404, "Okänd strategi")
    params = {k: v for k, v in request.query_params.items() if k != "start"}
    return await asyncio.to_thread(_guard, service.strategy_detail, strategy_id, params, start)


@app.get("/api/compare")
async def compare(start: str | None = None):
    return await asyncio.to_thread(_guard, service.compare, start)


@app.get("/api/live")
async def live(symbols: str = Query("", description="Kommaseparerade tickers")):
    tickers = [s.strip().upper() for s in symbols.split(",") if s.strip()][:200]
    return await alpaca.snapshots(tickers)


@app.get("/api/status")
async def status():
    data = await asyncio.to_thread(_guard, service.data_status)
    return {"data": data, "alpaca": await alpaca.account()}


app.mount("/css", StaticFiles(directory=config.FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=config.FRONTEND_DIR / "js"), name="js")


@app.get("/")
async def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")
