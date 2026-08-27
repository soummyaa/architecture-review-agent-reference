# Module 04: Research Agent

## Goal
Research a submitted technology from external sources, restricted to a
configurable domain allowlist, with every claim carrying a citation.

## Prerequisites
- Completed [Module 00](../00-setup/README.md), including a working Foundry
  project and model deployment.
- An approved list of source domains.

## Run Standalone

Run the agent against one of the existing synthetic submissions:

```bash
python -m pip install -r 04-research/requirements.txt
export AZURE_RESOURCE_GROUP=<your-resource-group>
python 04-research/run.py \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md \
  --allowed-domain learn.microsoft.com \
  --allowed-domain cisa.gov
```

The command returns a typed `TechnologyResearch` object as JSON. Every claim
contains one citation. The domains are applied to the Foundry web-search tool
and checked again against the returned URLs. Plain web search is managed by
Foundry and does not require a project connection.

The technologies in the workshop submissions are synthetic. An empty claims
list is therefore a valid and expected result when no approved source confirms
the proposed product. The agent is instructed not to turn search results for a
similarly named real product into evidence.

## Test

The unit tests do not require a search connection:

```bash
cd 04-research
python -m unittest -v test_run.py
```

## What you should understand by the end
How to constrain external grounding so the output is defensible, and why
an allowlist is a governance control rather than a technical detail. The
research agent is built live in this module; its external search capability
remains optional in the submission-to-reviewed-ADR loop.
