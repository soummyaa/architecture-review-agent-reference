# 05 — Review and Evaluation

## Goal
Build a reviewer agent that checks the draft ADR against the source findings
before a human sees it. The reviewer is the fourth agent in the live build and
completes the submission-in, reviewed-ADR-out loop.

The evaluation harness that scores output across the synthetic cases remains
reference code for participants to read and pull; it is not built live.

## Prerequisites
- Completed [Module 00](../00-setup/README.md), including a successful validator run
- An approved research domain allowlist as described in [Module 03](../03-orchestration/README.md)
- Python dependencies installed from this module's `requirements.txt`

## Run
From the repository root, run the complete four-agent chain, which includes
research by default, and capture its structured output:

```bash
python -m pip install -r 05-review-eval/requirements.txt
export AZURE_RESOURCE_GROUP=<your-resource-group>
python 05-review-eval/run.py \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md \
  > reviewed-adr.json
```

The output contains the standards report, author draft, reviewer flags, and
reviewed ADR. Render only the reviewed ADR with Module 06:

```bash
python 06-adr-generation/run.py reviewed-adr.json
```

For a portal walkthrough, add `--keep-agent` before the submission path. By
default, the standards, research, ADR author, and reviewer agent versions and
their conversations are then retained for inspection in the Microsoft Foundry
portal. Their names and versions are printed to standard error, so redirected
JSON remains valid:

```bash
python 05-review-eval/run.py --keep-agent \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md \
  > reviewed-adr.json
```

Without the flag, the existing cleanup behavior remains in place.

Use `--skip-research` when the approved source allowlist is not ready or the
external lookup is not wanted. The research agent is not invoked, so the ADR
author receives no research object and determines the decision from the
standards findings alone. The standards, ADR author, and reviewer agents still
run in that order.

When the flag is omitted but no Bing or Bing Custom Search connection ID is
configured, the orchestrator prints one skip notice and continues. In that
case, the ADR author receives a valid `TechnologyResearch` object with an empty
claims list rather than `None` or a partial result.

## The four-agent chain

The orchestrator is deliberately linear:

1. The standards agent produces a typed `ConformanceReport`.
2. Unless `--skip-research` is passed, the research agent adds allowlisted
  external context.
3. The ADR author consumes both typed inputs and produces a draft.
4. The reviewer receives the report and draft, flags unsupported claims and omitted
   findings, and returns corrected ADR content for document rendering.

## Evaluation harness

> **Reference code:** Participants read and pull the evaluation harness rather
> than building it live. The reviewer agent above is built live.

Run the live decision regression after changing agent instructions:

```bash
python 05-review-eval/decision_regression.py
```

The command runs the three configured regression submissions through the
standards, research, ADR author, and reviewer agents. It verifies these final
reviewed decisions:

| Submission | Expected decision | Expected conditions |
|---|---|---|
| `SUB-003` | `approved` | None |
| `SUB-001` | `approved_with_conditions` | At least one |
| `SUB-002` | `rejected` | None |

Each submission prints the expected and actual decision and condition count.
The command exits non-zero if any workflow fails or any result differs, making
it suitable for checking participant-authored instructions and for automated
regression runs.

Together, these three deliberately unambiguous synthetic cases prove that the
system can approve cleanly, approve with conditions, and reject. Real
submissions will contain more ambiguity, so a production deployment should
expect more variation than this regression suite shows.

The separate quality-scoring harness runs every `SUB-*.md` file in the selected
directory:

```bash
python 05-review-eval/evaluate.py
```

The repository currently contains four submission files, so the default command
runs all four. Point `--submissions-directory` at another non-empty directory to
evaluate a different set. Each case receives one point for a valid reviewed ADR, one for no
unsupported claims in the author draft, and one for no omitted findings.

## What you should understand by the end
How a review pass reduces hallucination risk and completes the orchestrated
workflow. The reference harness also demonstrates how to define and measure
what "good" means across the synthetic cases.
