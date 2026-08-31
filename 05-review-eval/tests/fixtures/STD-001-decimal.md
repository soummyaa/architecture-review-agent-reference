# STD-001: Cloud Hosting and Data Residency

**Status:** Active
**Owner:** Enterprise Architecture
**Last reviewed:** 2026-01-15

## Purpose

This standard governs where workloads and data may be hosted, and which
hosting models are approved for new technology introduced into the
enterprise portfolio.

## Requirements

1. Approved hosting models

New workloads must use one of the following, in order of preference:

1. Platform-as-a-service on the enterprise's primary cloud provider
2. Containerized workloads on the managed container platform
3. Vendor-hosted SaaS, where the vendor meets the conditions in Section 3
4. Infrastructure-as-a-service, only where 1 through 3 are demonstrably
   unsuitable

Self-managed infrastructure in a colocation facility is not approved for
new workloads.

2. Data residency

All data classified Internal or above must be stored and processed within
the continental United States. Vendors must be able to contractually
guarantee regional pinning, including for backups, disaster recovery
replicas, and support access.

Systems that cannot guarantee residency are limited to Public-classified
data only.

3. Vendor-hosted SaaS conditions

A vendor-hosted SaaS product may be approved where all of the following
hold:

- The vendor holds a current SOC 2 Type II report, refreshed annually
- Data residency per Section 2 is contractually committed
- The vendor supports SSO via SAML 2.0 or OIDC (see STD-002)
- A documented data export path exists, so the enterprise can retrieve its
  own data in a non-proprietary format without vendor assistance
- Subprocessors are disclosed, with notice required before changes

4. Region and availability

Production workloads must be deployed across at least two availability
zones. Single-zone deployments require a documented exception with a
stated recovery time objective.

## Exceptions

Exceptions require Enterprise Architecture review and are granted for a
maximum of twelve months, after which the exception must be renewed or the
workload remediated.
