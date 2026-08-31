targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Object ID of the user or managed identity that runs the workshop.')
param principalId string

@description('Short prefix used to create globally unique resource names.')
@minLength(2)
@maxLength(10)
param namePrefix string = 'archreview'

@description('Name of the Microsoft Foundry project.')
param projectName string = 'architecture-review'

@description('Model name from the Microsoft Foundry model catalog.')
param modelName string = 'gpt-5.6-luna'

@description('Model version available in the selected region.')
param modelVersion string = '2026-07-09'

// DataZoneStandard keeps inference within the data zone; GlobalStandard routes globally, which regulated customers may not permit.
@description('SKU used for the model deployment.')
param modelSkuName string = 'DataZoneStandard'

@description('Name used by applications when calling the deployed model.')
param modelDeploymentName string = 'architecture-review-model'

@description('Deployment capacity in thousands of tokens per minute.')
@minValue(1)
param modelCapacity int = 50

@description('SharePoint hostname used by the setup validator.')
param sharepointHostname string

@description('Server-relative path of the SharePoint workshop site.')
param sharepointSitePath string

@description('Deploy private endpoints, private DNS, and disable public access to the platform services.')
param enablePrivateNetworking bool = true

@description('Resource ID of an existing virtual network. Supply with existingPrivateEndpointSubnetResourceId to use landing-zone networking.')
param existingVirtualNetworkResourceId string = ''

@description('Resource ID of an existing private endpoint subnet. Supply with existingVirtualNetworkResourceId to use landing-zone networking.')
param existingPrivateEndpointSubnetResourceId string = ''

@description('Create and link private DNS zones. Set to false when private DNS is managed centrally.')
param createPrivateDnsZones bool = true

@description('Deploy a Linux jump box reachable through Azure Bastion or an existing network path.')
param deployJumpBox bool = false

@description('SSH public key for the optional Linux jump box.')
param sshPublicKey string = ''

@description('Administrator username for the optional Linux jump box.')
param jumpBoxAdminUsername string = 'workshopadmin'

var uniqueSuffix = uniqueString(resourceGroup().id)
var foundryName = take('${namePrefix}-${uniqueSuffix}', 64)
var logAnalyticsWorkspaceName = take('${namePrefix}-${uniqueSuffix}-logs', 63)
var applicationInsightsName = take('${namePrefix}-${uniqueSuffix}-appi', 260)
var virtualNetworkName = '${namePrefix}-vnet'
var privateEndpointSubnetName = 'private-endpoints'
var jumpBoxSubnetName = 'jumpbox'
var bastionSubnetName = 'AzureBastionSubnet'
var jumpBoxName = '${namePrefix}-jumpbox'
var jumpBoxNicName = '${namePrefix}-jumpbox-nic'
var jumpBoxNsgName = '${namePrefix}-jumpbox-nsg'
var bastionName = '${namePrefix}-bastion'
var bastionPublicIpName = '${namePrefix}-bastion-pip'
var useExistingNetworking = !empty(existingVirtualNetworkResourceId) && !empty(existingPrivateEndpointSubnetResourceId)
var deployManagedVirtualNetwork = enablePrivateNetworking && !useExistingNetworking
var virtualNetworkResourceId = useExistingNetworking ? existingVirtualNetworkResourceId : virtualNetwork.id
var privateEndpointSubnetResourceId = useExistingNetworking ? existingPrivateEndpointSubnetResourceId : privateEndpointSubnet.id
var azureAiDeveloperRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '64702f94-c441-49e6-a78b-ef80e0188fee'
)

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-05-01' = if (deployManagedVirtualNetwork) {
  name: virtualNetworkName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        name: privateEndpointSubnetName
        properties: {
          addressPrefix: '10.0.1.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      ...(deployJumpBox ? [
        {
          name: jumpBoxSubnetName
          properties: {
            addressPrefix: '10.0.2.0/24'
          }
        }
        {
          name: bastionSubnetName
          properties: {
            addressPrefix: '10.0.3.0/26'
          }
        }
      ] : [])
    ]
  }
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = if (deployManagedVirtualNetwork) {
  parent: virtualNetwork
  name: privateEndpointSubnetName
}

resource jumpBoxSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = if (deployManagedVirtualNetwork && deployJumpBox) {
  parent: virtualNetwork
  name: jumpBoxSubnetName
}

resource bastionSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = if (deployManagedVirtualNetwork && deployJumpBox) {
  parent: virtualNetwork
  name: bastionSubnetName
}

module foundryProvisioning 'provision-foundry.bicep' = {
  name: 'provision-foundry'
  params: {
    location: location
    foundryName: foundryName
    projectName: projectName
    modelName: modelName
    modelVersion: modelVersion
    modelSkuName: modelSkuName
    modelDeploymentName: modelDeploymentName
    modelCapacity: modelCapacity
  }
}

module observabilityProvisioning 'provision-observability.bicep' = {
  name: 'provision-observability'
  params: {
    location: location
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    applicationInsightsName: applicationInsightsName
  }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

module privateNetworking 'private-networking.bicep' = if (enablePrivateNetworking) {
  name: 'private-networking'
  params: {
    location: location
    virtualNetworkResourceId: virtualNetworkResourceId
    privateEndpointSubnetResourceId: privateEndpointSubnetResourceId
    createPrivateDnsZones: createPrivateDnsZones
    foundryName: foundryProvisioning.outputs.foundryName
    foundryResourceId: foundryProvisioning.outputs.foundryResourceId
  }
  // The account API can return Accepted before provisioning is complete, so the module boundary is intentional.
  dependsOn: [
    #disable-next-line no-unnecessary-dependson
    foundryProvisioning
  ]
}

module disableFoundryPublicAccess 'disable-foundry-public-access.bicep' = if (enablePrivateNetworking) {
  name: 'disable-foundry-public-access'
  params: {
    foundryName: foundryProvisioning.outputs.foundryName
    location: location
  }
  dependsOn: [
    privateNetworking
  ]
}

resource jumpBoxNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = if (deployManagedVirtualNetwork && deployJumpBox) {
  name: jumpBoxNsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'allow-ssh'
        properties: {
          access: 'Allow'
          direction: 'Inbound'
          priority: 100
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '22'
        }
      }
    ]
  }
}

resource jumpBoxNic 'Microsoft.Network/networkInterfaces@2024-05-01' = if (deployManagedVirtualNetwork && deployJumpBox) {
  name: jumpBoxNicName
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: jumpBoxSubnet.id
          }
        }
      }
    ]
    networkSecurityGroup: {
      id: jumpBoxNsg.id
    }
  }
}

resource bastionPublicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = if (deployManagedVirtualNetwork && deployJumpBox) {
  name: bastionPublicIpName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource bastionHost 'Microsoft.Network/bastionHosts@2024-05-01' = if (deployManagedVirtualNetwork && deployJumpBox) {
  name: bastionName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    enableTunneling: true
    ipConfigurations: [
      {
        name: 'configuration'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: {
            id: bastionPublicIp.id
          }
          subnet: {
            id: bastionSubnet.id
          }
        }
      }
    ]
  }
}

resource jumpBox 'Microsoft.Compute/virtualMachines@2024-07-01' = if (deployManagedVirtualNetwork && deployJumpBox) {
  name: jumpBoxName
  location: location
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_B2s'
    }
    osProfile: {
      computerName: jumpBoxName
      adminUsername: jumpBoxAdminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${jumpBoxAdminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Standard_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: jumpBoxNic.id
          properties: {
            primary: true
          }
        }
      ]
    }
  }
}

resource foundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, principalId, azureAiDeveloperRoleId)
  scope: foundry
  properties: {
    principalId: principalId
    roleDefinitionId: azureAiDeveloperRoleId
  }
  dependsOn: [
    foundryProvisioning
  ]
}

output foundryProjectEndpoint string = 'https://${foundryProvisioning.outputs.foundryName}.services.ai.azure.com/api/projects/${foundryProvisioning.outputs.projectName}'
output foundryResourceId string = foundry.id
output foundryResourceName string = foundry.name
output modelEndpoint string = 'https://${foundry.name}.openai.azure.com/'
output modelDeploymentName string = foundryProvisioning.outputs.modelDeploymentName
output applicationInsightsConnectionString string = observabilityProvisioning.outputs.applicationInsightsConnectionString
output applicationInsightsResourceId string = observabilityProvisioning.outputs.applicationInsightsResourceId
output sharepointHostname string = sharepointHostname
output sharepointSitePath string = sharepointSitePath
output virtualNetworkResourceId string = enablePrivateNetworking ? virtualNetworkResourceId : ''
output privateEndpointSubnetResourceId string = enablePrivateNetworking ? privateEndpointSubnetResourceId : ''