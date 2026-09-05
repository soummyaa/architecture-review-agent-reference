# Technology Review Submission

**Submission ID:** SUB-001
**Submitted by:** Data Platform Team
**Date submitted:** 2026-03-04
**Requested decision date:** 2026-04-01

## Technology being proposed

Northwind Analytics Cloud, a vendor-hosted analytics and dashboarding
platform.

## Business driver

The Data Platform Team currently maintains three separate reporting tools
with overlapping capability. Consolidating onto a single platform would
reduce license spend and give business users self-service dashboard
creation without engineering involvement. Two business units have
independently asked for this capability in the last two quarters.

## Proposed usage

Business analysts would connect Northwind to the enterprise data warehouse
and build dashboards against curated datasets. Approximately 400 named
users in year one, growing to 900 if adoption goes well.

Data consumed would include operational metrics, financial summaries, and
customer counts classified as Internal. No individual customer records or
Confidential-classified data are in scope for the initial rollout.

## Hosting and deployment

Northwind is delivered as SaaS from the vendor's own cloud tenancy. The
vendor operates from three regions globally and assigns customers to a
region at onboarding. Our account would be contractually pinned to the
vendor's Virginia and Ohio regions, both within the continental United
States.

The contract states that all enterprise data is stored and processed only
in Virginia and Ohio. This restriction includes primary storage, temporary
processing, backups, disaster recovery replicas, telemetry containing
enterprise data, and support access. Support personnel outside the
continental United States cannot access the tenant or its data.

Production is active across three availability zones in Virginia and three
availability zones in Ohio. Automated regional failover keeps the service
available if one zone or either region fails.

## Integration approach

The enterprise data platform publishes the curated datasets hourly as
Parquet 2.6 files through the managed transfer service. Northwind consumes
those files from a dedicated managed-transfer endpoint; it has no direct
connection to the data warehouse or any application database. The managed
transfer service is used because each hourly batch can reach 80 GB, making
synchronous REST unsuitable.

The Northwind transfer connector authenticates with a dedicated service
account and long-lived password stored in Northwind's credential vault.
This does not conform to the workload identity requirement. Northwind does
not currently support cloud-issued workload identity for this connector.
The vendor has committed to release workload identity federation in version
2026.3 by 2026-09-30; the Data Platform Team will migrate the connector and
remove the service account within 30 days of that release. The proposed
2026-06-01 production launch will therefore use the long-lived password and
will remain nonconforming until that migration is complete; planned future
remediation is not implemented in the submitted design.

Northwind also offers a REST API for administrative operations, documented
with an OpenAPI 3.0 specification. Enterprise administrative clients reach
it only through the enterprise API gateway at the versioned /v1 path and
authenticate with SAML-derived OAuth 2.0 tokens. There are no anonymous
operations. Breaking changes use a new major path version, and the vendor
supports the prior major version for 12 months.

The Parquet schemas are versioned in the enterprise schema registry. The
Northwind connector ignores unrecognized fields, and the data platform does
not remove or repurpose fields within a major schema version. Administrative
API consumers follow the same forward-compatible rules in the OpenAPI 3.0
contract.

For both the managed transfer and administrative API integrations,
Northwind retries at most five times with exponential backoff starting at
two seconds and capped at 32 seconds. A circuit breaker opens for 60 seconds
after five consecutive failures.

Both integration points emit structured JSON logs to the enterprise logging
platform and propagate a UUID correlation identifier from export through
import. Logs contain dataset name, row count, status, duration, and
correlation identifier, but exclude financial values, customer counts, file
contents, credentials, and all other Internal-classified payload data.

## Identity and access

Northwind supports SAML 2.0 federation, which we would configure against
the enterprise identity provider. MFA is enforced by the enterprise identity
provider for every human login, and Northwind has no local user accounts
other than the two administrator accounts described below. Roles are
defined inside Northwind and mapped only to enterprise directory groups
through SAML group assertions; permissions cannot be assigned directly to
individual users.

Administrative access requires a Northwind-local administrator account
that cannot be federated or made time-bound. The proposed design has two
permanently assigned local administrator accounts for redundancy, and no
exception has been approved. This does not conform to the privileged access
requirement. The vendor plans federated just-in-time administration in
version 2026.3 by 2026-09-30; the Data Platform Team will integrate it with
the enterprise privileged access workflow and retire both standing accounts
within 30 days of that release. The proposed 2026-06-01 production launch
will use both standing accounts and will remain nonconforming until that
work is complete; planned future remediation is not implemented in the
submitted design.

Northwind's access-review API exports every user, enterprise directory
group, assigned role, effective permission, account status, and last login
as UTF-8 JSON. Identity Governance will retrieve this export quarterly and
retain it for 18 months.

## Security posture

The vendor holds a SOC 2 Type II report, most recently issued in
January 2026, and contractually refreshes the report every 12 months. Data
is encrypted at rest with AES-256 vendor-managed keys.
Customer-managed keys are on the vendor roadmap but not currently
available.

TLS 1.2 is enforced on all connections.

The vendor contract lists every subprocessor by legal name and processing
location. The vendor must give 60 days' written notice before adding or
replacing a subprocessor.

## Commercials

Three-year term, annual subscription based on named users. Estimated
first-year cost is in line with the combined spend on the three tools it
would replace.

## Data export

Without vendor assistance, the administrative API exports all enterprise
data held by Northwind: dashboard definitions, dataset definitions, role
mappings, access-review records, and audit history as UTF-8 JSON, plus all
curated dataset rows as Parquet 2.6. Rendered visualization images are not
enterprise source data and are regenerated from the exported dashboard
definitions.
