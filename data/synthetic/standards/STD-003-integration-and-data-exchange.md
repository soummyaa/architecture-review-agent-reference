# STD-003: Integration and Data Exchange

**Status:** Active
**Owner:** Enterprise Architecture
**Last reviewed:** 2026-02-20

## Purpose

This standard governs how systems exchange data with one another, and what
integration patterns are approved for new technology.

## Requirements

### 1. Approved integration patterns

New integrations must use one of:

1. Synchronous REST over HTTPS, with an OpenAPI 3.x specification
2. Asynchronous messaging via the enterprise event platform
3. Scheduled bulk file transfer via the managed transfer service, for
   volumes unsuitable to 1 or 2

Direct database-to-database connections between systems owned by different
teams are not approved. Point-to-point integrations that bypass the API
gateway are not approved for systems handling Internal data or above.

### 2. API requirements

Externally reachable APIs must be published through the enterprise API
gateway. APIs must be versioned in the path, and breaking changes require a
new major version with the prior version supported for at least six months.

All APIs must enforce authentication per STD-002. Anonymous endpoints are
limited to health checks and public metadata.

### 3. Transport and encryption

All data in transit must use TLS 1.2 or higher. Data at rest must be
encrypted using platform-managed or customer-managed keys. Systems that
cannot encrypt at rest are limited to Public-classified data.

### 4. Data contracts

Every integration must have a documented schema. Consumers must tolerate
the addition of unknown fields. Producers must not remove or repurpose
fields within a major version.

### 5. Rate limiting and resilience

Consumers must implement retry with exponential backoff and a circuit
breaker. Integrations that retry indefinitely without backoff do not meet
this standard.

### 6. Logging

Integration points must emit structured logs to the enterprise logging
platform, including a correlation identifier propagated across service
boundaries. Logs must not contain payload data classified Internal or
above.

## Exceptions

Exceptions to Section 1 require documented justification of why an
approved pattern is unsuitable, and a remediation plan with a target date.
