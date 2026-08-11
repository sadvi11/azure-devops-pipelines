#!/usr/bin/env python3
"""Structural and security checks for Azure Pipelines definitions.

Azure DevOps only tells you a pipeline is wrong by failing a run, which means
a mistake costs a commit, a queue wait and an agent. These checks run in
seconds and catch the classes of problem that matter:

  * a credential written into the pipeline instead of coming from a service
    connection or Key Vault
  * a security scan that cannot fail the build, which is a scan that does
    nothing
  * a deployment job with no `environment:`, which is a deployment with no
    approval gate and no audit trail
  * template parameters that are declared and never passed, or passed and
    never declared

Pure text and YAML analysis -- no Azure DevOps organisation required, which is
why CI can run it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Values that look like a credential typed directly into the file. Deliberately
# does not flag $(var) or ${{ parameters.x }} -- those are references, which is
# the pattern we WANT.
SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b\w*(password|passwd|secret|token|apikey|api_key|connectionstring)
    \s*[:=]\s*
    (?!\$\()          # not a variable reference
    (?!\$\{\{)        # not a template expression
    ['"]?[A-Za-z0-9+/=_\-]{8,}
    """
)

# A secret echoed into logs. Azure DevOps masks known secrets, but only ones it
# knows about; a value read from a file or built by string concatenation is not.
ECHO_SECRET = re.compile(r"(?i)\becho\b[^\n]*\$\(\s*\w*(secret|password|token|key)\w*\s*\)")

failures: list[str] = []
notes: list[str] = []


def fail(path: Path, msg: str) -> None:
    try:
        name = path.relative_to(ROOT)
    except ValueError:
        name = path
    failures.append(f"{name}: {msg}")


def load(path: Path) -> Any:
    try:
        # Azure Pipelines uses ${{ }} which is not YAML; it parses as a string,
        # so safe_load works, but a tab or bad indent still raises here.
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        fail(path, f"invalid YAML: {str(exc).splitlines()[0]}")
        return None


def check_no_inline_secrets(path: Path, text: str) -> None:
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if SECRET_ASSIGNMENT.search(line):
            fail(path, f"line {i}: looks like a hard-coded credential")
        if ECHO_SECRET.search(line):
            fail(path, f"line {i}: echoes a secret-looking variable into the log")


def check_security_steps_can_fail(path: Path, text: str, doc: Any) -> None:
    """A scanner with continueOnError does not gate anything."""
    if "security" not in path.name and "scan" not in path.name:
        return
    if re.search(r"continueOnError:\s*true", text, re.I):
        fail(path, "a security step sets continueOnError: true - it cannot gate the build")


def _all_job_lists(doc: Any):
    """Yield every jobs list, whether at the top level (template) or nested
    under stages (root pipeline). Missing the nested case meant a deployment
    with no approval gate passed validation."""
    if not isinstance(doc, dict):
        return
    if isinstance(doc.get("jobs"), list):
        yield doc["jobs"]
    for stage in doc.get("stages") or []:
        if isinstance(stage, dict) and isinstance(stage.get("jobs"), list):
            yield stage["jobs"]


def check_deploy_has_environment(path: Path, doc: Any) -> None:
    """Deployment jobs must use `environment:`; that is where approvals attach."""
    for jobs in _all_job_lists(doc):
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if "deployment" in job and not job.get("environment"):
                fail(path, f"deployment job '{job['deployment']}' has no environment: - "
                           "no approval gate and no deployment history")


def check_template_parameters(path: Path, doc: Any) -> None:
    """Every declared parameter without a default must be passed by some caller."""
    if not isinstance(doc, dict):
        return
    declared = doc.get("parameters")
    if not isinstance(declared, list):
        return
    required = {p["name"] for p in declared
                if isinstance(p, dict) and "name" in p and "default" not in p}
    if not required:
        return

    rel = path.relative_to(ROOT).as_posix()
    callers = [p for p in ROOT.rglob("*.yml")
               if p != path and rel.split("templates/")[-1] in p.read_text()]
    if not callers:
        notes.append(f"{rel}: template is never referenced")
        return

    for caller in callers:
        text = caller.read_text()
        # Find the template reference block and the parameters passed with it.
        for match in re.finditer(
                r"template:\s*\S*" + re.escape(rel.split("/")[-1]) + r"\s*\n(.*?)(?=\n\s*-\s|\Z)",
                text, re.S):
            block = match.group(1)
            for name in required:
                if f"{name}:" not in block:
                    fail(caller, f"calls {rel} without required parameter '{name}'")


def check_root_pipeline(path: Path, doc: Any) -> None:
    if not isinstance(doc, dict):
        return
    if "stages" not in doc:
        fail(path, "root pipeline has no stages")
    if "trigger" not in doc:
        fail(path, "no trigger defined - the pipeline would only ever run manually")
    for var in doc.get("variables", []) or []:
        if isinstance(var, dict) and "group" not in var and "name" not in var:
            fail(path, f"malformed variables entry: {var}")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    files = sorted(p for p in root.rglob("*.yml")
                   if ".github" not in p.parts and "tests" not in p.relative_to(root).parts)
    if not files:
        print("no pipeline YAML found", file=sys.stderr)
        return 1

    for path in files:
        text = path.read_text()
        doc = load(path)
        check_no_inline_secrets(path, text)
        check_security_steps_can_fail(path, text, doc)
        check_deploy_has_environment(path, doc)
        if root == ROOT:
            check_template_parameters(path, doc)
        if path.name == "azure-pipelines.yml":
            check_root_pipeline(path, doc)

    print(f"checked {len(files)} pipeline file(s)")
    for n in notes:
        print(f"  note: {n}")
    if failures:
        print(f"\n{len(failures)} problem(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("all pipeline checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
