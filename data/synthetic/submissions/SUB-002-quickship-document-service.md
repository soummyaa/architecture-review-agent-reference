# Technology Review Submission

**Submission ID:** SUB-002
**Submitted by:** Claims Operations Engineering
**Date submitted:** 2026-03-11
**Requested decision date:** 2026-03-25

## Technology being proposed

QuickShip Document Service, an open-source document rendering and delivery
library, self-hosted.

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

Both virtual machines would run in the same facility. There is no secondary
site in the initial proposal.

## Integration approach

The claims platform would write render requests directly into a QuickShip
job table in a dedicated PostgreSQL database. QuickShip polls that table
every thirty seconds and picks up pending work.

Completed documents are written to a network file share, which the print
vendor's agent collects on a schedule.

There is no HTTP interface in the proposed deployment. The team notes that
QuickShip does ship an optional REST interface, but the polling approach
requires less change to the claims platform.

## Identity and access

QuickShip has no user-facing interface, so no end-user authentication is
required. Operational access is via SSH to the virtual machines using
individual engineer accounts.

The database connection uses a static username and password held in a
configuration file on each virtual machine, deployed by the existing
configuration management tooling.

## Security posture

QuickShip is Apache 2.0 licensed. The project has had two CVEs in the last
three years, both patched within a week of disclosure.

Documents on the file share are not encrypted at rest. The team notes the
share sits inside the facility's private network segment.

Transport between the claims platform and the QuickShip database is over
the internal network without TLS, consistent with how the current system
operates.

## Support model

Community support only. Claims Operations Engineering would own the
deployment, with two engineers designated as maintainers.

## Data export

Not applicable. QuickShip holds no durable data beyond the job queue.
