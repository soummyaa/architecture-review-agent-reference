targetScope = 'resourceGroup'

@description('Azure region for the private endpoints.')
param location string

@description('Resource ID of the virtual network.')
param virtualNetworkResourceId string

@description('Resource ID of the private endpoint subnet.')
param privateEndpointSubnetResourceId string

@description('Create and link private DNS zones.')
param createPrivateDnsZones bool = true

@description('Resource IDs of existing private DNS zones to register with the Foundry private endpoint.')
param existingPrivateDnsZoneResourceIds array = []

@description('Name of the Microsoft Foundry account.')
param foundryName string

@description('Resource ID of the Microsoft Foundry account.')
param foundryResourceId string

resource foundryPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones) {
  name: 'privatelink.cognitiveservices.azure.com'
  location: 'global'
}

resource foundryServicesPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones) {
  name: 'privatelink.services.ai.azure.com'
  location: 'global'
}

resource foundryOpenAiPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (createPrivateDnsZones) {
  name: 'privatelink.openai.azure.com'
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

resource foundryServicesPrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (createPrivateDnsZones) {
  parent: foundryServicesPrivateDnsZone
  name: 'foundry-services-vnet-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetworkResourceId
    }
  }
}

resource foundryOpenAiPrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (createPrivateDnsZones) {
  parent: foundryOpenAiPrivateDnsZone
  name: 'foundry-openai-vnet-link'
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

var useExistingPrivateDnsZones = !empty(existingPrivateDnsZoneResourceIds)
var existingPrivateDnsZoneConfigs = [
  for (privateDnsZoneResourceId, index) in existingPrivateDnsZoneResourceIds: {
    name: 'existing-${index}'
    properties: {
      privateDnsZoneId: privateDnsZoneResourceId
    }
  }
]
var createdPrivateDnsZoneConfigs = createPrivateDnsZones
  ? [
      {
        name: 'cognitiveservices'
        properties: {
          privateDnsZoneId: foundryPrivateDnsZone.id
        }
      }
      {
        name: 'services'
        properties: {
          privateDnsZoneId: foundryServicesPrivateDnsZone.id
        }
      }
      {
        name: 'openai'
        properties: {
          privateDnsZoneId: foundryOpenAiPrivateDnsZone.id
        }
      }
    ]
  : []
var privateDnsZoneConfigs = useExistingPrivateDnsZones
  ? existingPrivateDnsZoneConfigs
  : createdPrivateDnsZoneConfigs
var createPrivateDnsZoneGroup = useExistingPrivateDnsZones || createPrivateDnsZones

// When zones are neither created nor supplied, the zone group is intentionally
// omitted and central DNS automation must register the private endpoint records.
resource foundryPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (createPrivateDnsZoneGroup) {
  parent: foundryPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: privateDnsZoneConfigs
  }
}