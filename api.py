from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from model import run_model
import requests
import traceback

app = FastAPI(
    title="DCF Engine",
    description="Discounted Cash Flow valuation — Ashish Ambashankar",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SEARCH_URLS = [
    "https://query1.finance.yahoo.com/v1/finance/search",
    "https://query2.finance.yahoo.com/v1/finance/search",
]

_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


@app.get("/", response_class=FileResponse)
def serve_frontend():
    """Serve the DCF frontend."""
    return FileResponse("dcf_engine.html")


@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/search")
def search_ticker(q: str = Query(..., min_length=1)):
    """
    Search Yahoo Finance for tickers by company name or symbol.
    Returns up to 10 matches.
    """
    q = q.strip()
    if not q:
        return {"results": []}

    params = {
        "q": q,
        "quotesCount": 10,
        "newsCount": 0,
        "enableFuzzyQuery": True,
        "region": "US",
        "lang": "en-US",
    }

    last_error = None
    for url in _SEARCH_URLS:
        try:
            res = requests.get(
                url, params=params, headers=_SEARCH_HEADERS, timeout=8
            )
            if res.status_code != 200:
                last_error = f"HTTP {res.status_code} from {url}"
                continue

            data = res.json()
            quotes_raw = data.get("quotes") or []
            quotes = []

            for item in quotes_raw:
                qt = item.get("quoteType", "")
                if qt not in ("EQUITY", "ETF", "MUTUALFUND", "INDEX"):
                    continue
                symbol = (item.get("symbol") or "").strip()
                if not symbol:
                    continue
                name = (
                    item.get("longname")
                    or item.get("shortname")
                    or symbol
                ).strip()
                quotes.append({
                    "symbol":   symbol,
                    "name":     name,
                    "exchange": (item.get("exchange") or "").strip(),
                    "type":     qt,
                })

            return {"results": quotes}

        except requests.exceptions.Timeout:
            last_error = f"Timeout on {url}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return {"results": [], "warning": f"Search unavailable: {last_error}"}


@app.get("/dcf")
def get_dcf(
    ticker:   str   = Query(...),
    growth:   float = Query(0.05,  ge=0.0,   le=0.5),
    wacc:     float = Query(0.10,  ge=0.005, le=0.5),
    terminal: float = Query(0.03,  ge=0.001, le=0.15),
):
    """
    Run a full DCF valuation for the given ticker.
    Returns projections, scenarios, sensitivity matrix, and waterfall.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker symbol is required.")

    if terminal >= wacc:
        terminal = wacc - 0.005

    try:
        result = run_model(
            ticker=ticker,
            growth=growth,
            wacc=wacc,
            terminal_growth=terminal,
        )
        return JSONResponse(content=result)
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Model error for {ticker}: {str(e)}\n{tb}",
        )
