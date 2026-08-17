targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short prefix used to create globally unique resource names.')
@minLength(2)
@maxLength(10)
param namePrefix string = 'archreview'

@description('Name of the Microsoft Foundry project.')
param projectName string = 'architecture-review'

@description('Model name from the Microsoft Foundry model catalog.')
param modelName string = 'gpt-4o-mini'

@description('Model version available in the selected region.')
param modelVersion string = '2024-07-18'

@description('Name used by applications when calling the deployed model.')
param modelDeploymentName string = 'architecture-review-model'

@description('Deployment capacity in thousands of tokens per minute.')
@minValue(1)
param modelCapacity int = 10

var uniqueSuffix = uniqueString(resourceGroup().id)
var foundryName = take('${namePrefix}-${uniqueSuffix}', 64)
var keyVaultName = take('${namePrefix}-${uniqueSuffix}', 24)
var storageName = 'ar${uniqueSuffix}'

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryName
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Architecture Review Workshop'
    description: 'Microsoft Foundry project for the architecture review workshop.'
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: modelDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    accessPolicies: []
    enableRbacAuthorization: true
    enableSoftDelete: true
    publicNetworkAccess: 'Enabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
    softDeleteRetentionInDays: 7
    tenantId: subscription().tenantId
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

output foundryProjectEndpoint string = 'https://${foundry.name}.services.ai.azure.com/api/projects/${project.name}'
output foundryResourceId string = foundry.id
output foundryResourceName string = foundry.name
output modelEndpoint string = 'https://${foundry.name}.openai.azure.com/'
output modelDeploymentName string = modelDeployment.name
output keyVaultName string = keyVault.name
output storageAccountName string = storageAccount.name