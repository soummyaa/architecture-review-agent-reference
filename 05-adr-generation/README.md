# 05 — ADR Generation

## Goal
Render the gap analysis and research output into an Architecture Decision
Record as a DOCX file, then write it back to SharePoint.

## Prerequisites
- 03-orchestration running successfully
- Graph access to a SharePoint site, verified in 00-setup

## Run
python 05-adr-generation/run.py
--submission data/synthetic/submissions/

SUB-001-northwind-analytics-cloud.md

## What you should understand by the end
Why document layout belongs in code and content belongs to the model, and
how the output lands somewhere people already work.
