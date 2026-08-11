# Wiring this up in Azure DevOps

The pipeline definitions in this repository are complete and validated, but a
pipeline only runs inside an Azure DevOps organisation. These are the steps.

## 1. Organisation and project

Create a free organisation at <https://dev.azure.com>, then a project.
The free tier includes 1800 minutes/month of Microsoft-hosted agents for
private projects, and more for public ones.

## 2. Service connection using workload identity federation

**Do not create a service principal with a client secret.** Use federation, so
no credential is stored:

Project settings → Service connections → New → Azure Resource Manager →
**Workload Identity federation (automatic)**.

Name them to match the pipeline: `sc-sentiment-dev` and `sc-sentiment-prod`.

Scope each to its own resource group, not the subscription. A dev pipeline
should not be able to touch production.

## 3. Environments with approvals

Pipelines → Environments → New environment. Create `sentiment-dev` and
`sentiment-prod`.

On `sentiment-prod` only: Approvals and checks → **Approvals** → add yourself
as an approver.

This is the step that makes `environment:` in `templates/deploy.yml` mean
something. The gate lives here, outside the repository, so it cannot be removed
by editing a file in a pull request.

## 4. Variable group backed by Key Vault

Pipelines → Library → Variable group → name it `sentiment-api-kv` to match the
pipeline. Toggle **Link secrets from an Azure key vault**, choose the vault, and
select the secrets to expose.

Values never enter this repository or the pipeline UI. Rotating a secret in the
vault changes nothing here.

Add a non-secret variable `acrName` in the same group, or as a pipeline
variable.

## 5. Create the pipeline

Pipelines → New pipeline → GitHub → select this repository → **Existing Azure
Pipelines YAML file** → `/azure-pipelines.yml`.

## What is verified and what is not

The checks in this repository run on every commit and prove the definitions are
structurally sound, free of hard-coded credentials, and that every deployment
job has an approval gate.

They do **not** prove the pipeline runs green, because that requires the
organisation, service connections and environments above. That is stated plainly
rather than implied — the badge on this repository is a validation badge, not a
deployment badge.
