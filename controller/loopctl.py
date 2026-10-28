#!/usr/bin/env python3
from loop.cli import main
from loop.util import Rejected
import json
import sys

if __name__ == "__main__":
    try:
        main()
    except (Rejected, OSError) as ex:
        print(json.dumps({"status": "REJECTED", "error": str(ex)}), file=sys.stderr)
        raise SystemExit(2)
