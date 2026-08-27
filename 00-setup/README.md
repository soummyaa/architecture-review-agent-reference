# Module 00: Setup

## Goal

Provision the shared Microsoft Foundry project, model deployment, Log Analytics
workspace, and workspace-based Application Insights resource. Validate that the
workshop identity can reach the project, invoke the model, and resolve the
workshop SharePoint site through Microsoft Graph.

## Prerequisites

- An Azure subscription and permission to create resources and role assignments.
- Tenant-admin-approved Microsoft Graph access to the workshop SharePoint site.
- A model and model version available in the target Azure region. The template
	defaults to `gpt-5.4-mini` version `2026-03-17`. In `centralus`, this model
	offers `GlobalStandard`, `DataZoneStandard`, `DataZoneProvisionedManaged`,
	`GlobalProvisionedManaged`, `GlobalBatch`, and `DataZoneBatch` deployment SKUs.

The devcontainer installs Azure CLI, Bicep, Python, and the packages in
`requirements.txt` globally. Do not create or activate a virtual environment.

## Private workstation setup

The machine used from inside the private network, including a jump box, needs:

- Azure CLI. For command-line Bastion connections, install the `bastion` and
	`ssh` Azure CLI extensions.
- Python 3.11 or later and the matching `python3-venv` package. Debian and
	Ubuntu block system-wide pip installs into their managed Python environment.
- Git.
- A virtual environment so workshop dependencies remain isolated from the
	operating system's managed Python packages.
- The requirements from every numbered module, not only `00-setup`.

On a fresh Ubuntu machine, clone this repository and run the setup script from
any directory. It is safe to re-run and installs all module requirements in
one pip command:

```bash
./00-setup/setup-workstation.sh
source .venv/bin/activate
```

The script uses `sudo` to install operating-system packages and Azure CLI. It
creates `.venv` at the repository root.

## Networking modes

Private networking is enabled by default for regulated environments. Public
network access to Microsoft Foundry is disabled in both private networking
modes. The validator and all agent modules must be run from a network that can
reach the private endpoint.

### Greenfield

By default, the template creates a virtual network, dedicated private endpoint
subnet, private DNS zones and links, and a private endpoint for Microsoft
Foundry. Deploy without the existing-network parameters:

```bash
az deployment group create \
	--name architecture-review-setup \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--template-file 00-setup/main.bicep \
	--parameters \
		principalId="$CALLER_OBJECT_ID" \
		sharepointHostname="<sharepoint-hostname>" \
		sharepointSitePath="/sites/<workshop-site>"
```

To deploy the optional Linux jump box and Azure Bastion, provide an SSH public
key and set `deployJumpBox=true`. The template creates the required
`AzureBastionSubnet` and a Bastion host. The Bastion host uses the Standard SKU
with native client support enabled; Basic supports portal connections only.
The VM has no public IP:

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

Validate private mode by connecting to the jump box with the Bastion native
client, then running the validator where the private endpoints resolve:

```bash
az network bastion ssh \
	--name archreview-bastion \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--target-resource-id "$(az vm show \
		--name archreview-jumpbox \
		--resource-group "$AZURE_RESOURCE_GROUP" \
		--query id -o tsv)" \
	--auth-type ssh-key \
	--username workshopadmin \
	--ssh-key ~/.ssh/id_ed25519
```

From the jump box, run:

```bash
python 00-setup/validate.py
```

### Landing zone

To use established networking, supply both the existing virtual network and
private endpoint subnet resource IDs. The template skips virtual network and
subnet creation and places all private endpoints in the supplied subnet:

```bash
az deployment group create \
	--name architecture-review-setup \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--template-file 00-setup/main.bicep \
	--parameters \
		principalId="$CALLER_OBJECT_ID" \
		sharepointHostname="<sharepoint-hostname>" \
		sharepointSitePath="/sites/<workshop-site>" \
		existingVirtualNetworkResourceId="$VNET_RESOURCE_ID" \
		existingPrivateEndpointSubnetResourceId="$PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID" \
		createPrivateDnsZones=false
```

Both resource ID parameters are required for landing-zone mode. The subnet
must allow private endpoints, and the deployment identity must be allowed to
create private endpoints in it. Set `createPrivateDnsZones=false` when central
private DNS already provides the required zones and virtual network links:

- `privatelink.cognitiveservices.azure.com`
- `privatelink.services.ai.azure.com`
- `privatelink.openai.azure.com`

With DNS creation disabled, the template does not create private DNS zones,
virtual network links, or private endpoint DNS zone groups. The landing-zone
DNS service must create the corresponding records. The optional jump box is
available only in greenfield mode because no existing jump-box subnet is
accepted by this template.

For quick local development, pass `enablePrivateNetworking=false`. This keeps
the existing public service endpoints and does not create the private network.

The deployment outputs the virtual network and private endpoint subnet
resource IDs, whether created or supplied, for later integration.

Application Insights uses public ingestion in this repository, so telemetry
leaves the virtual network even when `enablePrivateNetworking=true`. Agent
tracing works when the workstation or jump box has outbound access to Azure
Monitor ingestion endpoints. Environments that block that outbound access, or
require all telemetry to remain on the private network, need an Azure Monitor
Private Link Scope with private endpoints and private DNS. This repository does
not provision those resources.

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
`modelName`, `modelVersion`, `modelSkuName`, and optionally `modelCapacity` to
the deployment. The default `modelSkuName` is `DataZoneStandard`.

The deployment outputs `applicationInsightsConnectionString` and
`applicationInsightsResourceId`. Agent modules read the connection string from
the same deployment outputs discovered through `AZURE_RESOURCE_GROUP`; if it is
absent, tracing remains disabled and the modules run normally.

Run the validator directly. It reads the deployment outputs using
`AZURE_RESOURCE_GROUP`, which the devcontainer sets to
`rg-architecture-review-workshop`.

```bash
python 00-setup/validate.py
```

The validator prints one `[PASS]` or `[FAIL]` line per dependency, followed by
a summary. It exits with status `1` if any check fails.

## What you should understand by the end

How managed identity, the Azure AI Developer role assignment, deployment
outputs, and Microsoft Graph permissions combine to provide the shared
foundation for later modules.
