# Architecture

## The flow

![Architecture](architecture.png)

## What each agent does

**Standards agent.** Reads the submission and evaluates it against every requirement in the standards library. Each finding carries a status, the quoted evidence from the submission, and a citation naming the standard and section. Status is one of `conforms`, `partially_conforms`, `does_not_conform`, or `not_evidenced`.

The fourth status matters. A submission that simply does not address a requirement is different from one that violates it, and collapsing those two is the fastest way to lose a review board's trust.

**Research agent.** Takes the technology name from the conformance report and searches only customer-approved domains. It returns `TechnologyResearch`, where every external claim has a source title and URL. The domain allowlist is configuration, and every returned URL is validated against it. This stage runs by default and can be omitted with `--skip-research` while the allowlist is undecided or external research is not wanted.

**ADR author agent.** Takes the conformance report and optional research findings and produces the content of an Architecture Decision Record: title, decision, drivers, conditions, and consequences. The standards library is authoritative. Research may inform context and consequences but never overrides a standards finding.

**Reviewer agent.** Critiques the draft against the findings it came from, before any human sees it. It looks for two failure modes: claims in the draft that the findings do not support, and findings the draft left out. Each is reported with a severity and the indices of the findings it relates to.

The ADR validator treats `not_evidenced` as an evidence gap rather than a material non-conformance, and the reviewer runs the corrected ADR through that same validation before returning it.

## The data contracts

The handoff between agents is a typed schema, not prose. This is the design decision that makes everything else simpler.

| Stage | Produces | Consumed by |
|---|---|---|
| Standards agent | `standards_report` | Research agent, ADR author, reviewer |
| Research agent (optional) | `technology_research` | ADR author |
| ADR author | `draft_adr` | Reviewer |
| Reviewer | `review` with `reviewed_adr` | DOCX renderer |
| DOCX renderer | `.docx` file | SharePoint upload (optional) |

## Reference modules

**Intake (02)** extracts structured fields from an unstructured submission. It is a standalone reference module and is not invoked by either live orchestrator.

## Design decisions

**Why separate agents rather than one large prompt.** Each agent has one job and one output contract, which makes each independently testable and independently replaceable. It also makes the reviewer possible at all, since a critic needs something separate to critique.

**Why the renderer is code, not a model.** Document layout is deterministic work. Models are good at content and unreliable at format fidelity, so the agent produces structured content and Python renders it into the template.

**Why SharePoint upload is optional.** The renderer writes the local DOCX before checking the upload flag. A missing Graph permission therefore fails the publishing step without removing the local document.

**Why research can be skipped.** The source allowlist is a customer governance decision. Foundry manages the web-search tool without a separate project connection, and `--skip-research` keeps standards review, ADR authoring, and final review available while the allowlist is unresolved or external research is not wanted.

**Why standards remain authoritative.** External sources describe a technology, but they do not define an enterprise's obligations. Research adds context to the ADR; only the internal standards library determines conformance.

**Why agent versions are deleted by default.** Repeated runs would otherwise accumulate versions. Pass `--keep-agent` to leave them in place and inspect the run in the Microsoft Foundry portal.

## Observability

When the setup deployment provides an Application Insights connection string,
the agent modules configure Azure Monitor OpenTelemetry tracing. A default
Module 05 run creates an `Architecture review` trace with spans for `Standards
agent`, `Research agent`, `ADR author agent`, and `Reviewer agent`.
`--skip-research` omits the research span. The custom `traced_span` wrapper
opens named spans but does not add attributes or explicitly attach submission,
standards, research, or ADR content. `configure_tracing` passes the deployment's
connection string to `configure_azure_monitor`.

Tracing makes the review path and failures reconstructable without relying on
console output. That evidence matters when an architecture decision must be
auditable, while excluding review payloads reduces unnecessary exposure of
potentially sensitive information.

Application Insights uses public ingestion in this repository, so telemetry
leaves the virtual network even when `enablePrivateNetworking=true`.
Environments that block outbound access to Azure Monitor endpoints, or require
all telemetry to remain on the private network, need an Azure Monitor Private
Link Scope with private endpoints and private DNS. This repository does not
provision one.
