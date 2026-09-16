import orjson
from typer.testing import CliRunner

from latros.cli import app
from latros.common import write_json


def test_public_cli_workflow(built):
    root, _ = built
    runner = CliRunner()
    prefix = ["--root", str(root)]
    for command in (
        ["sources", "list"],
        ["sources", "validate"],
        ["data", "build", "--snapshot", "test"],
        ["data", "inspect", "--snapshot", "test"],
    ):
        result = runner.invoke(app, prefix + command)
        assert result.exit_code == 0, result.output
        assert orjson.loads(result.stdout)
    case = root / "case.json"
    write_json(
        case,
        dict(case_id="synthetic", observations=[dict(concept_id="HP:9000001", status="present")]),
    )
    for command in (["diagnose"], ["question", "next"]):
        result = runner.invoke(app, prefix + command + ["--snapshot", "test", "--case", str(case)])
        assert result.exit_code == 0, result.output
        assert orjson.loads(result.stdout)["safety_status"] == "not_evaluated"
