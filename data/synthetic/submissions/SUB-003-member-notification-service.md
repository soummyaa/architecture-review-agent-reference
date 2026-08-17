# Technology Review Submission

**Submission ID:** SUB-003
**Submitted by:** Member Experience Engineering
**Date submitted:** 2026-03-18
**Requested decision date:** 2026-04-15

## Technology being proposed

Member Notification Service, a new internally built service using the
enterprise cloud provider's managed application platform and managed
event streaming service.

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
are within the continental United States.

Production runs across three availability zones in each region, with
automated failover between regions. No data is stored or processed outside
the continental United States, including backups and the disaster recovery
replica in us-central.

## Integration approach

Source applications publish claim and benefit events to the enterprise
event platform. The notification service subscribes to the relevant event
types and generates notifications from those events. There is no direct
coupling between the notification service and the source applications'
databases.

The service exposes a REST API for preference management, published
through the enterprise API gateway, documented with an OpenAPI 3.1
specification and versioned in the path as /v1. Event schemas are
registered in the enterprise schema registry, and consumers are built to
ignore unrecognized fields.

Outbound delivery to the email and SMS vendors uses their REST APIs over
TLS 1.3, with retry using exponential backoff and a circuit breaker that
opens after five consecutive failures.

## Identity and access

The preference management API authenticates end users through the
enterprise identity provider using OpenID Connect, with MFA enforced at
the identity provider. There is no local account store.

Service-to-service authentication uses workload identity issued by the
cloud platform. The vendor API credentials that cannot use workload
identity are held in the enterprise secrets manager with ninety-day
rotation configured.

Authorization is role-based, with three roles mapped to enterprise
directory groups: member self-service, service desk read, and platform
administrator. Administrative access is requested through the privileged
access workflow and granted for a maximum of eight hours.

The service exposes an endpoint that returns all users and their effective
permissions in JSON for quarterly access review.

## Security posture

Data at rest uses customer-managed keys held in the enterprise key
management service. All transport uses TLS 1.3. Structured logs are
emitted to the enterprise logging platform with a correlation identifier
propagated from the originating event, and log records exclude
notification payload content.

## Support model

Owned and operated by Member Experience Engineering, with an existing
on-call rotation and a documented runbook.

## Data export

Member preference data can be exported through the preference API in JSON.
Notification delivery history is retained for eighteen months and can be
exported as CSV.
