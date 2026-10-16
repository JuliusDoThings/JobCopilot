"""Stdlib-only Compose configuration and real HTTP smoke checks; no Azure calls."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def verify_configuration():
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    config = json.loads(result.stdout)
    services = config["services"]
    assert set(services) == {"backend", "frontend"}, "Exactly two services required"
    for service in services.values():
        assert service.get("healthcheck", {}).get("test"), "Missing healthcheck"
        assert not service.get("env_file"), "Host env files must not be loaded"
        assert not service.get("secrets"), "No secrets needed"
        assert not service.get("volumes"), "No host files mounted"
        for port in service.get("ports", []):
            assert port["host_ip"] == "127.0.0.1", "Only loopback ports allowed"
        assert not any("AZURE" in key or "KEY" in key or "TOKEN" in key
                       for key in service.get("environment", {})), "Credentials forbidden"
    frontend = services["frontend"]
    assert frontend["environment"]["JOB_COPILOT_BENCH_API_BASE"] == "http://backend:8000"
    assert frontend["environment"]["FASTAPI_BASE_URL"] == "http://backend:8000"
    assert frontend["depends_on"]["backend"]["condition"] == "service_healthy"
    for name in services:
        dockerfile = (ROOT / name / "Dockerfile").read_text()
        assert "USER " in dockerfile, "Non-root runtime required"
        assert "COPY . " not in dockerfile, "Use explicit source copies"
        ignore = (ROOT / name / ".dockerignore").read_text()
        assert ignore.startswith("**\n"), "Build context must use an allowlist"
        assert "**/.env*" in ignore, "Env files excluded even in allowed directories"
    print("Compose config: two services, loopback ports, healthchecks, no secrets")


def get(url):
    with OPENER.open(url, timeout=30) as response:
        assert response.status == 200
        return response.read().decode()


def run_case(scenario):
    request = urllib.request.Request(
        "http://localhost:3000/api/dev/valorization",
        data=json.dumps({"scenarioId": scenario["id"]}).encode(),
        headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"},
    )
    with OPENER.open(request, timeout=15) as response:
        assert response.status == 200
        return json.load(response)


def verify_http(unavailable=False):
    corpus = json.loads((ROOT / "frontend/lib/dev-bench/corpus.json").read_text())
    assert "Job" in get("http://localhost:3000/"), "Product UI missing"
    page = get("http://localhost:3000/dev/valorization")
    assert "VAL-001" in page, "Bench corpus missing from SSR page"
    counts = {"conforme": 0, "ecart": 0, "non_execute": 0}
    for scenario in corpus["scenarios"]:
        result = run_case(scenario)
        assert result["scenarioId"] == scenario["id"]
        if unavailable:
            assert result["outcome"] == "not_executed", "Unavailable API must not succeed"
            assert result["actual"] is None and result["error"]
            counts["non_execute"] += 1
            continue
        assert result["outcome"] == "executed" and result["httpStatus"] == 200
        actual = result["actual"]
        assert isinstance(actual, list) and len(actual) == len(scenario["expected"])
        expected = []
        for entry in scenario["expected"]:
            row = {key: value for key, value in entry.items() if key != "questionRequired"}
            expected.append(row)
        equal = True
        for observed, wanted, requirement in zip(actual, expected, scenario["expected"]):
            assert set(observed) == {"skill", "status", "evidence", "suggestion", "clarification_question"}
            equal &= all(observed[key] == value for key, value in wanted.items())
            equal &= bool(observed["clarification_question"]) == requirement["questionRequired"]
            if observed["suggestion"] is not None:
                assert observed["suggestion"] == observed["evidence"]
                assert observed["suggestion"] in scenario["input"]["cv_text"]
        if equal:
            counts["conforme"] += 1
        else:
            # Known business gap, not a relaxed expectation: keep it visible.
            assert scenario["id"] == "VAL-007", "Unexpected business regression"
            observed = actual[0]
            assert observed["skill"] == "Python"
            assert observed["status"] == "needs_clarification"
            assert observed["evidence"] == scenario["input"]["cv_text"]
            assert observed["suggestion"] is None and observed["clarification_question"]
            counts["ecart"] += 1
    report = {"corpusVersion": corpus["version"], "backendUnavailable": unavailable, "counts": counts}
    print(json.dumps(report))
    (ROOT / ("compose-unavailable-report.json" if unavailable else "compose-smoke-report.json")).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--unavailable", action="store_true")
    args = parser.parse_args()
    try:
        if args.config_only:
            verify_configuration()
        else:
            verify_http(args.unavailable)
    except Exception as error:
        # Never dump upstream bodies or environment configuration.
        print(f"Compose verification failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
