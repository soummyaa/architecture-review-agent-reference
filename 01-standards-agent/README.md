# Module 01: Standards Agent

## Goal

Run one Microsoft Foundry agent grounded on the three synthetic internal
architecture standards. Given a submission, the agent returns a typed JSON
conformance report. Every finding cites an exact standard file and numbered
section.

## Prerequisites

- Completed [Module 00](../00-setup/README.md), including a working model
  deployment.
- `az login` completed for an identity with access to the Microsoft Foundry
  project.

The devcontainer installs this module's Python dependencies globally. Rebuild
the container after pulling dependency changes; no virtual environment is
needed.

## Run Standalone

Review either existing synthetic submission from the repository root:

```bash
python 01-standards-agent/run.py \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md

python 01-standards-agent/run.py \
  data/synthetic/submissions/SUB-002-quickship-document-service.md
```

The command reads the project endpoint and model deployment from the Module 00
deployment in `AZURE_RESOURCE_GROUP`. You can instead set
`FOUNDRY_PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME`, or pass
`--project-endpoint` and `--model-deployment`.

The Foundry client explicitly requests the `https://ai.azure.com/.default`
token scope. It uploads only the existing files under
`data/synthetic/standards`, creates one file-search agent, validates every
returned citation against the local standard headings, prints JSON, and removes
the temporary agent version, vector store, uploaded files, and conversation.

To inspect the agent, conversation, and run in the Microsoft Foundry portal,
add `--keep-agent`:

```bash
python 01-standards-agent/run.py --keep-agent \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md
```

The command prints the retained agent name and version to standard error. By
default, cleanup still runs so repeated workshop runs do not accumulate agent
versions and supporting resources.

## Output Contract

Each finding has one of four statuses: `conforms`, `does_not_conform`,
`partially_conforms`, or `not_evidenced`. Its citation contains a standard ID,
the exact numbered section heading, and the source file name.

Run the local contract tests without contacting Microsoft Foundry:

```bash
python -m unittest discover -s 01-standards-agent -p "test_*.py"
```