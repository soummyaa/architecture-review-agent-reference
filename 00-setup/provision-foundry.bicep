targetScope = 'resourceGroup'

@description('Azure region for the Microsoft Foundry resources.')
param location string

@description('Name of the Microsoft Foundry account.')
param foundryName string

@description('Name of the Microsoft Foundry project.')
param projectName string

@description('Model name from the Microsoft Foundry model catalog.')
param modelName string

@description('Model version available in the selected region.')
param modelVersion string

@description('SKU used for the model deployment.')
param modelSkuName string = 'DataZoneStandard'

@description('Name used by applications when calling the deployed model.')
param modelDeploymentName string

@description('Deployment capacity in thousands of tokens per minute.')
param modelCapacity int

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
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

output foundryName string = foundry.name
output foundryResourceId string = foundry.id
output projectName string = project.name
output modelDeploymentName string = modelDeployment.name