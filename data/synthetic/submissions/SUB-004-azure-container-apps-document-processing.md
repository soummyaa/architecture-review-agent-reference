# Technology Review Submission

**Submission ID:** SUB-004
**Submitted by:** Benefits Platform Engineering
**Date submitted:** 2026-03-25
**Requested decision date:** 2026-04-22

## Technology being proposed

Azure Container Apps

## Business driver

Benefits documents currently pass through several manual queues before their
contents are available to service representatives. Processing delays increase
during annual enrollment and require temporary staff to monitor failed jobs.
A managed container platform would let the team automate document validation,
classification, and routing without operating Kubernetes control-plane
infrastructure.

## Proposed usage

The platform would host an internal REST API that accepts document-processing
requests and a background worker that retrieves documents from enterprise
object storage. Expected volume is approximately 180,000 documents per month,
with short peaks of 40 requests per second during annual enrollment.

Documents include member identifiers, plan selections, and supporting benefit
information. This is Confidential-classified data. The containers retain no
documents on local storage after processing completes.

## Hosting and deployment

The team proposes one Azure Container Apps environment in East US 2 and a
second in Central US for disaster recovery. Both environments and all backing
storage would remain within the continental United States. Backups and
disaster recovery replicas would also remain in Central US.

Production would use workload profiles with zone redundancy enabled across
three availability zones. Traffic would normally route to East US 2, with the
enterprise traffic manager directing requests to Central US during a regional
failure. Minimum replica counts would keep two API replicas and two worker
replicas running in each active environment.

## Integration approach

Source applications would submit processing requests through a REST API
published behind the enterprise API gateway. The API would be documented with
OpenAPI 3.1 and versioned in the path as /v1.

Accepted requests would publish messages to the enterprise managed messaging
service. Worker replicas would consume those messages and retrieve documents
from enterprise object storage using private endpoints. Message schemas would
be registered in the enterprise schema registry, and consumers would ignore
unrecognized fields for backward compatibility.

Calls to the document-classification service would use HTTPS with exponential
backoff, a maximum of three retries, and a circuit breaker. Failed messages
would move to a dead-letter queue for operational review.

## Identity and access

Employees would authenticate to the API through the enterprise identity
provider using OpenID Connect, with MFA enforced by the identity provider.
There would be no local user account store.

Each container app would use a dedicated managed identity for access to object
storage, messaging, secrets, and the classification service. No static service
credentials would be stored in container images or application settings.

Authorization would use application roles mapped to enterprise directory
groups. Administrative access would be granted through the privileged access
workflow for a maximum of eight hours. Quarterly access reviews would use an
export of role assignments and effective permissions from the cloud platform
and application API.

## Security posture

Container images would be built by the enterprise pipeline, scanned before
release, and pulled from the enterprise container registry over a private
endpoint. Images would run as a non-root user in read-only containers.

Application secrets would be references to the enterprise key management
service. Data in object storage and messaging would use customer-managed keys.
All application traffic would use TLS 1.2 or later. Structured logs and metrics
would flow to the enterprise monitoring platform with correlation identifiers,
while document contents and member identifiers would be excluded from logs.

## Support model

Benefits Platform Engineering would own the API and worker service with an
existing on-call rotation. The Cloud Platform Team would own the landing zone,
network controls, policy assignments, and shared monitoring configuration.
Runbooks would cover failed-message replay, regional failover, and container
image rollback.

## Data export

Processing status and audit history could be exported through the API as JSON
or CSV. Original documents would remain in enterprise object storage under the
existing records-retention policy and could be retrieved without platform
vendor assistance.
