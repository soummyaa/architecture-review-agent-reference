# Technology Review Submission

**Submission ID:** SUB-005
**Submitted by:** Agent Platform Engineering
**Date submitted:** 2026-09-06
**Requested decision date:** 2026-10-02

## Technology being proposed

A token-exchange interceptor deployed with the enterprise API gateway in a
second cloud. The interceptor would let internally built agents running in the
primary cloud call tools behind that gateway without placing a vendor SDK in
every agent workload.

The interceptor would be an internally managed platform-as-a-service function,
not vendor-hosted software as a service or self-managed infrastructure. The
vendor-hosted SaaS conditions in STD-001 Section 3 therefore do not apply. The
gateway service contract and the second cloud's support model still require
review for residency, subprocessors, and administrative access.

## Business driver

Several agent teams need access to policy lookup, provider directory, and
document-status tools operated in a second cloud. Today each team is proposing
its own authentication adapter. A shared exchange point would give the
enterprise one place to validate identity, map claims to tool scopes, enforce
rate limits, and record cross-cloud access decisions.

## Proposed usage

An agent would obtain a short-lived workload identity token from the primary
cloud and send it with a synchronous tool request to the second-cloud gateway.
The interceptor would validate the token and exchange it for a short-lived
credential accepted by the gateway. It would then forward the request only to
the tool scopes authorized for that workload.

Requests and responses can contain member identifiers, benefit details, and
provider information and are therefore Confidential-classified. The boundary
crossing consists of the workload token, correlation identifier, tool name,
request parameters, and tool response. The design does not send agent prompts,
conversation history, or model traces unless a tool parameter explicitly
contains that information.

An open question is whether the second cloud's token service can federate
directly with the primary cloud's workload identity issuer for every required
gateway scope. The preferred design is conditional on that capability. The
team has not yet demonstrated claim mapping for delegated tool calls in which
the agent acts in the context of a human user.

## Hosting and deployment

Agents remain on the enterprise managed container platform in the primary
cloud. The interceptor runs as a platform-as-a-service function integrated
with the enterprise-managed API gateway in the second cloud. Both workloads
would run only in continental United States regions; request processing,
temporary platform storage, logs, backups, and disaster recovery replicas are
intended to remain in those regions.

Production agent workloads already span three availability zones. The gateway
spans at least two availability zones, and the interceptor would be configured
with a minimum of two instances. The team has not confirmed whether a zonal
gateway failure keeps interceptor execution in-zone or causes the platform to
process a retry in another region. A failover test and a documented recovery
time objective are required before production use.

The second-cloud contract must still confirm regional pinning for processing,
backups, disaster recovery, diagnostic data, and support access. Until that
commitment is verified, the design cannot carry Confidential data. No
infrastructure-as-a-service or colocation deployment is proposed, and no
STD-001 exception has been requested.

## Integration approach

Tool calls use synchronous REST over HTTPS through the enterprise API gateway.
The gateway API would have an OpenAPI 3.1 specification and a versioned `/v1`
path. Breaking changes would receive a new major version, with the prior major
version supported for at least six months. There are no direct database
connections or routes that bypass the gateway.

Each tool request and response has a documented JSON schema. Consumers ignore
unknown fields, and producers do not remove or repurpose fields within a major
version. The gateway and interceptor require authentication on every tool
endpoint; only a payload-free health endpoint can be anonymous.

All cross-cloud traffic uses TLS 1.3. Gateway configuration, interceptor state,
and audit records use platform-managed encryption at rest. The interceptor is
intended to be stateless and must not persist tokens or tool payloads. The team
still needs evidence that gateway diagnostics and vendor support tooling do not
capture Confidential request or response bodies by default.

The agent client retries connection and service-unavailable failures at most
three times with exponential backoff and jitter. A circuit breaker opens after
five consecutive failures. When the second cloud is unreachable, tool calls
fail closed with a dependency-unavailable response; they are not redirected to
an unapproved endpoint and requests are not queued for later replay. Agent
workflows must either pause for operator retry or continue without the tool,
and the product teams have not yet classified which workflows can safely
continue.

Every boundary crossing emits structured logs to the enterprise logging
platform with the same correlation identifier in the agent, interceptor,
gateway, and tool. The interceptor records issuer, audience, workload subject,
requested scope, mapped scope, decision, token expiration, and failure reason,
but never records token values or Confidential payload fields. Whether the
workload subject must be pseudonymized in the central audit store, and how long
that mapping must remain reversible for investigations, remain open decisions.

## Identity and access

Identity is asserted by the primary cloud's workload identity issuer. The
interceptor validates the assertion's signature against pinned issuer metadata
and checks issuer, audience, subject, expiration, and allowed workload claims
before contacting the second-cloud token service. The gateway then validates
the exchanged token's signature, audience, expiration, and scope before
forwarding a request. Tokens expire after fifteen minutes and are held in
memory only.

The target design has no API key, client secret, shared secret, or other
long-lived credential at the agent, interceptor, gateway, or tool. The team
must verify that the second-cloud token service supports workload identity
federation rather than requiring a confidential-client secret. If it requires
a secret, that path does not meet the preferred design and would require
Security Architecture review, storage in the enterprise secrets manager, and
rotation at least every ninety days; it would not be silently adopted.

Human administrators authenticate to both cloud consoles through federation
with the enterprise identity provider using OpenID Connect, with MFA enforced
by that provider. There are no local human account stores or MFA bypasses. Each
cloud retains one documented provider-managed break-glass process, and its use
is alerted and reviewed after every invocation.

Authorization is role-based. Agent caller, gateway operator, tool owner, and
audit reader roles map to enterprise directory groups, with no permissions
assigned directly to individuals. Tool scopes would be mapped from an
allowlist of workload subjects and claims. The exact mapping for human-delegated
requests, including whether user identity or only the agent identity reaches
the tool, is not yet decided and requires a threat-model review.

Administrative roles are requested through the enterprise privileged access
workflow and expire after a maximum of eight hours; there are no standing
administrator assignments. Both cloud platforms and the gateway must export
users, workload identities, group mappings, tool scopes, and effective
permissions as JSON for quarterly access reviews. The team has validated the
individual exports but has not yet demonstrated that they can be reconciled
into one end-to-end effective-permissions report.

## Security posture

Gateway policy permits only registered agent workload subjects, approved tool
scopes, and expected token audiences. Exchange failures fail closed and create
an audit event. Platform threat detection monitors repeated failed exchanges,
scope escalation attempts, replay indicators, and calls from an unexpected
region. Logs exclude tokens, member identifiers, benefit details, provider
details, request parameters, and tool responses.

The alternative considered is a vendor SDK sidecar deployed beside each agent.
It would validate local workload identity and perform the exchange before the
request leaves the primary cloud. The team did not select it because SDK
versioning, policy mapping, audit behavior, and possible credential caching
would be distributed across every agent deployment. It also remains unclear
whether the sidecar can prove that tokens and tool payloads are never written
to local diagnostic storage. The sidecar may be reconsidered if direct
federation at the gateway is unavailable, but it would require a separate
review rather than becoming an automatic fallback.

## Support model

Agent Platform Engineering owns the interceptor, identity mapping, client
library, and on-call response. The second-cloud platform team owns the gateway,
network policy, platform encryption, and regional failover. Tool-owning teams
own authorization scopes and decide whether their workflows stop or degrade
when the second cloud is unavailable.

Runbooks would cover issuer metadata rollover, rejected exchanges, suspected
token replay, scope rollback, gateway outage, audit reconciliation, and
emergency disablement of a workload subject. Ownership during an incident that
affects both cloud providers still needs a single incident commander and an
agreed escalation path.

## Data export

Gateway configuration, scope mappings, effective-permission reports, and audit
events can be exported without vendor assistance as JSON or CSV. Tool payloads
remain in their systems of record under existing retention policies and are
not retained by the interceptor. The team must verify that platform diagnostic
records can be completely exported and deleted at the end of their retention
period before production approval.