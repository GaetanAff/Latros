"""JSON-only stdout; failures on stderr and a nonzero exit status."""

from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from lxml import etree

from latros.clinical.models import ClinicalCase
from latros.common import LatrosError, encoded
from latros.knowledge.store import build_snapshot, load_manifest
from latros.reasoning.engine import Engine
from latros.reasoning.questions import next_question
from latros.sources.fetch import fetch_source
from latros.sources.registry import load_registry

app = typer.Typer(no_args_is_help=True, help="Latros — research CLI, safety not evaluated.")
sources = typer.Typer(no_args_is_help=True)
data = typer.Typer(no_args_is_help=True)
question = typer.Typer(no_args_is_help=True)
app.add_typer(sources, name="sources")
app.add_typer(data, name="data")
app.add_typer(question, name="question")


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
    output(load_registry(ctx.obj["registry"]).model_dump(mode="json"))


@sources.command("validate")
def validate_sources(ctx: typer.Context) -> None:
    registry = load_registry(ctx.obj["registry"])
    output({"valid": True, "sources": len(registry.sources), "schema_version": 1})


@sources.command("fetch")
def fetch(
    ctx: typer.Context, source: str = typer.Option(...), release: str = typer.Option(...)
) -> None:
    registry = load_registry(ctx.obj["registry"])
    output(fetch_source(ctx.obj["root"], registry.source(source, release)))


@data.command("build")
def build(ctx: typer.Context, snapshot: str = typer.Option(...)) -> None:
    output(build_snapshot(ctx.obj["root"], load_registry(ctx.obj["registry"]), snapshot))


@data.command("inspect")
def inspect(ctx: typer.Context, snapshot: str = typer.Option(...)) -> None:
    output(load_manifest(ctx.obj["root"], snapshot))


@app.command("diagnose")
def diagnose(
    ctx: typer.Context,
    snapshot: Annotated[str, typer.Option()],
    case: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
) -> None:
    engine = Engine(ctx.obj["root"], snapshot)
    output(engine.diagnose(ClinicalCase.model_validate_json(case.read_bytes())))


@question.command("next")
def next_command(
    ctx: typer.Context,
    snapshot: Annotated[str, typer.Option()],
    case: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
) -> None:
    engine = Engine(ctx.obj["root"], snapshot)
    output(next_question(engine, ClinicalCase.model_validate_json(case.read_bytes())))


def main() -> None:
    try:
        app()
    except (LatrosError, ValueError, OSError, httpx.HTTPError, etree.XMLSyntaxError) as exc:
        # ValidationError inherits ValueError. No case content is logged to files.
        typer.echo(f"Latros error: {exc}", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
