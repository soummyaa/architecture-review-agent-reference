# 03 — Orchestration

## Goal
Add a gap analysis agent that consumes the intake output and the standards
findings, wired behind an explicit orchestrator. This is the multi-agent
pattern the workshop exists to demonstrate.

## Prerequisites
- 01 and 02 running successfully

## Run
python 03-orchestration/run.py
--submission data/synthetic/submissions/

SUB-002-quickship-document-service.md

## What you should understand by the end
Where the orchestration boundary sits, how state passes between agents,
and why decomposing into several agents beats one large prompt.
