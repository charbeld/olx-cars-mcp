# olx-cars-mcp

An MCP server for asking questions about cars for sale on OLX / dubizzle Lebanon.
It answers from a database that is refreshed automatically, so the numbers stay
current. You do not need to install or run anything. Just add the hosted server
to your MCP client and start asking.

## Install

No accounts, no keys, no local setup. The server URL is:

```
https://olx-cars-mcp-196205401893.us-central1.run.app/mcp
```

### Claude Code

Run:

```
claude mcp add --transport http olx-cars https://olx-cars-mcp-196205401893.us-central1.run.app/mcp
```

### Claude Desktop or Claude web

1. Open Settings, then Connectors (also called Integrations).
2. Click Add custom connector.
3. Give it a name, for example OLX Cars.
4. Paste the URL above.
5. Choose Streamable HTTP as the transport type.
6. Save. No API key or login is needed.

### Other MCP clients

Point them at the same URL as a streamable HTTP server.

## What you can ask

- Best Mercedes deals posted this week under 25000
- What is a 2019 Kia Sportage worth
- Show me BMWs under 10000 in Beirut, cheapest first
- Is this a good price? (paste an OLX listing link)
- How does a Range Rover Sport lose value by year
- Which makes have the most listings in Beirut and their median price
- Full details and photos for a specific listing

## What it can do

- Search cars by make, model, year, price, mileage, region and seller.
- Find deals: cars priced below similar listings (same make, model and year),
  with the discount, how many listings it was compared against, and whether the
  mileage is at or below average.
- Give a market price for any make, model and year (median and range).
- Rank a specific listing against comparable cars to see if it is a good price.
- Show how a model depreciates by year.
- Give a market overview: supply, top makes, median prices and days listed.
- Return full details, all photos and price history for a listing.

## Notes

The data is cars for sale only. Deals are suggestions, so always check the
actual listing.

License: MIT
