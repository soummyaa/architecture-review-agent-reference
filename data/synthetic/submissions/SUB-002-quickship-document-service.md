# Technology Review Submission

**Submission ID:** SUB-002
**Submitted by:** Claims Operations Engineering
**Date submitted:** 2026-03-11
**Requested decision date:** 2026-03-25

## Technology being proposed

QuickShip Document Service, an open-source document rendering and delivery
library, self-hosted.

QuickShip is an internally operated library, not a vendor-hosted
software-as-a-service product. The vendor-hosted SaaS conditions in
STD-001 Section 3 therefore do not apply.

The team requests approval for the design exactly as described below. It
has supplied no remediation plan, target date, compensating control, or
exception request for any failed requirement, and it does not propose to
change the design before production launch.

## Business driver

Correspondence generation currently runs through a vendor product that is
reaching end of support in eighteen months. QuickShip is a widely adopted
open-source alternative with an active community and would remove an
annual license cost.

## Proposed usage

QuickShip would render correspondence documents from templates and deliver
them to a print vendor and to the member portal. Expected volume is
approximately 60,000 documents per month, rising during annual enrollment.

Documents contain member names, addresses, and claim references. This is
Confidential-classified data.

## Hosting and deployment

The team proposes deploying QuickShip on two dedicated virtual machines in
the existing colocation facility, where the current correspondence system
already runs. This keeps the deployment adjacent to the print vendor's
dedicated network link, which is physically terminated at that facility.

This is self-managed infrastructure in a colocation facility and is not an
approved hosting model for a new workload. The team has not demonstrated
that the approved platform, container, SaaS, or infrastructure-as-a-service
models are unsuitable.

Both virtual machines would run in the same facility. There is no secondary
site in the proposal. They share one power zone and one network zone, so the
production service is effectively single-zone. There is no documented
exception and no recovery time objective.

The facility is in Ohio, and all document rendering, primary storage, and
temporary processing remain there. Nightly backups remain in the same Ohio
facility. The two designated maintainers are based in Ohio and are the only
people with support access; no vendor or overseas support organization can
access the workload or its Confidential-classified data.

## Integration approach

The claims platform would write document-status reconciliation records
directly into a QuickShip job table in a dedicated PostgreSQL database.
QuickShip polls that table every thirty seconds and picks up pending work.
This is an undocumented
direct database-to-database contract between systems owned by different
teams. No schema document, schema registry entry, data dictionary, or
versioned contract exists for either integration. Producers may change or
repurpose columns without a major version, and the QuickShip consumer fails
on unrecognized columns.

Completed documents are written to a network file share, which the print
vendor's agent collects on a schedule.

QuickShip's optional REST interface is enabled only for administrative
operations and render requests. It is published through the enterprise API gateway at the
versioned /v1 path, documented with OpenAPI 3.0, and authenticated through
the enterprise identity provider. There are no anonymous endpoints.
Breaking changes use a new major path version, and the prior major version
remains supported for 12 months. Every externally reachable API operation,
including every render request, uses this interface and satisfies these API
controls. The separate document-status reconciliation feed continues to use
the nonconforming direct database integration described above.

Failed database polls and file-share writes are retried every thirty seconds
without backoff and without a retry limit. Neither integration has a circuit
breaker.

Both integrations emit structured JSON operational logs to the enterprise
logging platform. A UUID correlation identifier created with each render
request is propagated to the job-table and file-share events. Logs contain
only timestamps, operation names, status codes, and correlation identifiers;
member names, addresses, claim references, document contents, and database
credentials are excluded.

## Identity and access

QuickShip has no user-facing interface, so no end-user authentication is
required. Operational access is via SSH to the virtual machines using
individual local engineer accounts with passwords. These accounts do not
federate to the enterprise identity provider, and MFA is not enforced.

Each engineer receives permissions directly on both virtual machines. There
are no roles, enterprise directory groups, or group-based joiner, mover, and
leaver controls.

Both designated maintainers have permanent root access. Access is standing,
not requested or time-bound, and there is no documented exception.

QuickShip and the virtual machines cannot export users and effective
permissions in a machine-readable format. Access records are maintained only
as separate local account files on each server, so quarterly access review
exports cannot be produced.

The database connection uses a static username and password held in a
configuration file on each virtual machine, deployed by the existing
configuration management tooling. It is a long-lived credential, is not
stored in the enterprise secrets manager, is not rotated, and is not a
cloud-issued workload identity.

## Security posture

QuickShip is Apache 2.0 licensed. The project has had two CVEs in the last
three years, both patched within a week of disclosure.

Documents on the file share are not encrypted at rest. The team notes the
share sits inside the facility's private network segment.

Transport between the claims platform and the QuickShip database is over
the internal network without TLS, consistent with how the current system
operates. Transport between QuickShip and the file share also uses unencrypted
SMB 1.0.

## Support model

Community support only. Claims Operations Engineering would own the
deployment, with two engineers designated as maintainers.

## Data export

QuickShip holds no durable business data beyond the job queue. This does not
change the separate inability to export users and effective permissions for
quarterly access reviews.
