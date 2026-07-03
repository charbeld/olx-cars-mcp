import argparse
import os

from .server import run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="olx-cars-mcp",
                                 description="MCP server for OLX Lebanon cars-for-sale")
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    ap.add_argument("--host", default="0.0.0.0")
    # honour $PORT (Render / Cloud Run / most PaaS set it)
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    args = ap.parse_args(argv)
    run(http=args.http, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
