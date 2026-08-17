# 00 — Setup

## Goal
Provision the Azure resources every later module depends on, and prove
they are reachable before the workshop begins.

## Prerequisites
- An Azure subscription with Contributor and role assignment rights
- Azure CLI and Bicep installed (the devcontainer handles this)

## Run
python 02-intake/run.py
--submission data/synthetic/submissions/

SUB-002-quickship-document-service.md

## What you should understand by the end
Why the handoff between agents should be a typed contract rather than
prose, and how structured output makes every downstream agent simpler.
