import io
import json

import pytest
from pydantic import ValidationError
from pydantic_settings import CliApp

from cache_cli.main import main
from cache_cli.settings import CliSettings

BODY = {"list_1": ["a", "b"], "list_2": ["c", "d"]}


def parse(*args: str) -> CliSettings:
    return CliApp.run(CliSettings, cli_args=list(args))


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
        ["-j", json.dumps({"list_1": ["a"], "list_2": ["b", "c"]})],
        ["-j", json.dumps(BODY), "-r", "0"],
        ["-j", json.dumps(BODY), "-H", "not a url"],
        ["-i", "/does/not/exist.json"],
    ],
)
def test_invalid_arguments_are_rejected(args):
    with pytest.raises((ValidationError, SystemExit)):
        parse(*args)


def test_length_mismatch_in_input_file_fails_before_any_request(tmp_path, capsys):
    request_file = tmp_path / "in.json"
    request_file.write_text(json.dumps({"list_1": ["a"], "list_2": ["b", "c"]}))

    assert main(["-i", str(request_file), "-H", "http://127.0.0.1:1"]) == 1
    assert "same length" in capsys.readouterr().err


def test_repeat_returns_same_id_each_iteration(live_server_url, capsys):
    assert main(["-H", live_server_url, "-j", json.dumps(BODY), "-r", "3"]) == 0

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(lines) == 3
    assert {line["id"] for line in lines} == {lines[0]["id"]}
    assert lines[0]["output"] == "A, C, B, D"


def test_reads_input_file_and_writes_output_file(live_server_url, tmp_path):
    request_file = tmp_path / "in.json"
    request_file.write_text(json.dumps(BODY))
    result_file = tmp_path / "out.jsonl"

    assert main(["-H", live_server_url, "-i", str(request_file), "-o", str(result_file)]) == 0

    assert json.loads(result_file.read_text())["output"] == "A, C, B, D"


def test_reads_stdin(live_server_url, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(BODY)))

    assert main(["-H", live_server_url, "-i", "-"]) == 0

    assert json.loads(capsys.readouterr().out)["output"] == "A, C, B, D"


def test_reports_unreachable_server(capsys):
    assert main(["-j", json.dumps(BODY), "-H", "http://127.0.0.1:1"]) == 1
    assert "error:" in capsys.readouterr().err
