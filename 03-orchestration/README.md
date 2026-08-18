# 03 — Orchestration

## Goal
Wire the standards agent to an ADR author agent behind an explicit
orchestrator. The orchestrator accepts a submission, passes the standards
findings to the author, and returns a draft ADR for review. This is the
multi-agent pattern the workshop exists to demonstrate.

## Prerequisites
- Completed [Module 00](../00-setup/README.md), including a successful validator run
- A synthetic submission from `data/synthetic/submissions`

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

Use `--standards-directory` to point the standards agent at your own Markdown
standards library instead of the synthetic workshop standards:

```bash
python 03-orchestration/run.py \
  --standards-directory path/to/standards \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

The command writes structured ADR content as JSON to standard output. Document
formatting is intentionally deferred to Module 05. Validation summaries and
elapsed times for both agent calls and the total orchestration are written to
standard error.

Add `--keep-agent` when participants need to inspect both agents,
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
2. The orchestrator passes that Pydantic model to the ADR author agent.
3. The author returns a validated `ArchitectureDecisionRecord`.

The `ConformanceReport` is the typed contract between agents. The author sees
the report rather than the original submission, which makes the handoff easy to
inspect, test, and extend during the workshop.

## Test

```bash
cd 03-orchestration
python -m unittest test_run.py
```

## What you should understand by the end
Where the orchestration boundary sits, how state passes between agents,
and why separating standards evaluation from ADR authoring is preferable
to one large prompt.
