# Technology Review Submission

**Submission ID:** SUB-003
**Submitted by:** Member Experience Engineering
**Date submitted:** 2026-03-18
**Requested decision date:** 2026-04-15

## Technology being proposed

Member Notification Service, a new internally built service using the
enterprise cloud provider's managed application platform and managed
event streaming service.

This is an internally built, containerized workload, not a vendor-hosted
software-as-a-service product. The vendor-hosted SaaS conditions in
STD-001 Section 3 therefore do not apply.

## Business driver

Member-facing notifications are currently generated inside three separate
applications, each with its own template logic and delivery scheduling.
Members receive duplicate messages, and there is no single place to apply
communication preferences or quiet hours. Consolidating notification
generation into one service removes the duplication and gives a single
enforcement point for member preferences.

## Proposed usage

The service would generate and deliver email and SMS notifications for
claims status changes, benefit updates, and appointment reminders.
Expected volume is approximately 1.2 million notifications per month.

Notification payloads include member identifiers and claim references.
This is Confidential-classified data. Message bodies are rendered from
templates at delivery time and are not retained after delivery
confirmation.

## Hosting and deployment

The service runs on the enterprise managed container platform, deployed to
the primary cloud provider's us-east and us-central regions. Both regions
are within the continental United States. The managed container platform is
the approved hosting model selected for this new workload; it does not use
self-managed infrastructure or infrastructure-as-a-service.

Production runs across three availability zones in each region, with
automated failover between regions. No data is stored or processed outside
the continental United States, including backups and the disaster recovery
replica in us-central. The cloud provider contract guarantees regional
pinning for storage, processing, backups, disaster recovery replicas, and
support access. This deployment therefore always uses six production
availability zones in total and never operates as a single-zone deployment.

## Integration approach

Source applications publish claim and benefit events to the enterprise
event platform. The notification service subscribes to the relevant event
types and generates notifications from those events. There is no direct
coupling between the notification service and the source applications'
databases. These event subscriptions, the preference API, and the outbound
email and SMS APIs are the complete set of service integration points; none
bypasses the enterprise event platform or API gateway with a point-to-point
or database-to-database connection.

The service exposes a REST API for preference management, published
through the enterprise API gateway, documented with an OpenAPI 3.1
specification and versioned in the path as /v1. Breaking changes use a new
major version, with the prior version supported for at least six months.
Event schemas are registered in the enterprise schema registry, consumers
are built to ignore unrecognized fields, and producers do not remove or
repurpose fields within a major version. The outbound email and SMS API
payloads also use documented, version-pinned JSON schemas supplied by each
vendor. Every API call requires authentication; there are no anonymous
endpoints, including health checks.

All integration consumers, including the enterprise event subscription and
outbound email and SMS vendor API calls, use retry with exponential backoff
and a circuit breaker that opens after five consecutive failures. Outbound
vendor API calls use TLS 1.3. Each integration point emits structured logs
to the enterprise logging platform and propagates the originating event's
correlation identifier across every service boundary. Integration logs
exclude member identifiers, claim references, and message body content.

## Identity and access

The preference management API authenticates end users through the
enterprise identity provider using OpenID Connect, with MFA enforced at
the identity provider. This applies to every human-accessible endpoint.
There is no local account store, break-glass account, or authentication path
that bypasses enterprise identity provider MFA.

Service-to-service authentication between cloud-hosted components uses
OpenID Connect 1.0 workload identity federation issued by the cloud
platform. Each workload exchanges its signed identity assertion for an
OAuth 2.0 access token with a 60-minute lifetime. Tokens are held only in
memory, are never persisted, and are discarded at expiration; no static
credential is used between cloud-hosted components.

The email and SMS vendor APIs also support OpenID Connect 1.0 workload
identity federation and trust the cloud platform's workload identity issuer.
The notification service exchanges its signed workload identity assertion
directly for a vendor-scoped OAuth 2.0 access token with a 15-minute lifetime.
These tokens are retained only in memory until expiration. The service uses
no API keys, client secrets, shared secrets, or other long-lived credentials
for any service-to-service path, including the two outbound vendor APIs.

Authorization is role-based, with three roles mapped to enterprise
directory groups: member self-service, service desk read, and platform
administrator. Administrative access is requested through the privileged
access workflow and granted for a maximum of eight hours. There are no
permissions assigned directly to individual users and no standing
administrator assignments.

The service exposes an endpoint that returns all users and their effective
permissions in JSON for quarterly access review. The export includes the
user identifier, enterprise directory group, effective role, and privilege
expiration timestamp.

## Security posture

Data at rest uses customer-managed keys held in the enterprise key
management service, including event data, preference data, delivery history,
backups, and disaster recovery replicas. All transport uses TLS 1.3,
including REST API, event platform, and outbound vendor connections.

## Support model

Owned and operated by Member Experience Engineering, with an existing
on-call rotation and a documented runbook.

## Data export

Member preference data can be exported through the preference API in JSON.
Notification delivery history is retained for eighteen months and can be
exported as CSV.
