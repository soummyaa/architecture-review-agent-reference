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
	defaults to `gpt-5.6-luna` version `2026-07-09`. In `centralus`, this model
	offers `GlobalStandard`, `DataZoneStandard`, `GlobalProvisionedManaged`, and
	`DataZoneProvisionedManaged` deployment SKUs.

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

In many enterprise landing zones, a network or platform team owns these zones
and their DNS records rather than the person running this deployment. DNS
registration must therefore be coordinated with that team. Choose one of
these approaches:

1. If the deployment identity can use the central zones, pass their resource
	IDs to `existingPrivateDnsZoneResourceIds`. The template creates the private
	DNS zone group and Azure registers the Foundry private endpoint records:

	```bash
	--parameters \
		createPrivateDnsZones=false \
		existingPrivateDnsZoneResourceIds="[$(printf '"%s","%s","%s"' \
			"$COGNITIVESERVICES_PRIVATE_DNS_ZONE_ID" \
			"$SERVICES_AI_PRIVATE_DNS_ZONE_ID" \
			"$OPENAI_PRIVATE_DNS_ZONE_ID")]"
	```

2. If the deployment identity cannot use the zones, ask the network or
	platform team that owns them to create the corresponding A records for the
	Foundry private endpoint.

As a manual fallback, someone who owns the zones and can update the private
endpoint can create the DNS zone group directly. The first command creates the
group and registers one zone; the following commands add the other zones:

```bash
FOUNDRY_NAME=$(az deployment group show \
	--name architecture-review-setup \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--query properties.outputs.foundryResourceName.value -o tsv)

az network private-endpoint dns-zone-group create \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--endpoint-name "${FOUNDRY_NAME}-pe" \
	--name default \
	--private-dns-zone "$COGNITIVESERVICES_PRIVATE_DNS_ZONE_ID" \
	--zone-name cognitiveservices

az network private-endpoint dns-zone-group add \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--endpoint-name "${FOUNDRY_NAME}-pe" \
	--name default \
	--private-dns-zone "$SERVICES_AI_PRIVATE_DNS_ZONE_ID" \
	--zone-name services

az network private-endpoint dns-zone-group add \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--endpoint-name "${FOUNDRY_NAME}-pe" \
	--name default \
	--private-dns-zone "$OPENAI_PRIVATE_DNS_ZONE_ID" \
	--zone-name openai
```

Until the private endpoint is registered and its records are resolvable from
the deployment network, `00-setup/validate.py` fails its Foundry and model
deployment checks with a name resolution error.

With DNS creation disabled, the template does not create private DNS zones or
virtual network links. When no existing zone IDs are supplied, it also
intentionally skips the private endpoint DNS zone group. The optional jump box
is available only in greenfield mode because no existing jump-box subnet is
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

## Troubleshooting

### Redeployment fails after deleting the resource group

Deleting the workshop resource group does not immediately purge the Cognitive
Services account behind the Microsoft Foundry project. Azure soft-deletes the
account at the subscription and region level. Redeploying the same account name
in the same region can then fail with `FlagMustBeSetForRestore` or
`CustomDomainInUse`.

When intentionally starting over, run the following command after deleting the
resource group and before redeploying. Use the deleted account's original name,
resource group, and Azure region:

```bash
az cognitiveservices account purge \
	--location "$AZURE_LOCATION" \
	--resource-group "$AZURE_RESOURCE_GROUP" \
	--name "$FOUNDRY_NAME"
```

Purging is irreversible. Run it only when the previous account is no longer
needed and a clean redeployment is intended. Record the account name and region
before deleting the resource group so they are available for this command.

### Azure Bastion CLI API-version errors

In some environments, the optional jump box and Azure Bastion connection can
fail with `InvalidApiVersionParameter` for `bastionHosts` or `virtualMachines`.
At least one reported case was traced to the local workstation environment
rather than to the template or a general Azure CLI limitation, so this does not
mean the greenfield or jump-box path is known to be broken.

If Bastion SSH encounters this error, check the local Azure CLI and `bastion`
extension installation and versions. In some environments,
`az network bastion tunnel` may work as an alternate connection path.

For shared workshop environments, the landing-zone deployment path using an
existing virtual network with VPN or peered connectivity is often the more
predictable option because connectivity can be prepared and verified centrally.

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

The validator treats Microsoft Foundry project access and model invocation as
the two required checks. It prints `[PASS]` or `[FAIL]` for those checks and
exits with status `1` if either fails. SharePoint access is reported separately
as `[PASS]` or `[WARN]`; missing Microsoft Graph tenant consent does not block
Modules 01 through 07. SharePoint-dependent input or publishing still requires
that warning to be resolved.

## What you should understand by the end

How managed identity, the Azure AI Developer role assignment, deployment
outputs, and Microsoft Graph permissions combine to provide the shared
foundation for later modules.
