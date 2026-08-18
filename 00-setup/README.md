# Module 00: Setup

## Goal

Provision the shared Microsoft Foundry project, model deployment, Key Vault,
and storage account. Validate that the workshop identity can reach the project,
invoke the model, and resolve the workshop SharePoint site through Microsoft
Graph.

## Prerequisites

- An Azure subscription and permission to create resources and role assignments.
- Tenant-admin-approved Microsoft Graph access to the workshop SharePoint site.
- A model and model version available in the target Azure region. The template
	defaults to `gpt-4o-mini` version `2024-07-18`.

The devcontainer installs Azure CLI, Bicep, Python, and the packages in
`requirements.txt` globally. Do not create or activate a virtual environment.

## Networking modes

Private networking is enabled by default for regulated environments. In this
mode the template creates a virtual network, a dedicated private endpoint
subnet, private DNS zones, and private endpoints for Microsoft Foundry, Key
Vault, and storage. Public network access to those services is disabled.
Private mode requires network connectivity into the virtual network: either
peering from a corporate network, a VPN, or Azure Bastion. The optional jump
box is reached through one of those paths. The validator and all agent modules
must be run from inside that network when private mode is enabled.

For quick local development, pass `enablePrivateNetworking=false`. This keeps
the existing public service endpoints and does not create the private network.

To deploy the optional Linux jump box in private mode, provide an SSH public
key and set `deployJumpBox=true`. The VM has no public IP. Connect through Azure
Bastion or an existing network path such as corporate peering or a VPN:

```bash
az deployment group create \
	--name architecture-review-setup \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--template-file 00-setup/main.bicep \
	--parameters \
		principalId="$CALLER_OBJECT_ID" \
		sharepointHostname="<sharepoint-hostname>" \
		sharepointSitePath="/sites/<workshop-site>" \
		sshPublicKey="$(cat ~/.ssh/id_ed25519.pub)" \
		deployJumpBox=true
```

The deployment outputs the virtual network and private endpoint subnet
resource IDs for later peering or jump-box integration. SSH uses the supplied
key and no password.

## Run Standalone

Sign in, create the workshop resource group, and deploy the resources. Replace
the SharePoint values with the synthetic workshop site provisioned by your
administrator.

```bash
az login
az group create \
	--name "$AZURE_RESOURCE_GROUP" \
	--location eastus

CALLER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)

az deployment group create \
	--name architecture-review-setup \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--template-file 00-setup/main.bicep \
	--parameters \
		principalId="$CALLER_OBJECT_ID" \
		sharepointHostname="<sharepoint-hostname>" \
		sharepointSitePath="/sites/<workshop-site>"
```

If the default model version is unavailable in the selected region, also pass
`modelName`, `modelVersion`, and optionally `modelCapacity` to the deployment.

Run the validator directly. It reads the deployment outputs using
`AZURE_RESOURCE_GROUP`, which the devcontainer sets to
`rg-architecture-review-workshop`.

```bash
python 00-setup/validate.py
```

The validator prints one `[PASS]` or `[FAIL]` line per dependency, followed by
a summary. It exits with status `1` if any check fails.

## What you should understand by the end

How managed identity, role assignments, deployment outputs, and Microsoft
Graph permissions combine to provide the shared foundation for later modules.
