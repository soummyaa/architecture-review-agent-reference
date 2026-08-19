# Architecture Review Agent — Reference Build

A teaching reference for a two-day hands-on session. It builds a
multi-agent Architecture Review Agent on Microsoft Foundry, in pro-code
Python and Bicep.

This is a **progression, not a product**. Each numbered folder is a module
that runs standalone, so someone whose environment breaks at one step can
still pull the next one and keep up. Read it as a curriculum.

## The problem it solves

Someone proposes a technology. Today a human reads the proposal, compares
it against the organization's architecture standards, researches the
technology, writes up where it falls short, and produces an Architecture
Decision Record.

The live build runs a complete three-agent loop behind an orchestrator:
the standards agent evaluates the submission, the ADR author agent drafts
the decision record, and the reviewer agent checks the draft before the
reviewed ADR is returned. Intake and approved-source research remain in
the repository as reference implementations participants can read and pull.

It assists a review board. It does not replace one.

## Modules

| Module | What it builds | Status |
|---|---|---|
| `00-setup` | Foundry project and model deployment, plus a validator that proves access | Live build |
| `01-standards-agent` | One agent grounded on the standards library, returning findings with section-level citations | Live build |
| `02-intake` | Structured extraction from an unstructured submission into a typed schema | Reference |
| `03-orchestration` | Standards and ADR author agents wired behind an explicit orchestrator | Live build |
| `04-research` | External research restricted to a domain allowlist, every claim cited | Reference |
| `05-adr-generation` | ADR author output rendered locally as a DOCX; optional SharePoint write-back | Live build |
| `06-review-eval` | Reviewer agent over the draft, plus an evaluation harness | Live build (harness is reference) |

## Getting started

Open the repository in a Codespace or a devcontainer, then follow
[`00-setup/README.md`](00-setup/README.md). Nothing else will work until
its validator reports 3/3.

Two things that are easy to miss and cost the most time:

- **Data-plane RBAC is separate from subscription ownership.** Being Owner
  grants you nothing at the data plane. The Bicep assigns Azure AI
  Developer to a `principalId` you pass in.
- **Foundry and SharePoint must be in the same tenant.** A Graph token
  issued for one tenant cannot read a site in another.

## Data

Everything in `data/synthetic` is invented. Three architecture standards
and three technology submissions, written to produce a clear range of
outcomes:

| Submission | Expected result |
|---|---|
| Member Notification Service | Conforms — a clean approval |
| Northwind Analytics Cloud | Several genuine gaps — approve with conditions |
| QuickShip Document Service | Fails across all three standards — clear rejection |

The conforming case matters as much as the failing ones. Without it, there
is no evidence the system can say yes.

## Conventions

- Python and Bicep. No Terraform.
- Managed identity through `DefaultAzureCredential`. No keys in code or `.env`
  files.
- Each module runs standalone and has its own README.
- Readability over cleverness. People will read this code and extend it.
- No customer names, tenant identifiers, or real URLs anywhere in this
  repository.

## What this is not

Not a production deployment, not a security review, and not a CI/CD
reference. Two days is enough to teach a pattern, not to ship a system.