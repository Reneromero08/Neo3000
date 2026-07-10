import json
import pathlib
import subprocess
import sys
import tempfile


def run(executable: pathlib.Path, mode: str, root: pathlib.Path):
    path = root / f"{mode}.jsonl"
    subprocess.run([str(executable), mode, str(path)], check=True)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return path, records


def aggregates(records):
    return [record for record in records if record.get("record_type") == "aggregate_delta"]


def latest_header(records):
    return [record for record in records if record.get("event_id") == "neo.compute.trace.header.v2"][-1]


def main():
    trace_exe = pathlib.Path(sys.argv[1]).resolve()
    disabled_exe = pathlib.Path(sys.argv[2]).resolve()
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)

        _, records = run(trace_exe, "aggregate", root)
        rows = aggregates(records)
        assert len(rows) == 1
        assert rows[0]["count"] == 100
        assert rows[0]["total_duration_ns"] == 500
        assert rows[0]["total_bytes"] == 700
        assert latest_header(records)["writer_open_count"] == 1

        _, records = run(trace_exe, "distinct", root)
        rows = aggregates(records)
        assert len(rows) == 4
        assert len({(r["layer_index"], r["device_id"], r["tensor_shape"], r["placement_reason"]) for r in rows}) == 4

        _, records = run(trace_exe, "batches", root)
        rows = aggregates(records)
        assert sum(row["count"] for row in rows) == 25
        assert sum(row["total_duration_ns"] for row in rows) == 125
        assert sum(row["total_bytes"] for row in rows) == 175

        path, records = run(trace_exe, "limits", root)
        headers = [record for record in records if record.get("event_id") == "neo.compute.trace.header.v2"]
        notices = [record for record in records if record.get("event_id") == "neo.compute.trace.truncation.v2"]
        assert path.stat().st_size <= 16 * 1024
        assert notices or any(header["trace_truncated"] for header in headers)
        assert any(record.get("dropped_event_count", 0) > 0 for record in notices + headers)

        _, records = run(trace_exe, "unknown", root)
        assert aggregates(records)[0]["placement_reason"] == "unknown"

        disabled_trace = root / "disabled.jsonl"
        env = dict(__import__("os").environ)
        env["NEO_COMPUTE_TRACE_PATH"] = str(disabled_trace)
        subprocess.run([str(disabled_exe)], check=True, env=env)
        assert not disabled_trace.exists()
        assert b"NEO_COMPUTE_TRACE_PATH" not in disabled_exe.read_bytes()

    print("neo compute trace aggregation tests passed")


if __name__ == "__main__":
    main()
