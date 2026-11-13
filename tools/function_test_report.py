"""Run the suite and documentation checks, recording per-function test evidence.

Run with the project interpreter from the repository root:
    .venv/Scripts/python.exe tools/function_test_report.py --date YYYY-MM-DD
"""

import argparse
from collections import Counter
import hashlib
import html
import inspect
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import h3v
from h3.api import basic_int as h3


def run_report(report_date):
    functions = {name: getattr(h3v, name) for name in h3v.__all__ if callable(getattr(h3v, name))}
    codes = {function.__code__: name for name, function in functions.items()}
    evidence = {name: Counter() for name in functions}
    tests = {}

    class Result(unittest.TextTestResult):
        active = None

        def startTest(self, test):
            super().startTest(test)
            self.active = test.id()
            method = getattr(type(test), test._testMethodName)
            tests[self.active] = {
                "status": "running", "started": time.perf_counter(),
                "source": str(Path(inspect.getsourcefile(method)).relative_to(ROOT)),
                "line": inspect.getsourcelines(method)[1],
            }

        def stopTest(self, test):
            row = tests[test.id()]
            row["seconds"] = time.perf_counter() - row.pop("started")
            if row["status"] == "running":
                row["status"] = "passed"
            self.active = None
            super().stopTest(test)

        def addSuccess(self, test):
            tests[test.id()]["status"] = "passed"
            super().addSuccess(test)

        def addFailure(self, test, err):
            tests[test.id()]["status"] = "failed"
            super().addFailure(test, err)

        def addError(self, test, err):
            tests[test.id()]["status"] = "error"
            super().addError(test, err)

        def addSkip(self, test, reason):
            tests[test.id()].update(status="skipped", reason=reason)
            super().addSkip(test, reason)

        def addExpectedFailure(self, test, err):
            tests[test.id()]["status"] = "expected failure"
            super().addExpectedFailure(test, err)

        def addUnexpectedSuccess(self, test):
            tests[test.id()]["status"] = "unexpected success"
            super().addUnexpectedSuccess(test)

        def addSubTest(self, test, subtest, err):
            if err is not None:
                tests[test.id()]["status"] = "failed"
            super().addSubTest(test, subtest, err)

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    log = io.StringIO()
    result = Result(unittest.runner._WritelnDecorator(log), True, 2)

    def profile(frame, event, arg):
        if event == "call" and result.active is not None:
            name = codes.get(frame.f_code)
            if name is not None:
                evidence[name][result.active] += 1

    started = time.perf_counter()
    previous_profile = sys.getprofile()
    try:
        sys.setprofile(profile)
        suite.run(result)
    finally:
        sys.setprofile(previous_profile)
    result.printErrors()
    unit_seconds = time.perf_counter() - started

    output_dir = ROOT / "reports"
    output_dir.mkdir(exist_ok=True)
    checks = []
    for builder in ("html", "doctest"):
        command = [sys.executable, "-m", "sphinx", "-b", builder, "-n", "-W", "--keep-going",
                   "docs", f"docs/_build/{builder}"]
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        filename = f"sphinx-{builder}.log"
        (output_dir / filename).write_text(completed.stdout + completed.stderr, encoding="utf-8")
        checks.append({"name": f"Sphinx {builder}", "exit_code": completed.returncode,
                       "seconds": time.perf_counter() - started, "log": filename,
                       "command": [Path(command[0]).name, *command[1:]]})

    manifest = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for folder, pattern in (("src", "*.py"), ("tests", "*.py"), ("docs", "*.md"))
                for path in sorted((ROOT / folder).glob(pattern))}
    rows = []
    for name, function in functions.items():
        associated = evidence[name]
        statuses = Counter(tests[test]["status"] for test in associated)
        status = ("NOT EXERCISED" if not associated else
                  "PASS" if statuses["passed"] == len(associated) else "REVIEW")
        rows.append({"name": name, "signature": str(inspect.signature(function)),
                     "module": function.__module__, "source": str(Path(inspect.getsourcefile(function)).relative_to(ROOT)),
                     "line": inspect.getsourcelines(function)[1],
                     "contract": inspect.getdoc(function).splitlines()[0],
                     "status": status, "test_count": len(associated),
                     "calls": sum(associated.values()), "test_outcomes": dict(statuses),
                     "tests": dict(sorted(associated.items()))})
    data = {"date": report_date, "timezone": "Europe/Berlin", "python": platform.python_version(),
            "h3": h3.versions(), "tested_state": "Current working tree, including uncommitted changes",
            "unit_tests": {"run": result.testsRun, "outcomes": dict(Counter(r["status"] for r in tests.values())),
                           "failures": len(result.failures), "errors": len(result.errors),
                           "successful": result.wasSuccessful(), "seconds": unit_seconds, "log": "unit-tests.log"},
            "checks": checks, "functions": rows, "tests": tests, "source_sha256": manifest,
            "limitations": [
                "Function evidence records calls made during each unittest test method in the main interpreter.",
                "A passing test may exercise multiple functions, including expected exception paths; counts are not independent function tests.",
                "Function execution is not statement or branch coverage, a performance benchmark, or proof of complete correctness.",
                "Calls in subprocesses, test discovery, and documentation examples are excluded from per-function attribution.",
                "Documentation checks are separate; skipped tests and expected failures are listed explicitly.",
                "No wheel build, clean-environment install, or cross-version/platform matrix is included.",
            ]}
    (output_dir / "unit-tests.log").write_text(log.getvalue(), encoding="utf-8")
    (output_dir / "function-test-report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    write_html(data, output_dir)
    print(json.dumps({"tests": data["unit_tests"], "functions": len(rows),
                      "function_statuses": dict(Counter(row["status"] for row in rows)),
                      "checks": checks, "report": str(output_dir / "function-test-report.html")}, indent=2))
    return 0 if result.wasSuccessful() and all(c["exit_code"] == 0 for c in checks) else 1


def write_html(data, output_dir):
    esc = html.escape
    all_tests = data["tests"]
    rows = []
    for function in data["functions"]:
        tests = "".join(f'<li><code>{esc(name)}</code> · {esc(all_tests[name]["status"])}'
                        f' · {count:,} calls<br><small>{esc(all_tests[name]["source"])}:{all_tests[name]["line"]}</small></li>'
                        for name, count in function["tests"].items())
        rows.append(f'<tr><td><details><summary><code>{esc(function["name"])}</code></summary>'
                    f'<p><code>{esc(function["name"] + function["signature"])}</code></p>'
                    f'<p>{esc(function["contract"])}</p><p class="muted">{esc(function["source"])}:{function["line"]}</p>'
                    f'<ul>{tests or "<li>No attributed calls.</li>"}</ul></details></td>'
                    f'<td>{esc(function["module"])}</td><td class="status">{function["status"]}</td>'
                    f'<td>{function["test_count"]}</td><td>{function["calls"]:,}</td></tr>')
    test_rows = "".join(f'<tr><td><code>{esc(name)}</code></td><td>{esc(row["status"])}</td>'
                        f'<td>{row["seconds"]:.4f}</td><td>{esc(row.get("reason", ""))}</td></tr>'
                        for name, row in all_tests.items())
    checks = "".join(f'<li><a href="{esc(check["log"])}">{esc(check["name"])}</a>: '
                     f'{"PASS" if check["exit_code"] == 0 else "FAIL"} ({check["seconds"]:.2f} s)</li>'
                     for check in data["checks"])
    limitations = "".join(f'<li>{esc(note)}</li>' for note in data["limitations"])
    total_functions = len(data["functions"])
    exercised = sum(f["test_count"] > 0 for f in data["functions"])
    passed = data["unit_tests"]["outcomes"].get("passed", 0)
    overall = "PASS" if data["unit_tests"]["successful"] and all(c["exit_code"] == 0 for c in data["checks"]) else "REVIEW"
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>H3V function test report</title>
<style>
body{{margin:0;background:#f5f7fa;color:#192536;font:15px/1.6 system-ui,sans-serif}}
main{{max-width:1200px;margin:40px auto;padding:0 24px}}h1{{font-size:34px;margin-bottom:4px}}
h2{{margin-top:32px}}.muted,small{{color:#596679}}a{{color:#1256a0}}
.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}}.card{{background:white;border:1px solid #dce3ec;border-radius:10px;padding:16px 24px;flex:1;min-width:160px}}
.card strong{{display:block;font-size:28px}}table{{border-collapse:collapse;width:100%;background:white}}
th,td{{border-bottom:1px solid #dce3ec;text-align:left;padding:12px;vertical-align:top}}th{{background:#e8eef5}}
code{{font-size:13px;overflow-wrap:anywhere}}summary{{cursor:pointer}}li{{margin:7px 0}}
.status{{font-weight:700}}input{{font:inherit;width:min(100%,520px);padding:10px;box-sizing:border-box;margin-bottom:16px}}
.scroll{{overflow:auto}}footer{{margin:32px 0;color:#596679}}details p{{margin:12px 0}}
</style><main>
<h1>H3V function test report</h1><p class="muted">{esc(data["date"])} · {esc(data["timezone"])} · {esc(data["tested_state"])}</p>
<div class="cards"><div class="card"><strong>{overall}</strong>Suite and documentation checks</div>
<div class="card"><strong>{passed} / {data["unit_tests"]["run"]}</strong>Unit tests passed</div>
<div class="card"><strong>{exercised} / {total_functions}</strong>Public functions exercised</div>
<div class="card"><strong>{data["unit_tests"]["seconds"]:.2f} s</strong>Instrumented unit suite duration</div></div>
<p>Python {esc(data["python"])} · h3-py {esc(data["h3"]["python"])} · H3 C {esc(data["h3"]["c"])}.
Public functions follow <code>h3v.__all__</code>; exported constants are excluded.</p>
<h2>Function evidence</h2><p>Expand a function to inspect its contract and the test methods that called it.
PASS means every attributed test passed. Test counts overlap across functions.</p>
<input id="filter" type="search" placeholder="Filter functions, modules, or test names" aria-label="Filter function evidence">
<div class="scroll"><table id="functions"><thead><tr><th>Function and test evidence</th><th>Module</th><th>Result</th><th>Tests</th><th>Calls</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Validation logs</h2><ul><li><a href="unit-tests.log">Unit test log</a>: {esc(str(data["unit_tests"]["outcomes"]))}</li>{checks}</ul>
<p><a href="function-test-report.json">Machine-readable results and SHA-256 source manifest</a>.</p>
<h2>Scope and limitations</h2><ul>{limitations}</ul>
<details><summary>All unit-test outcomes ({len(all_tests)})</summary><div class="scroll"><table><thead><tr><th>Test</th><th>Result</th><th>Seconds</th><th>Skip reason</th></tr></thead><tbody>{test_rows}</tbody></table></div></details>
<footer>Regenerate from the repository root: <code>.venv/Scripts/python.exe tools/function_test_report.py --date {esc(data["date"])}</code>.
This report describes the working tree captured by the included source manifest.</footer></main>
<script>document.getElementById('filter').addEventListener('input',function(){{const q=this.value.toLowerCase();document.querySelectorAll('#functions tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));}});</script></html>'''
    (output_dir / "function-test-report.html").write_text(document, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="User-facing report date (YYYY-MM-DD, Europe/Berlin)")
    sys.exit(run_report(parser.parse_args().date))
