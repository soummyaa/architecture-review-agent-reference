#!/usr/bin/env bash
# Deploy the Architecture Review Agent workshop infrastructure.

set -euo pipefail

RG=${AZURE_RESOURCE_GROUP:-rg-architecture-review-workshop}
LOCATION=${AZURE_LOCATION:-centralus}
APP_PORT_ID=${APP_PORT_ID:-OI-7F9623760C1011F1BD67C66C3F89230A}

: "${SHAREPOINT_HOSTNAME:?Set SHAREPOINT_HOSTNAME, for example contoso.sharepoint.com}"
: "${SHAREPOINT_SITE_PATH:?Set SHAREPOINT_SITE_PATH, for example /sites/workshop}"
: "${VNET_RESOURCE_ID:?Set VNET_RESOURCE_ID to the existing virtual network resource ID}"
: "${PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID:?Set PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID to the existing private endpoint subnet resource ID}"

echo "Resolving signed-in user object id..."
PID=$(az ad signed-in-user show --query id -o tsv)
echo "Object id: $PID"

echo "Ensuring resource group $RG exists in $LOCATION..."
az group create \
  --name "$RG" \
  --location "$LOCATION" \
  --tags "AppPortId=$APP_PORT_ID" \
  --output none

echo "Deploying Foundry project and model deployment..."
az deployment group create \
  --name architecture-review-setup \
  --resource-group "$RG" \
  --template-file 00-setup/main.bicep \
  --parameters \
    principalIds="[\"$PID\"]" \
    sharepointHostname="$SHAREPOINT_HOSTNAME" \
    sharepointSitePath="$SHAREPOINT_SITE_PATH" \
    existingVirtualNetworkResourceId="$VNET_RESOURCE_ID" \
    existingPrivateEndpointSubnetResourceId="$PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID" \
    createPrivateDnsZones=false

echo ""
echo "Deploy finished. Next:"
echo "  export AZURE_RESOURCE_GROUP=$RG"
echo "  python 00-setup/validate.py"
