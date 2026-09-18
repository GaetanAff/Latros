"""JSON-only stdout; failures on stderr and a nonzero exit status."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from lxml import etree

from latros.clinical.loading import ClinicalCaseDocument, load_clinical_case
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError, encoded, write_json
from latros.knowledge.curation import (
    audit_curation_package,
    export_approved_assertions,
    write_review_workbook,
)
from latros.knowledge.importers_v2 import import_registry_v2
from latros.knowledge.loading import load_manifest_document
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.research_unreviewed import (
    UNREVIEWED_SNAPSHOT_SUFFIX,
    UNREVIEWED_WARNING,
    build_unreviewed_research_snapshot,
    require_official_gate,
)
from latros.knowledge.store import build_snapshot
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.reasoning.engine import Engine
from latros.reasoning.general_v1 import GeneralV1Strategy
from latros.reasoning.profiles import load_reasoning_profile
from latros.reasoning.results_v2 import build_differential_v2, build_question_v2
from latros.reasoning.semantic_v1_adapter import SemanticV1Adapter
from latros.sources.fetch import fetch_source
from latros.sources.fetch_v2 import fetch_source_v2
from latros.sources.loading import load_registry_document
from latros.sources.registry import Registry
from latros.sources.registry_v2 import RegistryV2

app = typer.Typer(no_args_is_help=True, help="Latros — research CLI, safety not evaluated.")
sources = typer.Typer(no_args_is_help=True)
data = typer.Typer(no_args_is_help=True)
question = typer.Typer(no_args_is_help=True)
curation = typer.Typer(no_args_is_help=True)
app.add_typer(sources, name="sources")
app.add_typer(data, name="data")
app.add_typer(question, name="question")
app.add_typer(curation, name="curation")


class OutputContract(StrEnum):
    auto = "auto"
    v1 = "v1"
    v2 = "v2"


@app.callback()
def configure(
    ctx: typer.Context,
    root: Annotated[Path, typer.Option("--root")] = Path("."),
    registry: Annotated[Path, typer.Option("--registry")] = Path("sources/registry.yaml"),
) -> None:
    """--root isolates local data; --registry selects explicitly pinned sources."""
    ctx.obj = {
        "root": root.resolve(),
        "registry": registry if registry.is_absolute() else root / registry,
    }


def output(value: Any) -> None:
    typer.echo(encoded(value).decode(), nl=False)


@sources.command("list")
def list_sources(ctx: typer.Context) -> None:
    output(load_registry_document(ctx.obj["registry"]).model_dump(mode="json"))


@sources.command("validate")
def validate_sources(ctx: typer.Context) -> None:
    registry = load_registry_document(ctx.obj["registry"])
    output(
        {
            "valid": True,
            "sources": len(registry.sources),
            "schema_version": registry.schema_version,
        }
    )


@sources.command("fetch")
def fetch(
    ctx: typer.Context, source: str = typer.Option(...), release: str = typer.Option(...)
) -> None:
    registry = load_registry_document(ctx.obj["registry"])
    if isinstance(registry, Registry):
        output(fetch_source(ctx.obj["root"], registry.source(source, release)))
    else:
        output(fetch_source_v2(ctx.obj["root"], registry.source(source, release)))


@data.command("build")
def build(
    ctx: typer.Context,
    snapshot: str = typer.Option(...),
    allow_unreviewed_research_data: Annotated[
        bool, typer.Option("--allow-unreviewed-research-data")
    ] = False,
    curation_package: Annotated[Path, typer.Option("--curation-package")] = Path(
        "curation/v0.5-orl"
    ),
) -> None:
    package_path = (
        curation_package if curation_package.is_absolute() else ctx.obj["root"] / curation_package
    )
    if snapshot == "v0.5.0":
        if allow_unreviewed_research_data:
            raise LatrosError(
                "The unreviewed override can never be used to build the official v0.5.0 snapshot"
            )
        require_official_gate(ctx.obj["root"], package_path)
        raise LatrosError("Official v0.5.0 approved snapshot inputs are not configured")
    if snapshot.endswith(UNREVIEWED_SNAPSHOT_SUFFIX):
        if not allow_unreviewed_research_data:
            raise LatrosError(
                "Unreviewed snapshot refused by default; pass "
                "--allow-unreviewed-research-data deliberately"
            )
        typer.echo(f"WARNING: {UNREVIEWED_WARNING}", err=True)
        result = build_unreviewed_research_snapshot(
            ctx.obj["root"],
            package_path,
            snapshot,
            allow_unreviewed_research_data=True,
        )
        output(result.model_dump(mode="json"))
        return
    if allow_unreviewed_research_data:
        raise LatrosError(
            "The unreviewed override may only build a snapshot ending in -dev-unreviewed"
        )
    registry = load_registry_document(ctx.obj["registry"])
    if isinstance(registry, RegistryV2):
        knowledge = import_registry_v2(ctx.obj["root"], registry)
        result = build_snapshot_v2(ctx.obj["root"], registry, snapshot, knowledge)
        output(result.model_dump(mode="json"))
    else:
        output(build_snapshot(ctx.obj["root"], registry, snapshot))


@data.command("inspect")
def inspect(ctx: typer.Context, snapshot: str = typer.Option(...)) -> None:
    manifest = load_manifest_document(ctx.obj["root"], snapshot)
    output(
        manifest.model_dump(mode="json")
        if isinstance(manifest, KnowledgeSnapshotManifestV2)
        else manifest
    )


@curation.command("audit")
def audit_curation(
    ctx: typer.Context,
    package: Annotated[Path, typer.Option("--package")] = Path("curation/v0.5-orl"),
    require_publishable: Annotated[bool, typer.Option("--require-publishable")] = False,
    report_path: Annotated[Path | None, typer.Option("--report")] = None,
) -> None:
    """Audit a review package without treating pending work as a snapshot."""
    package_path = package if package.is_absolute() else ctx.obj["root"] / package
    report = audit_curation_package(ctx.obj["root"], package_path)
    report_payload = report.model_dump(mode="json")
    if report_path is not None:
        resolved_report_path = (
            report_path if report_path.is_absolute() else ctx.obj["root"] / report_path
        )
        write_json(resolved_report_path, report_payload)
    output(report_payload)
    if require_publishable and report.status != "ready_for_publication":
        raise LatrosError("Curation publication gate is blocked")


@curation.command("export-approved")
def export_curation(
    ctx: typer.Context,
    package: Annotated[Path, typer.Option("--package")] = Path("curation/v0.5-orl"),
    destination: Annotated[Path, typer.Option("--destination")] = Path(
        "data/staging/v0.5-orl/approved-assertions.jsonl"
    ),
) -> None:
    """Export importer-compatible JSONL only after the publication gate passes."""
    package_path = package if package.is_absolute() else ctx.obj["root"] / package
    destination_path = destination if destination.is_absolute() else ctx.obj["root"] / destination
    records = export_approved_assertions(ctx.obj["root"], package_path, destination_path)
    output(
        {
            "exported": len(records),
            "destination": str(destination_path),
            "status": "approved",
        }
    )


@curation.command("review-workbook")
def review_workbook(
    ctx: typer.Context,
    package: Annotated[Path, typer.Option("--package")] = Path("curation/v0.5-orl"),
    destination: Annotated[Path, typer.Option("--destination")] = Path(
        "docs/reviews/v0.5-orl/assertion-review.md"
    ),
) -> None:
    """Generate a review table without recording or implying any approval."""
    package_path = package if package.is_absolute() else ctx.obj["root"] / package
    destination_path = destination if destination.is_absolute() else ctx.obj["root"] / destination
    write_review_workbook(package_path, destination_path)
    output(
        {
            "destination": str(destination_path),
            "status": "review_workbook_generated",
        }
    )


@app.command("diagnose")
def diagnose(
    ctx: typer.Context,
    snapshot: Annotated[str, typer.Option()],
    case: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    strategy: Annotated[str, typer.Option("--strategy")] = "semantic_v1",
    output_contract: Annotated[
        OutputContract, typer.Option("--output-contract")
    ] = OutputContract.auto,
) -> None:
    case_document = load_clinical_case(case.read_bytes())
    if strategy == "general_v1":
        if not isinstance(case_document, ClinicalCaseV2):
            raise LatrosError("general_v1 accepts only ClinicalCaseV2")
        if output_contract is OutputContract.v1:
            raise LatrosError("general_v1 has no v1 output contract")
        profile = load_reasoning_profile(_profile_path(strategy, snapshot))
        output(
            GeneralV1Strategy(ctx.obj["root"], snapshot, profile)
            .diagnose(case_document)
            .model_dump(mode="json")
        )
        return
    adapter = _strategy(ctx.obj["root"], snapshot, strategy)
    if _v2_output(case_document, output_contract):
        profile = load_reasoning_profile(_profile_path(strategy, snapshot))
        output(
            build_differential_v2(ctx.obj["root"], case_document, adapter, profile).model_dump(
                mode="json"
            )
        )
    else:
        output(adapter.diagnose_legacy(case_document))


@question.command("next")
def next_command(
    ctx: typer.Context,
    snapshot: Annotated[str, typer.Option()],
    case: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    strategy: Annotated[str, typer.Option("--strategy")] = "semantic_v1",
    output_contract: Annotated[
        OutputContract, typer.Option("--output-contract")
    ] = OutputContract.auto,
) -> None:
    case_document = load_clinical_case(case.read_bytes())
    if strategy == "general_v1":
        if not isinstance(case_document, ClinicalCaseV2):
            raise LatrosError("general_v1 accepts only ClinicalCaseV2")
        if output_contract is OutputContract.v1:
            raise LatrosError("general_v1 has no v1 output contract")
        profile = load_reasoning_profile(_profile_path(strategy, snapshot))
        output(
            GeneralV1Strategy(ctx.obj["root"], snapshot, profile)
            .question(case_document)
            .model_dump(mode="json")
        )
        return
    adapter = _strategy(ctx.obj["root"], snapshot, strategy)
    if _v2_output(case_document, output_contract):
        profile = load_reasoning_profile(_profile_path(strategy, snapshot))
        output(
            build_question_v2(ctx.obj["root"], case_document, adapter, profile).model_dump(
                mode="json"
            )
        )
    else:
        output(adapter.next(case_document).payload)


def _strategy(root: Path, snapshot: str, strategy: str) -> SemanticV1Adapter:
    if strategy != "semantic_v1":
        raise LatrosError(f"Unknown reasoning strategy: {strategy}")
    return SemanticV1Adapter(Engine(root, snapshot))


def _profile_path(strategy: str, snapshot: str | None = None) -> Path:
    name = (
        "general_v1-orl-unreviewed.json"
        if strategy == "general_v1"
        and snapshot is not None
        and snapshot.endswith(UNREVIEWED_SNAPSHOT_SUFFIX)
        else f"{strategy}.json"
    )
    candidates = [
        Path(__file__).resolve().parents[2] / "profiles" / name,
        Path(__file__).resolve().parent / "profiles" / name,
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise LatrosError(f"Reasoning profile is missing: {strategy}")


def _v2_output(case: ClinicalCaseDocument, output_contract: OutputContract) -> bool:
    return output_contract is OutputContract.v2 or (
        output_contract is OutputContract.auto and isinstance(case, ClinicalCaseV2)
    )


def main() -> None:
    try:
        app()
    except (LatrosError, ValueError, OSError, httpx.HTTPError, etree.XMLSyntaxError) as exc:
        # ValidationError inherits ValueError. No case content is logged to files.
        typer.echo(f"Latros error: {exc}", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
