import io
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pydantic_settings import CliApp

from cache_cli.main import main, run
from cache_cli.settings import CliSettings
from cache_service.config import Settings
from cache_service.main import create_app

BODY = {"list_1": ["a", "b"], "list_2": ["c", "d"]}


def parse(*args: str) -> CliSettings:
    return CliApp.run(CliSettings, cli_args=list(args))


@pytest.fixture
def client(transformer, tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path}/cache.db")
    with TestClient(create_app(settings, transformer)) as client:
        yield client


def test_short_and_long_flags_are_equivalent():
    short = parse("-H", "http://svc:9000", "-r", "3", "-j", json.dumps(BODY))
    long = parse("--host", "http://svc:9000", "--repeat", "3", "--json", json.dumps(BODY))

    assert short == long
    assert short.repeat == 3


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-j", json.dumps(BODY), "-i", "-"],
        ["-j", "not json"],
        ["-j", json.dumps({"list_1": ["a"], "list_2": []})],
        ["-j", json.dumps(BODY), "-r", "0"],
        ["-j", json.dumps(BODY), "-H", "not a url"],
        ["-i", "/does/not/exist.json"],
    ],
)
def test_invalid_arguments_are_rejected(args):
    with pytest.raises((ValidationError, SystemExit)):
        parse(*args)


def test_run_repeats_and_hits_cache(client, transformer):
    out = io.StringIO()

    run(parse("-j", json.dumps(BODY), "-r", "3"), client, out)

    lines = [json.loads(line) for line in out.getvalue().splitlines()]
    assert len(lines) == 3
    assert {line["id"] for line in lines} == {lines[0]["id"]}
    assert lines[0]["output"] == "A, C, B, D"
    assert len(transformer.calls) == 1


def test_main_reads_input_file_and_writes_output_file(tmp_path, monkeypatch, client):
    request_file = tmp_path / "in.json"
    request_file.write_text(json.dumps(BODY))
    result_file = tmp_path / "out.jsonl"
    # Route the CLI's HTTP client through the in-process app instead of the network.
    monkeypatch.setattr("cache_cli.main.httpx.Client", lambda **_: client)

    assert main(["-i", str(request_file), "-o", str(result_file)]) == 0

    assert json.loads(result_file.read_text())["output"] == "A, C, B, D"


def test_main_reads_stdin(monkeypatch, capsys, client):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(BODY)))
    monkeypatch.setattr("cache_cli.main.httpx.Client", lambda **_: client)

    assert main(["-i", "-"]) == 0

    assert json.loads(capsys.readouterr().out)["output"] == "A, C, B, D"


def test_main_reports_unreachable_server(capsys):
    assert main(["-j", json.dumps(BODY), "-H", "http://127.0.0.1:1"]) == 1
    assert "error:" in capsys.readouterr().err
