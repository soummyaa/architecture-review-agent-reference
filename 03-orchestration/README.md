# 03 — Orchestration

## Goal
Wire the standards, research, and ADR author agents behind an explicit
orchestrator. The orchestrator accepts a submission, validates internal
standards findings, optionally gathers allowlisted external research, and
returns a draft ADR for review. This is the multi-agent pattern the workshop
exists to demonstrate.

## Prerequisites
- Completed [Module 00](../00-setup/README.md), including a successful validator run
- A synthetic submission from `data/synthetic/submissions`
- An approved research domain allowlist

## Run
From the repository root:

```bash
python -m pip install -r 03-orchestration/requirements.txt
export AZURE_RESOURCE_GROUP=<your-resource-group>
python 03-orchestration/run.py \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

You can pass `--project-endpoint` and `--model-deployment` instead of using
`AZURE_RESOURCE_GROUP`. Authentication uses `DefaultAzureCredential` and the
`https://ai.azure.com/.default` scope required by the Foundry project endpoint.
Plain web search is managed by Foundry and does not require a project connection.

Approved research domains are stored in
[`research-allowlist.json`](research-allowlist.json). Replace its example
domains with the customer's approved sources, or select another config file:

```bash
python 03-orchestration/run.py \
  --research-allowlist path/to/research-allowlist.json \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

The config is a JSON object with an `allowed_domains` string array. Values are
hostnames without a scheme or path. The same domains constrain the Foundry
web-search tool and validate every returned citation URL.

When the allowlist or search connection has not been approved, keep the rest of
the chain runnable with `--skip-research`:

```bash
python 03-orchestration/run.py --skip-research \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

Use `--standards-directory` to point the standards agent at your own Markdown
standards library instead of the synthetic workshop standards:

```bash
python 03-orchestration/run.py \
  --standards-directory path/to/standards \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

The command writes structured ADR content as JSON to standard output. Document
formatting is intentionally deferred to Module 06. Validation summaries and
elapsed times for both agent calls and the total orchestration are written to
standard error.

Add `--keep-agent` when participants need to inspect all three agents,
conversations, and runs in the Microsoft Foundry portal:

```bash
python 03-orchestration/run.py --keep-agent \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

Each retained agent name and version is printed to standard error. Without the
flag, all temporary resources are cleaned up as before.

## How the orchestration works

The flow is deliberately linear:

1. The standards agent reviews the submission and returns a validated
   `ConformanceReport`.
2. Unless skipped, the research agent takes the report's technology name and
  returns validated `TechnologyResearch`. Every claim has one allowlisted URL
  citation.
3. The orchestrator passes both Pydantic models to the ADR author agent.
4. The author returns a validated `ArchitectureDecisionRecord`.

`ConformanceReport` and `TechnologyResearch` are typed contracts between agents.
The standards library remains authoritative. Research can inform ADR context
and consequences, but it cannot override a standards finding. With
`--skip-research`, the author receives no research object and works only from
the conformance report.

## Test

```bash
cd 03-orchestration
python -m unittest test_run.py
```

## What you should understand by the end
Where the orchestration boundary sits, how typed state passes between agents,
how an optional external dependency can be skipped, and why standards remain
authoritative when external context is available.
