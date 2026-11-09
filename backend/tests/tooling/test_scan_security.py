import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts" / "scan-security.sh"


@pytest.mark.parametrize(
    ("scan_type", "target", "scanners"),
    [
        ("fs", ".", "vuln,misconfig,secret"),
        ("image", "bee-there:test", "vuln,secret"),
    ],
)
@pytest.mark.parametrize("failure_stage", ["none", "scan", "gate"])
def test_scans_then_gates_the_saved_report(
    tmp_path: Path,
    scan_type: str,
    target: str,
    scanners: str,
    failure_stage: str,
) -> None:
    calls = tmp_path / "calls.jsonl"
    trivy = tmp_path / "trivy"
    trivy.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TRIVY_TEST_CALLS'], 'a') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "stage = 'gate' if args[0] == 'convert' else 'scan'\n"
        "if stage == os.environ['TRIVY_TEST_FAILURE_STAGE']:\n"
        "    sys.exit(1 if stage == 'gate' else 2)\n"
        "if stage == 'scan':\n"
        "    pathlib.Path(args[args.index('--output') + 1]).write_text('{}')\n",
        encoding="utf-8",
    )
    trivy.chmod(0o755)
    report = tmp_path / "reports" / "project.json"

    result = subprocess.run(
        ["bash", str(SCRIPT), scan_type, target, str(report)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "TRIVY_TEST_CALLS": str(calls),
            "TRIVY_TEST_FAILURE_STAGE": failure_stage,
        },
        capture_output=True,
        text=True,
        check=False,
    )

    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    if failure_stage == "scan":
        assert result.returncode == 2
        assert len(recorded) == 1  # Do not gate a missing or stale report.
        assert not report.exists()
        return

    assert result.returncode == (1 if failure_stage == "gate" else 0)
    scan, gate = recorded
    exclusions = (
        [
            "--skip-dirs",
            ".git,**/.venv,**/node_modules,**/.cache,**/.pytest_cache,"
            "**/.mypy_cache,**/.ruff_cache,**/__pycache__,graphify-out,"
            ".trivy-reports,**/dist,**/release",
        ]
        if scan_type == "fs"
        else []
    )
    assert scan == [
        scan_type,
        "--config",
        "trivy.yaml",
        "--scanners",
        scanners,
        *exclusions,
        "--format",
        "json",
        "--exit-code",
        "0",
        "--severity",
        "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
        "--output",
        str(report),
        target,
    ]
    assert gate == [
        "convert",
        "--config",
        "trivy.yaml",
        "--format",
        "table",
        "--scanners",
        scanners,
        "--severity",
        "HIGH,CRITICAL",
        "--exit-code",
        "1",
        str(report),
    ]
    assert report.is_file()
