targetScope = 'resourceGroup'

@description('Name of the provisioned Microsoft Foundry account.')
param foundryName string

@description('Azure region of the Microsoft Foundry account.')
param location string

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
    publicNetworkAccess: 'Disabled'
  }
}