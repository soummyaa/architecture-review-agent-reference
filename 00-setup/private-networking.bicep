targetScope = 'resourceGroup'

@description('Azure region for the private endpoints.')
param location string

@description('Resource ID of the virtual network.')
param virtualNetworkResourceId string

@description('Resource ID of the private endpoint subnet.')
param privateEndpointSubnetResourceId string

@description('Create and link private DNS zones.')
param createPrivateDnsZones bool = true

@description('Name of the Microsoft Foundry account.')
param foundryName string

@description('Resource ID of the Microsoft Foundry account.')
param foundryResourceId string

resource foundryPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones) {
  name: 'privatelink.cognitiveservices.azure.com'
  location: 'global'
}

resource foundryPrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (createPrivateDnsZones) {
  parent: foundryPrivateDnsZone
  name: 'foundry-vnet-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetworkResourceId
    }
  }
}

resource foundryPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${foundryName}-pe'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: '${foundryName}-connection'
        properties: {
          privateLinkServiceId: foundryResourceId
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
}

resource foundryPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (createPrivateDnsZones) {
  parent: foundryPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'cognitiveservices'
        properties: {
          privateDnsZoneId: foundryPrivateDnsZone.id
        }
      }
    ]
  }
}