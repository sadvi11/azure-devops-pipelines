# GitHub Actions vs Azure DevOps Pipelines

I have shipped the same workload through both. This is what actually differs in
practice, rather than a feature matrix.

## The short version

**Azure DevOps is better at governance. GitHub Actions is better at speed of
iteration.** If a compliance officer needs to prove who approved a production
change, Azure DevOps answers it out of the box. If you want a contributor's
first pull request to run tests without an administrator involved, Actions wins.

## Where Azure DevOps is genuinely better

**Environments and approvals are first-class.** In Azure DevOps, an approval is
attached to an *environment*, which lives outside the repository. A developer
cannot bypass a production gate by editing the pipeline in their branch —
the gate is not in the file. GitHub Actions has environments too, but the
protection rules are newer and less granular, and much of the ecosystem still
gates on branch conditions written into the workflow, which is exactly the
bypassable pattern.

**Variable groups backed by Key Vault.** A variable group maps secret names to a
Key Vault, so rotating a secret changes nothing in any repository. GitHub secrets
are copies — rotate the source and you must remember every repository holding
the old value.

**Deployment history as a real object.** Azure DevOps records what deployed to
which environment, when, and who approved it, queryable independently of build
logs. In Actions, that history is something you reconstruct from workflow runs.

**Cross-repository templates with enforcement.** A central `templates` repository
can be *required* — Azure DevOps can reject a pipeline that does not extend an
approved template. Actions can share reusable workflows, but nothing forces
their use.

## Where GitHub Actions is genuinely better

**Setup cost.** Actions needs a repository. Azure DevOps needs an organisation,
a project, a service connection, an agent pool, and usually a conversation with
whoever owns them.

**The marketplace and community.** Far more actions, updated faster.

**Pull requests from forks.** Actions handles untrusted contributions with a
sensible default permission model. Azure DevOps is built for a trusted internal
audience and fork workflows are awkward.

**Local reasoning.** A workflow file is largely self-contained. An Azure DevOps
pipeline's real behaviour depends on environment approvals, variable groups and
service connections you cannot see in the repository — which is the same
property that makes its governance strong.

## Security: the honest comparison

Both support **workload identity federation**, and both should use it. Neither
needs a stored cloud credential in the current generation.

- Actions: `permissions: id-token: write`, then `azure/login@v2` with a client
  ID. The trust is a federated credential on an app registration, scoped to a
  repository and branch.
- Azure DevOps: a service connection configured for workload identity
  federation. The trust is scoped to the service connection, which is itself
  permission-controlled per project.

The Azure DevOps model is slightly stronger in a large organisation because the
service connection is an administered object — someone must grant a project
access to it. In Actions, anyone who can push a workflow to an authorised branch
can use the federated credential, so the branch protection *is* the security
boundary.

## What I would choose

| Situation | Choice |
|---|---|
| Regulated Canadian enterprise, audit requirements, existing Azure DevOps | **Azure DevOps** |
| Open source, or a small team already on GitHub | **Actions** |
| Public repo needing contributor pull requests | **Actions** |
| Production deploys needing a named approver and an audit trail | **Azure DevOps** |
| Greenfield startup on Azure | Actions, and revisit when compliance appears |

The uncomfortable answer many teams land on is **both**: Actions for CI on pull
requests because it is fast and fork-friendly, Azure DevOps for the gated
production deploy because that is where the audit trail is needed. That split is
more common than either camp admits.

## Concrete syntax differences that cost time

| Concept | Azure DevOps | GitHub Actions |
|---|---|---|
| Variable reference | `$(name)` | `${{ env.name }}` / `$NAME` |
| Compile-time expression | `${{ parameters.x }}` | `${{ inputs.x }}` |
| Runtime expression | `$[ variables.x ]` | no direct equivalent |
| Reusable unit | `template:` | `uses:` reusable workflow |
| Approval gate | `environment:` on a `deployment` job | `environment:` with protection rules |
| Set an output | `##vso[task.setvariable]` | `>> $GITHUB_OUTPUT` |

The one that catches everyone: Azure DevOps has **three** expression syntaxes
that evaluate at different times. `${{ }}` is resolved when the pipeline
compiles, so it cannot see anything produced during the run. Using it where you
needed `$[ ]` produces an empty string rather than an error.
