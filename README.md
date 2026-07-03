# olx-cars-mcp

An **MCP server** for asking natural-language questions about **OLX / dubizzle
Lebanon cars-for-sale** — deals, prices, market stats — answered from a cleaned
Postgres database.

Ask things like:
- *"Best Mercedes deals posted this week under $25k"*
- *"What's a 2019 Kia Sportage worth?"*
- *"Show me BMWs under $10k in Beirut, cheapest first"*
- *"Is this a good price? https://www.olx.com.lb/ad/…-ID116961204.html"*
- *"How does a Range Rover Sport depreciate by year?"*

## Two ways to use it

### A) Hosted — just add a URL (no install, no credentials)
If a public instance is running, add it to Claude Code:
```bash
claude mcp add --transport http olx-cars https://<the-public-url>/mcp
```
…then ask car questions. Nothing to install; you don't need database access.

### B) Local (stdio) — run it yourself
Needs a read-only `CARS_DATABASE_URL` to the cars database.
```bash
pip install git+https://github.com/charbeld/olx-cars-mcp
```
Claude Desktop / Code config:
```json
{
  "mcpServers": {
    "olx-cars": {
      "command": "olx-cars-mcp",
      "env": { "CARS_DATABASE_URL": "postgresql://…?sslmode=require" }
    }
  }
}
```

## Tools

| Tool | Purpose |
|------|---------|
| `search_cars` | filter/sort active cars (make, model, year, price, mileage, region, seller) |
| `find_deals` | underpriced cars vs comparable listings (discount, comps, mileage flag, posted date) |
| `market_price` | median/p25/p75 + median mileage for a make+model+year |
| `rank_car` | where a given listing (id/url) sits vs its comps |
| `depreciation` | median price by year for a make+model |
| `market_overview` | supply, top makes, medians, avg days-listed (optionally by region) |
| `car_details` | full spec + all photo URLs + price history for one car |
| `list_makes` / `list_models` | available makes/models with counts |
| `query_sql` | *(opt-in via `ALLOW_SQL=1`)* guarded read-only SELECT for open-ended analytics |

Data is cars-for-sale only, cleaned (no rentals/parts/placeholder-priced/duplicate/
invalid-year listings), with mileage-aware deal detection. Deals are algorithmic
leads (price + mileage vs same make/model/year) — verify condition/history on the
listing.

## Deploy a public instance (free)

The server speaks **streamable HTTP** at `/…/mcp`. Any host that runs the Docker
image works. The env vars:
- `CARS_DATABASE_URL` — **read-only** Postgres DSN (secret)
- `ALLOW_SQL` — leave `0` for public (keeps the arbitrary-SQL tool off)

**Google Cloud Run** (recommended — generous free tier, scale-to-zero):
```bash
gcloud run deploy olx-cars-mcp --source . --region us-central1 \
  --allow-unauthenticated --port 8000 \
  --set-env-vars ALLOW_SQL=0 --set-env-vars CARS_DATABASE_URL="postgresql://…"
```
Public MCP URL: `https://olx-cars-mcp-xxxx.run.app/mcp`

**Hugging Face Spaces** (no credit card): create a **Docker** Space from this repo,
add `CARS_DATABASE_URL` as a Space secret, set `ALLOW_SQL=0`. URL:
`https://<user>-olx-cars-mcp.hf.space/mcp`

**Render** (`render.yaml` included): connect the repo, set `CARS_DATABASE_URL`.

## License
MIT
