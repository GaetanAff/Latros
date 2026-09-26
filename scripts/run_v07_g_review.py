"""Launch the isolated, offline G1/G2 human-review UI on loopback only."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from latros.review.adjudication import create_adjudication_app
from latros.review.g07 import create_review_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--exports", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--adjudication", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    exports = args.exports or root / (
        "data/staging/v0.7-g5" if args.adjudication else "data/staging/v0.7-g"
    )
    app = (
        create_adjudication_app(root, exports)
        if args.adjudication
        else create_review_app(root, exports)
    )
    label = "G5 adjudication" if args.adjudication else "G1/G2"
    print(f"Revue locale {label} : http://127.0.0.1:{args.port}/", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
