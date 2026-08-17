# STD-002: Identity and Access Management

**Status:** Active
**Owner:** Enterprise Architecture
**Last reviewed:** 2025-11-03

## Purpose

This standard defines how users and workloads authenticate, and how access
is granted and reviewed, for any system introduced into the portfolio.

## Requirements

### 1. Human authentication

All systems handling Internal-classified data or above must federate to
the enterprise identity provider. Local account stores are not permitted
except for a documented break-glass account.

Federation must use SAML 2.0 or OpenID Connect. Proprietary or
password-synchronization-based integrations are not approved.

Multi-factor authentication is enforced at the identity provider. Systems
must not bypass or independently satisfy the MFA requirement.

### 2. Workload authentication

Service-to-service authentication must use workload identity issued by the
cloud platform. Long-lived static credentials, including API keys and
shared secrets, are not approved for new systems.

Where a third-party system cannot support workload identity, credentials
must be stored in the enterprise secrets manager, rotated at least every
ninety days, and never committed to source control or configuration files.

### 3. Authorization model

Access must be role-based. Systems that grant permissions only at an
individual-user level, with no role or group abstraction, do not meet this
standard.

Roles must map to groups managed in the enterprise directory, so that
joiner, mover, and leaver processes apply automatically.

### 4. Privileged access

Administrative access must be time-bound and requested, not standing.
Systems that require permanently assigned administrator accounts require a
documented exception.

### 5. Access review

All systems must support an export of users and their effective
permissions, in a machine-readable format, to support quarterly access
reviews.

## Exceptions

Section 1 and Section 2 exceptions require Security Architecture approval
in addition to Enterprise Architecture review.
