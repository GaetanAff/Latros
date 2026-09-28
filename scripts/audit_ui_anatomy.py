"""Read-only counts of navigation references resolved in a chosen local snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from latros.knowledge.presentation_repository import ObservationPresentationRepository
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2
from latros.ui.anatomy import load_navigation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--snapshot", default="v0.7.0-general-dev-unreviewed")
    args = parser.parse_args()
    config = load_navigation()
    with CanonicalKnowledgeRepositoryV2(args.root, args.snapshot) as repository:
        presentation = ObservationPresentationRepository(repository)
        regions = {}
        for region, node in config["nodes"].items():
            presentation.navigation_options(config["system"], node["codes"], "en")
            identities = presentation.resolve_supported_codes(config["system"], node["codes"])
            regions[region] = {
                "configured": len(node["codes"]),
                "resolved": len({row["concept_id"] for row in identities.values()}),
                "missing_or_ambiguous": [code for code in node["codes"] if code not in identities],
            }
    print(json.dumps({"snapshot": args.snapshot, "regions": regions}, indent=2))


if __name__ == "__main__":
    main()
