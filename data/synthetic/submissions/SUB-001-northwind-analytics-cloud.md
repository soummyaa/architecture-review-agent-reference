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
customer counts. No individual customer records are in scope for the
initial rollout.

## Hosting and deployment

Northwind is delivered as SaaS from the vendor's own cloud tenancy. The
vendor operates from three regions globally and assigns customers to a
region at onboarding. Our account would be provisioned in their North
America region.

The vendor has confirmed that primary data storage stays in North America.
Backups are replicated to a secondary region for disaster recovery, and
the vendor's support organization operates on a follow-the-sun model.

## Integration approach

Northwind connects to the data warehouse using a native connector over a
JDBC connection. The connector authenticates with a service account and
password stored in Northwind's credential vault. The vendor also offers a
REST API for administrative operations, documented with OpenAPI 3.0.

Data refresh is scheduled hourly. There is no event-driven option.

## Identity and access

Northwind supports SAML 2.0 federation, which we would configure against
the enterprise identity provider. Roles are defined inside Northwind and
can be mapped to SAML group assertions.

Administrative access requires a Northwind-local administrator account
that cannot be federated. The vendor recommends two such accounts for
redundancy.

## Security posture

The vendor holds a SOC 2 Type II report, most recently issued in
January 2026. Data is encrypted at rest with vendor-managed keys.
Customer-managed keys are on the vendor roadmap but not currently
available.

TLS 1.2 is enforced on all connections.

## Commercials

Three-year term, annual subscription based on named users. Estimated
first-year cost is in line with the combined spend on the three tools it
would replace.

## Data export

Dashboards and underlying dataset definitions can be exported via the
administrative API in JSON. Rendered visualizations cannot be exported in
a portable format.
