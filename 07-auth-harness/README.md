# Module 07: Authentication Harness

## Goal

Demonstrate Microsoft Entra ID sign-in at the entry point to the existing
architecture review chain. A signed-in participant can select a synthetic
submission, run the existing standards, research, ADR author, and reviewer
stages, and view the reviewed ADR with the participant's display name and
Microsoft Entra object ID recorded alongside the run.

This module is a teaching harness, not a production authentication
implementation. It demonstrates sign-in and identity capture at the entry point
only. The signed-in user's identity is not propagated to downstream data access,
including SharePoint document reads. Delegated downstream access is a roadmap
item.

The harness does not reimplement agent logic. It invokes the existing
`06-review-eval/run.py` entry point and displays its reviewed ADR result.

## Prerequisites

- Complete Module 00 and set `AZURE_RESOURCE_GROUP` to the resource group
  containing the `architecture-review-setup` deployment.
- Install the requirements for Module 06 and this module.
- Register a Microsoft Entra application as described below.
- Use only the synthetic submissions in `data/synthetic/submissions/`.

## Microsoft Entra app registration

1. In the Microsoft Entra admin center, open **App registrations** and select
   **New registration**.
2. Enter a name such as `Architecture Review Workshop Auth Harness`.
3. Select **Accounts in this organizational directory only**.
4. After registration, open **Authentication**, select **Add a platform**, and
   choose **Mobile and desktop applications**.
5. Add this loopback redirect URI exactly:

   `http://localhost:5000/auth/callback`

6. Under **Advanced settings**, set **Allow public client flows** to **Yes**.
   The harness uses authorization code flow with PKCE and does not use a client
   secret.
7. Open **API permissions** and add these delegated Microsoft Graph
   permissions:
   - `openid` - signs the user in and provides the stable object ID claim.
   - `profile` - provides the user's display name and basic profile claims.
   - `User.Read` - permits sign-in and reading the signed-in user's basic
     profile.

`openid`, `profile`, and `User.Read` do not require admin consent by their
default permission definitions; a user can consent for themselves when tenant
user-consent policy permits it. If the tenant disables or restricts user
consent, an administrator must grant tenant-wide consent before participants
can sign in. This module requires no application permissions and no permission
that inherently requires admin consent.

Copy the **Application (client) ID** and **Directory (tenant) ID** from the app
registration overview. These identifiers are configuration values, not
credentials. Do not create a client secret.

## Install

From the repository root:

```bash
python -m pip install -r 06-review-eval/requirements.txt
python -m pip install -r 07-auth-harness/requirements.txt
```

Each numbered module remains independently installable; this harness includes
the Module 06 runtime dependencies because it invokes that module's existing
entry point.

## Configure

Set the app registration identifiers and existing workshop resource group in
the shell:

```bash
export ENTRA_CLIENT_ID="<application-client-id>"
export ENTRA_TENANT_ID="<directory-tenant-id>"
export AZURE_RESOURCE_GROUP="<workshop-resource-group>"
```

Optionally override the defaults:

```bash
export AUTH_REDIRECT_URI="http://localhost:5000/auth/callback"
export AUTH_HOST="127.0.0.1"
export AUTH_PORT="5000"
```

Do not put credentials in code or `.env` files. The harness is a public client
and uses PKCE, so it has no client secret. It generates an ephemeral Flask
session key at startup; restarting the process signs users out.

## Run Standalone

From the repository root:

```bash
python 07-auth-harness/run.py
```

Open `http://localhost:5000`, sign in, select a synthetic submission, and run
the review. Research is enabled by default and uses the existing Module 06
configuration. Select **Skip research** when the Foundry web-search connection
or approved source allowlist is not configured.

The request blocks while the existing agent chain runs. This simple synchronous
behavior is intentional for the workshop and is not a production job-processing
design.

## Run records

For each completed review, the harness writes a JSON Lines record to
`07-auth-harness/output/auth-runs.jsonl` containing:

- UTC completion time
- signed-in user's Microsoft Entra object ID
- signed-in user's display name
- selected synthetic submission
- reviewed ADR result

The output directory is ignored by Git. The record demonstrates associating an
entry-point identity with a review run; it is not a production audit store.

## Authentication boundary

Microsoft Entra authenticates access to this web entry point. The existing agent
chain continues to use `DefaultAzureCredential` for Microsoft Foundry and other
Azure service access.

The harness does not exchange, forward, or use the signed-in user's token for
downstream calls. In particular, the signed-in user's identity is not propagated
to SharePoint document reads. Implementing delegated downstream data access,
token exchange, and production authorization policy remains a roadmap item.

## Test

```bash
PYTHONPATH=07-auth-harness python -m unittest discover \
  -s 07-auth-harness \
  -p "test_*.py"
```

Tests mock MSAL and the Module 06 process; they do not require an Entra tenant or
run agents.