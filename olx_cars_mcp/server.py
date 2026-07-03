"""Cars-for-sale MCP server — ask natural-language questions about OLX Lebanon
car data and get answers, backed by a cleaned Postgres (Supabase) database.

Read-only. Configure the connection with CARS_DATABASE_URL (a SELECT-only role).
Set ALLOW_SQL=1 to also expose the open-ended `query_sql` tool (off by default
on public deployments).

Run:  olx-cars-mcp            # stdio (Claude Desktop/Code)
      olx-cars-mcp --http     # streamable HTTP endpoint
"""
from __future__ import annotations

import os
import re
import threading
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# public HTTPS endpoint (behind Cloud Run etc.) — the browser-focused DNS-rebinding
# guard would otherwise reject the proxy Host header with HTTP 421.
mcp = FastMCP("olx-cars",
              transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

_POSTED = "to_timestamp((l.data->>'createdAt')::bigint)"


class CarsDB:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None
        self._lock = threading.Lock()

    def _c(self):
        import psycopg
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.dsn, prepare_threshold=None, autocommit=True)
        return self._conn

    def q(self, sql: str, params: tuple = ()) -> list[dict]:
        import psycopg
        with self._lock:
            try:
                cur = self._c().cursor(); cur.execute(sql, params)
            except psycopg.OperationalError:
                self._conn = None
                cur = self._c().cursor(); cur.execute(sql, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, r)) for r in cur.fetchall()]


_db: CarsDB | None = None


def _get_db() -> CarsDB:
    global _db
    if _db is None:
        dsn = os.environ.get("CARS_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("set CARS_DATABASE_URL (read-only) to the Postgres DSN")
        if "sslmode=" not in dsn:
            dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
        _db = CarsDB(dsn)
    return _db


def _ext_id(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"ID(\d+)", s) or re.search(r"(\d{6,})", s)
    return m.group(1) if m else s


# ----------------------------- tools -----------------------------

@mcp.tool()
def search_cars(
    make: Optional[str] = None,
    model: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    max_mileage_km: Optional[int] = None,
    region: Optional[str] = None,
    seller_type: Optional[str] = None,
    sort: str = "price_asc",
    limit: int = 25,
) -> list[dict]:
    """Search active cars-for-sale with filters. Returns matching cars with
    price, year, mileage, region, seller and listing url.

    sort: price_asc | price_desc | year_desc | mileage_asc | newest.
    make/model/region match case-insensitively. seller_type is 'Agency' or 'Individual'.
    """
    w = ["status='active'", "price_usd IS NOT NULL"]
    p: list[Any] = []
    if make: w.append("make ILIKE %s"); p.append(f"%{make}%")
    if model: w.append("model ILIKE %s"); p.append(f"%{model}%")
    if year_min: w.append("year >= %s"); p.append(year_min)
    if year_max: w.append("year <= %s"); p.append(year_max)
    if price_min: w.append("price_usd >= %s"); p.append(price_min)
    if price_max: w.append("price_usd <= %s"); p.append(price_max)
    if max_mileage_km: w.append("mileage_km <= %s"); p.append(max_mileage_km)
    if region: w.append("region ILIKE %s"); p.append(f"%{region}%")
    if seller_type: w.append("seller_type ILIKE %s"); p.append(seller_type)
    order = {"price_asc": "price_usd ASC", "price_desc": "price_usd DESC",
             "year_desc": "year DESC NULLS LAST", "mileage_asc": "mileage_km ASC NULLS LAST",
             "newest": "days_listed ASC"}.get(sort, "price_usd ASC")
    p.append(min(limit, 100))
    return _get_db().q(
        f"SELECT make, model, year, price_usd, mileage_km, region, seller_type, "
        f"condition, days_listed, url FROM v_vehicle WHERE {' AND '.join(w)} "
        f"ORDER BY {order} LIMIT %s", tuple(p))


@mcp.tool()
def find_deals(
    make: Optional[str] = None,
    model: Optional[str] = None,
    region: Optional[str] = None,
    min_discount_pct: int = 20,
    min_comps: int = 5,
    exclude_unknown_mileage: bool = False,
    posted_within_days: Optional[int] = None,
    limit: int = 25,
) -> list[dict]:
    """Find underpriced cars from the deal detector: priced below the median of
    comparable listings (same make+model+year, >= min_comps) and not merely
    cheaper due to higher mileage. Shows price vs market_price, discount_pct,
    comps, mileage vs the group average, posted date and url. Use
    posted_within_days for recently-listed deals only.
    """
    w = ["discount_pct >= %s", "comps >= %s"]
    p: list[Any] = [min_discount_pct, min_comps]
    if make: w.append("d.make ILIKE %s"); p.append(f"%{make}%")
    if model: w.append("d.model ILIKE %s"); p.append(f"%{model}%")
    if region: w.append("d.region ILIKE %s"); p.append(f"%{region}%")
    if exclude_unknown_mileage: w.append("d.mileage_vs_market <> 'unknown'")
    if posted_within_days:
        w.append(f"{_POSTED} >= now() - (%s || ' days')::interval"); p.append(posted_within_days)
    p.append(min(limit, 100))
    return _get_db().q(
        f"SELECT d.make, d.model, d.year, d.price_usd, d.market_price, d.discount_pct, "
        f"d.comps, d.mileage_km, d.market_km, d.mileage_vs_market, d.region, "
        f"{_POSTED}::date AS posted, d.url "
        f"FROM v_car_deal d JOIN listings l ON l.external_id=d.external_id "
        f"WHERE {' AND '.join(w)} ORDER BY d.discount_pct DESC LIMIT %s", tuple(p))


@mcp.tool()
def market_price(make: str, model: str, year: int) -> dict:
    """Benchmark price for a make+model+year: median/p25/p75 price, median
    mileage, and how many comparable listings back it."""
    rows = _get_db().q(
        "SELECT count(*) AS listings, "
        "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY price_usd)) AS median_price, "
        "round(percentile_cont(0.25) WITHIN GROUP (ORDER BY price_usd)) AS p25, "
        "round(percentile_cont(0.75) WITHIN GROUP (ORDER BY price_usd)) AS p75, "
        "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY mileage_km)) AS median_km "
        "FROM v_vehicle WHERE make ILIKE %s AND model ILIKE %s AND year=%s "
        "AND price_usd IS NOT NULL", (make, model, year))
    r = rows[0] if rows else {}
    r.update({"make": make, "model": model, "year": year})
    return r


@mcp.tool()
def rank_car(id_or_url: str) -> dict:
    """Given a listing id or OLX url, show where its price sits versus comparable
    cars (same make+model+year): market median, % above/below, deal or not."""
    ext = _ext_id(id_or_url)
    db = _get_db()
    car = db.q("SELECT make, model, year, price_usd, mileage_km, url, region, condition "
               "FROM v_vehicle WHERE external_id=%s", (ext,))
    if not car:
        return {"error": f"car {ext} not found"}
    car = car[0]
    mk = market_price(car["make"], car["model"], car["year"])
    med = mk.get("median_price")
    out = {**car, "market_price": med, "comps": mk.get("listings"), "market_km": mk.get("median_km")}
    if med and car["price_usd"]:
        out["pct_vs_market"] = round((car["price_usd"] / float(med) - 1) * 100)
    deal = db.q("SELECT discount_pct, mileage_vs_market FROM v_car_deal WHERE external_id=%s", (ext,))
    out["is_flagged_deal"] = bool(deal)
    if deal:
        out["discount_pct"] = deal[0]["discount_pct"]
        out["mileage_vs_market"] = deal[0]["mileage_vs_market"]
    return out


@mcp.tool()
def depreciation(make: str, model: str) -> list[dict]:
    """Median price by model year for a make+model — how it holds value with age."""
    return _get_db().q(
        "SELECT year, count(*) AS listings, "
        "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY price_usd)) AS median_price, "
        "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY mileage_km)) AS median_km "
        "FROM v_vehicle WHERE make ILIKE %s AND model ILIKE %s AND price_usd IS NOT NULL "
        "AND year IS NOT NULL GROUP BY year HAVING count(*) >= 3 ORDER BY year DESC",
        (make, model))


@mcp.tool()
def market_overview(region: Optional[str] = None, limit: int = 15) -> dict:
    """Snapshot: total active cars, and top makes by supply with median price and
    average days listed. Optionally scoped to a region."""
    db = _get_db()
    w = "status='active' AND price_usd IS NOT NULL"
    p: list[Any] = []
    if region:
        w += " AND region ILIKE %s"; p.append(f"%{region}%")
    total = db.q(f"SELECT count(*) AS n FROM v_vehicle WHERE {w}", tuple(p))[0]["n"]
    top = db.q(
        f"SELECT make, count(*) AS listings, "
        f"round(percentile_cont(0.5) WITHIN GROUP (ORDER BY price_usd)) AS median_price, "
        f"round(avg(days_listed)) AS avg_days_listed "
        f"FROM v_vehicle WHERE {w} AND make IS NOT NULL GROUP BY make "
        f"ORDER BY 2 DESC LIMIT %s", tuple(p) + (min(limit, 50),))
    deals = db.q("SELECT count(*) AS n FROM v_car_deal")[0]["n"]
    return {"region": region or "all", "total_active_cars": total,
            "open_deals": deals, "top_makes": top}


@mcp.tool()
def car_details(id_or_url: str) -> dict:
    """Full detail for one car — spec, seller, all photo URLs and price history."""
    ext = _ext_id(id_or_url)
    db = _get_db()
    base = db.q("SELECT external_id, title, make, model, year, mileage_km, price_usd, "
                "fuel_type, transmission, body_type, color, region, seller_type, "
                "condition, status, days_listed, url FROM v_vehicle WHERE external_id=%s", (ext,))
    if not base:
        return {"error": f"car {ext} not found"}
    out = base[0]
    out["photos"] = [r["url"] for r in db.q(
        "SELECT url FROM photo_urls WHERE listing_external_id=%s ORDER BY idx", (ext,))]
    out["price_history"] = db.q(
        "SELECT price, to_timestamp(observed_at)::date AS on FROM price_history "
        "WHERE external_id=%s ORDER BY observed_at", (ext,))
    return out


@mcp.tool()
def list_makes(limit: int = 40) -> list[dict]:
    """List available car makes with active listing counts."""
    return _get_db().q(
        "SELECT make, count(*) AS listings FROM v_vehicle WHERE status='active' "
        "AND make IS NOT NULL GROUP BY make ORDER BY 2 DESC LIMIT %s", (min(limit, 100),))


@mcp.tool()
def list_models(make: str, limit: int = 40) -> list[dict]:
    """List models (with counts) for a given make."""
    return _get_db().q(
        "SELECT model, count(*) AS listings FROM v_vehicle WHERE status='active' "
        "AND make ILIKE %s AND model IS NOT NULL GROUP BY model ORDER BY 2 DESC LIMIT %s",
        (f"%{make}%", min(limit, 100)))


def _query_sql(sql: str) -> list[dict]:
    """Run a read-only SELECT for open-ended car analytics. Query these views/tables:
      v_vehicle(external_id,make,model,year,mileage_km,price_usd,fuel_type,
                transmission,body_type,color,region,seller_type,condition,status,
                days_listed,url)
      v_car_deal(make,model,year,mileage_km,market_km,price_usd,market_price,
                 discount_pct,comps,mileage_vs_market,region,url)
      listings, price_history, events, photo_urls
    Only a single SELECT/WITH statement is allowed; results are capped.
    """
    s = sql.strip().rstrip(";").strip()
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise ValueError("only a single SELECT/WITH query is allowed")
    if ";" in s:
        raise ValueError("only one statement is allowed")
    if " limit " not in f" {low} ":
        s += " LIMIT 200"
    return _get_db().q(s)


# Expose the open-ended SQL tool only when explicitly enabled (default: off).
if os.environ.get("ALLOW_SQL", "").lower() in ("1", "true", "yes"):
    mcp.tool(name="query_sql")(_query_sql)


def run(http: bool = False, host: str = "127.0.0.1", port: int = 8000):
    if http:
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
