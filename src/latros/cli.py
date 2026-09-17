"""JSON-only stdout; failures on stderr and a nonzero exit status."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from lxml import etree

from latros.clinical.loading import ClinicalCaseDocument, load_clinical_case
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError, encoded
from latros.knowledge.importers_v2 import import_registry_v2
from latros.knowledge.loading import load_manifest_document
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.store import build_snapshot
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.reasoning.engine import Engine
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
app.add_typer(sources, name="sources")
app.add_typer(data, name="data")
app.add_typer(question, name="question")


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
def build(ctx: typer.Context, snapshot: str = typer.Option(...)) -> None:
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
    adapter = _strategy(ctx.obj["root"], snapshot, strategy)
    if _v2_output(case_document, output_contract):
        profile = load_reasoning_profile(_profile_path(strategy))
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
    adapter = _strategy(ctx.obj["root"], snapshot, strategy)
    if _v2_output(case_document, output_contract):
        profile = load_reasoning_profile(_profile_path(strategy))
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


def _profile_path(strategy: str) -> Path:
    name = f"{strategy}.json"
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
