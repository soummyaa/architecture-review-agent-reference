# Project context

This repository is a teaching reference for a hands-on workshop.
It builds a multi-agent Architecture Review Agent on Microsoft Foundry.

## Domain
An enterprise submits a proposed technology (a vendor product, an
open-source library, a data platform) for architecture review. The
system compares the submission against a library of internal
architecture standards, optionally researches the technology from
approved external sources, identifies gaps, and generates an
Architecture Decision Record as a Word document.

## Constraints
- Python and Bicep. No Terraform.
- Microsoft Foundry for agents and orchestration.
- SharePoint via Microsoft Graph for document input and output.
- Managed identity and Key Vault only. Never keys in code or .env files.
- All sample data is synthetic and lives in data/synthetic.
- No customer names, tenant IDs, or real URLs anywhere in this repo.

## Structure
Each numbered folder is a workshop module that must run standalone.
00-setup, 01-standards-agent, 02-intake, 03-orchestration,
04-research, 05-review-eval, 06-adr-generation.

## Style
Optimize for readability over cleverness. Workshop participants will
read this code and extend it. Explicit orchestration, typed data
contracts between agents, and comments where a design choice is
non-obvious.

## Naming
The product is Microsoft Foundry. Never write "Azure AI Foundry" in
code, comments, documentation, or identifiers.
