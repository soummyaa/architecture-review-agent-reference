# 05 — ADR Generation

## Goal
Render the ADR author agent's output into an Architecture Decision Record
as a local DOCX file. Writing the completed document back to SharePoint is
an optional, separate step.

## Prerequisites
- Reviewed ADR JSON produced by [Module 06](../06-review-eval/README.md)
- Python dependencies installed from this module's `requirements.txt`

## Run
From the repository root, first capture the reviewed output from the
three-agent chain:

```bash
python -m pip install -r 05-adr-generation/requirements.txt
python 06-review-eval/run.py \
	data/synthetic/submissions/SUB-001-northwind-analytics-cloud.md \
  > reviewed-adr.json
python 05-adr-generation/run.py reviewed-adr.json
```

The default output is `05-adr-generation/output/<submission-id>-adr.docx`.
Use `--output` to choose another local path or `--template` to render with a
custom DOCX template. The model produces content only; `docxtpl` applies the
layout from `adr-template.docx`.

## Optional SharePoint write-back

Local rendering does not require Microsoft Graph. To publish the already
rendered file as a separate step, add the explicit upload flag:

```bash
python 05-adr-generation/run.py reviewed-adr.json \
  --upload-to-sharepoint \
  --sharepoint-hostname <tenant>.sharepoint.com \
  --sharepoint-site-path /sites/<workshop-site>
```

The signed-in identity needs Graph write access to the target site. If Graph
returns HTTP 403, the command reports the missing write permission clearly and
leaves the successfully rendered local DOCX in place.

## Customize the template

Open `adr-template.docx` in Word to adjust styles and layout while preserving
the Jinja tags. To regenerate the workshop default template:

```bash
python 05-adr-generation/build_template.py
```

## Test

```bash
cd 05-adr-generation
python -m unittest -v test_run.py
```

## What you should understand by the end
Why document layout belongs in code and content belongs to the model, and
how to produce a usable local document before adding an optional publishing
integration such as SharePoint write-back.
