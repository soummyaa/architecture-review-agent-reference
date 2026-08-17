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

This system does the first pass: reads the submission, evaluates it
against a standards library, researches within approved sources, drafts
the ADR, reviews its own draft, and files the result where the review
board already works.

It assists a review board. It does not replace one.

## Modules

| Module | What it builds | Status |
|---|---|---|
| `00-setup` | Foundry project, model deployment, Key Vault, storage, plus a validator that proves access | Working |
| `01-standards-agent` | One agent grounded on the standards library, returning findings with section-level citations | Working |
| `02-intake` | Structured extraction from an unstructured submission into a typed schema | Scaffolded |
| `03-orchestration` | Gap analysis agent wired to the standards agent behind an explicit orchestrator | Scaffolded |
| `04-research` | External research restricted to a domain allowlist, every claim cited | Scaffolded |
| `05-adr-generation` | Render findings into a DOCX ADR from a template, write back to SharePoint | Scaffolded |
| `06-review-eval` | Critic agent over the draft, plus an evaluation harness | Scaffolded |

## Getting started

Open the repository in a Codespace or a devcontainer, then follow
[`00-setup/README.md`](00-setup/README.md). Nothing else will work until
its validator reports 3/3.

Two things that are easy to miss and cost the most time:

- **Data-plane RBAC is separate from subscription ownership.** Being Owner
  grants you nothing at the data plane. The Bicep assigns Azure AI
  Developer, Key Vault Secrets User, and Storage Blob Data Contributor to
  a `principalId` you pass in.
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
- Managed identity and Key Vault. No keys in code or `.env` files.
- Each module runs standalone and has its own README.
- Readability over cleverness. People will read this code and extend it.
- No customer names, tenant identifiers, or real URLs anywhere in this
  repository.

## What this is not

Not a production deployment, not a security review, and not a CI/CD
reference. Two days is enough to teach a pattern, not to ship a system.
