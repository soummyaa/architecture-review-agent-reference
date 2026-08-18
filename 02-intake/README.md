# Module 02: Intake

> **Reference module:** Participants read and pull this module as reference
> code. It is not part of the live workshop build.

## Goal

Convert a local synthetic technology-review submission into a typed intake
contract, with an optional Microsoft Graph reader that demonstrates the
SharePoint source path.

## Prerequisites

- Python dependencies installed from this module's `requirements.txt`.
- For the optional SharePoint path, completed [Module 00](../00-setup/README.md)
  with validated Graph access.

## Run Standalone

The default path reads one of the existing synthetic files locally and requires
no cloud access:

```bash
python -m pip install -r 02-intake/requirements.txt
python 02-intake/run.py \
  data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md
```

The command writes a validated `IntakeSubmission` as JSON. The parser is
deliberately direct: metadata and known Markdown headings map to Pydantic
fields, while `support_model` and `commercials` remain optional because the
synthetic cases do not all contain both sections.

## Optional SharePoint source

The same parser can read Markdown from the default document library through
Microsoft Graph:

```bash
export SHAREPOINT_HOSTNAME=<tenant>.sharepoint.com
export SHAREPOINT_SITE_PATH=/sites/<workshop-site>
python 02-intake/run.py \
  --sharepoint-item-path Submissions/SUB-001-northwind-analytics-cloud.md
```

This path uses `DefaultAzureCredential` and the
`https://graph.microsoft.com/.default` scope. Local execution remains the
primary standalone example.

## Test

```bash
cd 02-intake
python -m unittest -v test_run.py
```