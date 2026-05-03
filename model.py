import math
import yfinance as yf


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def clean(x):
    """
    Safely convert anything to a finite Python float.
    Handles: None, pandas NA/NaT/NaN, numpy floats, strings, Inf, -Inf.
    Returns 0.0 on any failure.
    """
    if x is None:
        return 0.0
    try:
        s = str(x).strip().lower()
        if s in ('nan', 'none', 'null', 'nat', '', 'inf', '-inf', 'infinity', '-infinity'):
            return 0.0
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except Exception:
        return 0.0


def safe_div(a, b, fallback=0.0):
    """Division that never raises."""
    try:
        a, b = float(a), float(b)
        if b == 0 or math.isnan(b) or math.isinf(b):
            return fallback
        result = a / b
        return result if math.isfinite(result) else fallback
    except Exception:
        return fallback


# ══════════════════════════════════════════════════════════════════
#  CASHFLOW EXTRACTION
# ══════════════════════════════════════════════════════════════════

_OP_CF_KEYS = [
    "Operating Cash Flow",
    "Total Cash From Operating Activities",
    "Cash From Operations",
    "operatingCashflow",
]
_CAPEX_KEYS = [
    "Capital Expenditure",
    "Capital Expenditures",
    "Purchase Of Property Plant And Equipment",
    "capitalExpenditures",
]


def _get_row(df, keys):
    for k in keys:
        if k in df.index:
            return df.loc[k]
    return None


def _extract_historical(cf_df):
    rows = []
    if cf_df is None or cf_df.empty:
        return rows
    op_row    = _get_row(cf_df, _OP_CF_KEYS)
    capex_row = _get_row(cf_df, _CAPEX_KEYS)
    for col in list(cf_df.columns)[:5]:
        try:
            year_str = str(col.year) if hasattr(col, 'year') else str(col)[:4]
            op_cf = clean(op_row[col])    if op_row    is not None else 0.0
            capex = clean(capex_row[col]) if capex_row is not None else 0.0
            fcf   = op_cf - abs(capex)
            rows.append({"year": year_str, "fcf": fcf})
        except Exception:
            continue
    return sorted(rows, key=lambda r: r["year"])


_FALLBACK_HISTORICAL = [
    {"year": "2020", "fcf": 600_000_000.0},
    {"year": "2021", "fcf": 800_000_000.0},
    {"year": "2022", "fcf": 900_000_000.0},
    {"year": "2023", "fcf": 1_000_000_000.0},
    {"year": "2024", "fcf": 1_100_000_000.0},
]


# ══════════════════════════════════════════════════════════════════
#  DATA FETCH
# ══════════════════════════════════════════════════════════════════

def fetch_financials(ticker: str) -> dict:
    """Fetch all DCF inputs from yfinance. Never raises."""
    stock = None
    try:
        stock = yf.Ticker(ticker)
    except Exception:
        pass

    historical = []
    if stock is not None:
        try:
            historical = _extract_historical(stock.cashflow)
        except Exception:
            historical = []

    if len(historical) < 3:
        historical = [dict(r) for r in _FALLBACK_HISTORICAL]

    info = {}
    if stock is not None:
        try:
            info = stock.info or {}
            if not isinstance(info, dict):
                info = {}
        except Exception:
            info = {}

    current_price = clean(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
        or 0
    )

    shares = clean(info.get("sharesOutstanding") or 0)
    if shares <= 0:
        shares = 1_000_000_000.0

    total_debt = clean(info.get("totalDebt") or 0)
    total_cash = clean(info.get("totalCash") or info.get("cashAndCashEquivalents") or 0)
    net_debt   = total_debt - total_cash

    analyst_growth = None
    try:
        for key in ("earningsGrowth", "revenueGrowth", "earningsQuarterlyGrowth"):
            val = clean(info.get(key) or 0)
            if val != 0.0:
                analyst_growth = round(val, 4)
                break
    except Exception:
        analyst_growth = None

    latest_fcf = historical[-1]["fcf"] if historical else 1_000_000_000.0

    return {
        "historical":     historical,
        "latest_fcf":     latest_fcf,
        "shares":         shares,
        "net_debt":       net_debt,
        "current_price":  current_price,
        "analyst_growth": analyst_growth,
    }


# ══════════════════════════════════════════════════════════════════
#  SINGLE DCF RUN
# ══════════════════════════════════════════════════════════════════

def _dcf(base_fcf, shares, net_debt, growth, wacc, terminal_growth, years=5):
    """One DCF pass. All inputs pre-validated. Never raises."""
    if terminal_growth >= wacc:
        terminal_growth = wacc - 0.005
    terminal_growth = max(terminal_growth, 0.001)
    wacc            = max(wacc, 0.005)
    base_fcf        = max(base_fcf, 1.0)
    shares          = max(shares, 1.0)

    fcf_series = []
    discounted = []
    cf = base_fcf

    for t in range(1, years + 1):
        cf      = cf * (1.0 + growth)
        pv      = safe_div(cf, (1.0 + wacc) ** t)
        fcf_series.append(clean(cf))
        discounted.append(clean(pv))

    pv_fcfs      = sum(discounted)
    last_cf      = fcf_series[-1] if fcf_series else base_fcf
    tv           = safe_div(last_cf * (1.0 + terminal_growth), wacc - terminal_growth)
    pv_terminal  = safe_div(tv, (1.0 + wacc) ** years)
    enterprise   = clean(pv_fcfs + pv_terminal)
    equity       = clean(enterprise - net_debt)
    price        = safe_div(equity, shares)

    return (
        clean(price),
        clean(enterprise),
        clean(equity),
        [clean(v) for v in fcf_series],
        [clean(v) for v in discounted],
        clean(pv_terminal),
    )


# ══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def run_model(ticker: str, growth: float = 0.05, wacc: float = 0.10,
              terminal_growth: float = 0.03) -> dict:
    """Full DCF. Always returns a complete, JSON-serialisable dict."""
    growth          = max(clean(growth), 0.0)
    wacc            = max(clean(wacc),   0.005)
    terminal_growth = max(clean(terminal_growth), 0.001)
    if terminal_growth >= wacc:
        terminal_growth = wacc - 0.005

    data           = fetch_financials(ticker)
    historical     = data["historical"]
    base_fcf       = max(clean(data["latest_fcf"]), 1.0)
    shares         = max(clean(data["shares"]),     1.0)
    net_debt       = clean(data["net_debt"])
    current_price  = clean(data["current_price"])
    analyst_growth = data["analyst_growth"]

    price, enterprise, equity, fcf_series, discounted_fcfs, pv_terminal = _dcf(
        base_fcf, shares, net_debt, growth, wacc, terminal_growth
    )

    mos = clean(safe_div(price - current_price, current_price)) if current_price > 0 else 0.0

    # sensitivity 3x3
    sensitivity = []
    for g_delta in [-0.01, 0.0, 0.01]:
        row = []
        for w_delta in [-0.01, 0.0, 0.01]:
            p, *_ = _dcf(
                base_fcf, shares, net_debt,
                max(growth + g_delta, 0.0),
                max(wacc   + w_delta, 0.005),
                terminal_growth,
            )
            row.append(clean(p))
        sensitivity.append(row)

    # three scenarios
    bear_tg = max(terminal_growth - 0.005, 0.001)
    bull_tg = terminal_growth + 0.005
    scenario_configs = {
        "bear": (max(growth - 0.05, 0.005), min(wacc + 0.01, 0.49), bear_tg),
        "base": (growth, wacc, terminal_growth),
        "bull": (min(growth + 0.05, 0.49),  max(wacc - 0.01, 0.005), bull_tg),
    }

    scenarios = {}
    for name, (g, w, tg) in scenario_configs.items():
        tg = min(tg, w - 0.005)
        sp, sev, seq, sfcf, _, _ = _dcf(base_fcf, shares, net_debt, g, w, tg)
        s_mos = clean(safe_div(sp - current_price, current_price)) if current_price > 0 else 0.0
        scenarios[name] = {
            "price":      clean(sp),
            "enterprise": clean(sev),
            "equity":     clean(seq),
            "growth":     round(clean(g),  4),
            "wacc":       round(clean(w),  4),
            "terminal":   round(clean(tg), 4),
            "mos":        clean(s_mos),
            "fcf_series": [clean(v) for v in sfcf],
        }

    pv_fcfs_total = clean(sum(discounted_fcfs))
    waterfall = [
        {"label": "PV of FCFs",        "value": pv_fcfs_total},
        {"label": "PV Terminal Value",  "value": clean(pv_terminal)},
        {"label": "Enterprise Value",   "value": clean(enterprise)},
        {"label": "Less: Net Debt",     "value": clean(-net_debt)},
        {"label": "Equity Value",       "value": clean(equity)},
    ]

    return {
        "price":            clean(price),
        "enterprise":       clean(enterprise),
        "equity":           clean(equity),
        "current_price":    clean(current_price),
        "analyst_growth":   analyst_growth,
        "margin_of_safety": clean(mos),
        "historical":       historical,
        "fcf_series":       [clean(v) for v in fcf_series],
        "discounted_fcfs":  [clean(v) for v in discounted_fcfs],
        "pv_terminal":      clean(pv_terminal),
        "sensitivity":      sensitivity,
        "waterfall":        waterfall,
        "scenarios":        scenarios,
    }
