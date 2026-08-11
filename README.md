# Azure DevOps Pipelines

[![Validate pipelines](https://github.com/sadvi11/azure-devops-pipelines/actions/workflows/validate.yml/badge.svg)](https://github.com/sadvi11/azure-devops-pipelines/actions/workflows/validate.yml)
![Azure DevOps](https://img.shields.io/badge/Azure%20DevOps-Pipelines-0078D4?logo=azuredevops&logoColor=white)
![Security](https://img.shields.io/badge/secrets-none%20stored-3ecca0)
![License](https://img.shields.io/badge/License-MIT-green)

A multi-stage Azure DevOps pipeline — build, test, security scan, deploy to dev,
gated deploy to production — built with reusable templates and **no stored
credentials anywhere**.

> **What this badge means.** Azure Pipelines YAML cannot execute on GitHub
> Actions; running it requires an Azure DevOps organisation, service connections
> and environments. The badge above is a **validation** badge: it proves the
> definitions are structurally sound and free of the security mistakes that
> matter. It does **not** prove a green deployment. [`docs/setup.md`](docs/setup.md)
> has the steps to wire it up, and states the same thing.
>
> Every other repository in this portfolio proves its central claim by executing
> it. This one cannot, so it says so rather than implying otherwise.

## Why an Azure-first shop cares

Canadian banks, insurers and government run on Azure DevOps, frequently for a
specific reason: **an approval attached to an environment lives outside the
repository.** A developer cannot bypass a production gate by editing the
pipeline in their own branch, because the gate is not in the file. That property
is what auditors ask about.

## The three security decisions

**No credential exists to leak.** The service connections use **workload
identity federation** — Azure DevOps exchanges a short-lived token rather than
holding a secret. There is no client secret to rotate, expire or steal.

**Application secrets come from Key Vault** through a variable group. The
pipeline references names; values never appear in this repository or in the
pipeline UI. Rotating a secret in the vault changes nothing here.

**Security scans fail the build.** None of them set `continueOnError`. A scanner
in warn-only mode produces a number that goes up quietly for two years — if a
finding is acceptable it gets suppressed explicitly with a reason in the tool's
own config, not by ignoring the tool.

## Structure

```
azure-pipelines.yml          # stages: Build -> Security -> DeployDev -> DeployProd
templates/
  build.yml                  # test + publish results and coverage
  security-scan.yml          # pip-audit, checkov, gitleaks over git history
  deploy.yml                 # deployment job with environment: gate
  steps/use-python.yml
```

Stages are templates rather than one long file. A 400-line pipeline nobody dares
change is the normal failure mode.

## Two details worth pointing at in an interview

**The deploy verifies it is actually serving.** After the Bicep deployment, the
pipeline waits for the revision holding 100% of traffic to reach `Running`, then
curls `/health`. This mirrors a real incident: a fix was deployed, the platform
reported success, and the old revision served every request — so the "verified"
measurement measured the old version. ([the postmortem](https://github.com/sadvi11/sre-incident-practice))

**Gitleaks scans git history, not the working tree.** A secret committed and
then deleted in a later commit is still a leaked secret, and a working-tree scan
reports clean.

## What CI actually checks

`scripts/validate_pipelines.py` catches, in seconds, the classes of problem
Azure DevOps only reports by failing a run:

| Check | Why |
|---|---|
| Hard-coded credentials | A value assigned inline instead of coming from Key Vault or a service connection |
| Secrets echoed to logs | Azure DevOps masks only the secrets it knows about |
| `continueOnError` on a security step | A scan that cannot fail the build gates nothing |
| Deployment job without `environment:` | No approval gate, no audit trail |
| Template parameters | Declared and never passed, or passed and never declared |

And it runs in **both directions** — CI points the validator at deliberately
broken pipelines in `tests/fixtures/` and fails if the validator *accepts* them.

That check earned its place immediately. The first version of the validator
**missed two of its own four test cases**: the regex `\b(secret)` never matched
`clientSecret`, because in camelCase the `S` is preceded by a word character and
there is no word boundary; and the deployment-gate check only looked at
top-level `jobs`, not the `stages[].jobs` shape a real pipeline uses. Both
passed validation while a hard-coded credential and an ungated production deploy
sat in the fixture. Fixed, and the negative fixture is why they were found.

## Also here

[**GitHub Actions vs Azure DevOps**](docs/github-actions-vs-azure-devops.md) —
an honest comparison from having shipped the same workload through both,
including where Actions is genuinely better and the three-expression-syntax trap
that catches everyone.

## Author

Sadhvi Sharma · Cloud & AI Engineer · Calgary, Alberta
[github.com/sadvi11](https://github.com/sadvi11)
