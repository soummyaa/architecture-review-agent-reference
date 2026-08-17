# Module 00: Setup

## Goal

Provision the shared Microsoft Foundry project, model deployment, Key Vault,
and storage account. Validate that the workshop identity can reach the project,
invoke the model, and resolve the workshop SharePoint site through Microsoft
Graph.

## Prerequisites

- An Azure subscription and a resource group where you can create resources
  and role assignments.
- Azure CLI with Bicep and Python 3.10 or later.
- A model and model version available in the target Azure region. The template
  defaults to `gpt-4o-mini` version `2024-07-18`.
- The validating identity assigned `Azure AI User` and `Cognitive Services
  OpenAI User` on the provisioned Microsoft Foundry resource.
- Tenant-admin-approved Microsoft Graph access to the target SharePoint site.
  Use least privilege: application identities should use `Sites.Selected` with
  an explicit site grant. A workshop user may use delegated `Sites.Read.All`.

The Bicep template creates only Azure resources. Microsoft Graph consent and
site grants are tenant-level operations and must be completed separately by an
Entra administrator.

## Run Standalone

Sign in and deploy the resources. Parameter values below are synthetic labels,
not tenant-specific configuration.

```bash
az login
az group create --name rg-architecture-review-workshop --location eastus
az deployment group create \
  --name architecture-review-setup \
  --resource-group rg-architecture-review-workshop \
  --template-file main.bicep \
  --parameters namePrefix=archreview
```

If the default model version is unavailable in the selected region, pass
`modelName`, `modelVersion`, and optionally `modelCapacity` to the deployment.

Capture the outputs and grant the validating user the required data-plane
roles. For a managed identity, use its object ID and set the principal type to
`ServicePrincipal` instead.

```bash
RESOURCE_GROUP=rg-architecture-review-workshop
DEPLOYMENT_NAME=architecture-review-setup
FOUNDRY_SCOPE=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query properties.outputs.foundryResourceId.value -o tsv)
CALLER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)

az role assignment create \
  --assignee-object-id "$CALLER_OBJECT_ID" \
  --assignee-principal-type User \
  --role "Azure AI User" \
  --scope "$FOUNDRY_SCOPE"
az role assignment create \
  --assignee-object-id "$CALLER_OBJECT_ID" \
  --assignee-principal-type User \
  --role "Cognitive Services OpenAI User" \
  --scope "$FOUNDRY_SCOPE"
```

Create an isolated Python environment and run the validation. Supply the
SharePoint hostname and path for the synthetic workshop site provisioned by
your administrator.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

PROJECT_ENDPOINT=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query properties.outputs.foundryProjectEndpoint.value -o tsv)
MODEL_ENDPOINT=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query properties.outputs.modelEndpoint.value -o tsv)
MODEL_DEPLOYMENT=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query properties.outputs.modelDeploymentName.value -o tsv)

python validate_setup.py \
  --project-endpoint "$PROJECT_ENDPOINT" \
  --model-endpoint "$MODEL_ENDPOINT" \
  --model-deployment "$MODEL_DEPLOYMENT" \
  --sharepoint-hostname "<sharepoint-hostname>" \
  --sharepoint-site-path "/sites/<workshop-site>"
```

The validator prints one `[PASS]` or `[FAIL]` line per dependency, followed by
a summary. It exits with status `1` if any check fails, making it suitable for
an unattended readiness job.