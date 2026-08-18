# 06 — Review and Evaluation

## Goal
Build a reviewer agent that checks the draft ADR against the source findings
before a human sees it. The reviewer is the third agent in the live build and
completes the submission-in, reviewed-ADR-out loop.

The evaluation harness that scores output across the synthetic cases remains
reference code for participants to read and pull; it is not built live.

## Prerequisites
- Completed [Module 00](../00-setup/README.md), including a successful validator run
- Python dependencies installed from this module's `requirements.txt`

## Run
From the repository root, run the complete three-agent chain and capture its
structured output:

```bash
python -m pip install -r 06-review-eval/requirements.txt
export AZURE_RESOURCE_GROUP=<your-resource-group>
python 06-review-eval/run.py \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md \
  > reviewed-adr.json
```

The output contains the standards report, author draft, reviewer flags, and
reviewed ADR. Render only the reviewed ADR with Module 05:

```bash
python 05-adr-generation/run.py reviewed-adr.json
```

## The three-agent chain

The orchestrator is deliberately linear:

1. The standards agent produces a typed `ConformanceReport`.
2. The ADR author consumes that report and produces a draft.
3. The reviewer receives both objects, flags unsupported claims and omitted
   findings, and returns corrected ADR content for document rendering.

## Evaluation harness

The separate harness runs the full chain for the three existing synthetic
submissions:

```bash
python 06-review-eval/evaluate.py
```

Each case receives one point for a valid reviewed ADR, one for no unsupported
claims in the author draft, and one for no omitted findings. The harness is
intentionally small: it loops over three files, runs the orchestrator, and sums
three Boolean checks per result.

## What you should understand by the end
How a review pass reduces hallucination risk and completes the orchestrated
workflow. The reference harness also demonstrates how to define and measure
what "good" means across the synthetic cases.
