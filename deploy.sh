#!/usr/bin/env bash
# Deploy the Architecture Review Agent workshop infrastructure.

set -euo pipefail

RG=${AZURE_RESOURCE_GROUP:-rg-architecture-review-workshop}
LOCATION=${AZURE_LOCATION:-centralus}
APP_PORT_ID=${APP_PORT_ID:-OI-7F9623760C1011F1BD67C66C3F89230A}
MODEL_NAME=${MODEL_NAME:-gpt-5.6-luna}
MODEL_VERSION=${MODEL_VERSION:-2026-07-09}

: "${SHAREPOINT_HOSTNAME:?Set SHAREPOINT_HOSTNAME, for example contoso.sharepoint.com}"
: "${SHAREPOINT_SITE_PATH:?Set SHAREPOINT_SITE_PATH, for example /sites/workshop}"

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
  --parameters principalIds="[\"$PID\"]" \
  --parameters enablePrivateNetworking=false \
  --parameters modelName="$MODEL_NAME" \
  --parameters modelVersion="$MODEL_VERSION" \
  --parameters sharepointHostname="$SHAREPOINT_HOSTNAME" \
  --parameters sharepointSitePath="$SHAREPOINT_SITE_PATH"

echo ""
echo "Deploy finished. Next:"
echo "  export AZURE_RESOURCE_GROUP=$RG"
echo "  python 00-setup/validate.py"
