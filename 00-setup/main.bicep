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
param modelName string = 'gpt-4o-mini'

@description('Model version available in the selected region.')
param modelVersion string = '2024-07-18'

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

@description('Deploy a Linux jump box reachable through Azure Bastion or an existing network path.')
param deployJumpBox bool = false

@description('SSH public key for the optional Linux jump box.')
param sshPublicKey string = ''

@description('Administrator username for the optional Linux jump box.')
param jumpBoxAdminUsername string = 'workshopadmin'

var uniqueSuffix = uniqueString(resourceGroup().id)
var foundryName = take('${namePrefix}-${uniqueSuffix}', 64)
var keyVaultName = 'kv${uniqueSuffix}'
var storageName = 'ar${uniqueSuffix}'
var virtualNetworkName = '${namePrefix}-vnet'
var privateEndpointSubnetName = 'private-endpoints'
var jumpBoxSubnetName = 'jumpbox'
var jumpBoxName = '${namePrefix}-jumpbox'
var jumpBoxNicName = '${namePrefix}-jumpbox-nic'
var jumpBoxNsgName = '${namePrefix}-jumpbox-nsg'
var azureAiDeveloperRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '64702f94-c441-49e6-a78b-ef80e0188fee'
)
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)
var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-05-01' = if (enablePrivateNetworking) {
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
      {
        name: jumpBoxSubnetName
        properties: {
          addressPrefix: '10.0.2.0/24'
        }
      }
    ]
  }
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = if (enablePrivateNetworking) {
  parent: virtualNetwork
  name: privateEndpointSubnetName
}

resource jumpBoxSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = if (enablePrivateNetworking && deployJumpBox) {
  parent: virtualNetwork
  name: jumpBoxSubnetName
}

module foundryProvisioning 'provision-foundry.bicep' = {
  name: 'provision-foundry'
  params: {
    location: location
    foundryName: foundryName
    projectName: projectName
    modelName: modelName
    modelVersion: modelVersion
    modelDeploymentName: modelDeploymentName
    modelCapacity: modelCapacity
  }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    accessPolicies: []
    enableRbacAuthorization: true
    enableSoftDelete: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
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
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

module privateNetworking 'private-networking.bicep' = if (enablePrivateNetworking) {
  name: 'private-networking'
  params: {
    location: location
    virtualNetworkResourceId: virtualNetwork.id
    privateEndpointSubnetResourceId: privateEndpointSubnet.id
    foundryName: foundryProvisioning.outputs.foundryName
    foundryResourceId: foundryProvisioning.outputs.foundryResourceId
    keyVaultName: keyVault.name
    keyVaultResourceId: keyVault.id
    storageAccountName: storageAccount.name
    storageAccountResourceId: storageAccount.id
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

resource jumpBoxNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = if (enablePrivateNetworking && deployJumpBox) {
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

resource jumpBoxNic 'Microsoft.Network/networkInterfaces@2024-05-01' = if (enablePrivateNetworking && deployJumpBox) {
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

resource jumpBox 'Microsoft.Compute/virtualMachines@2024-07-01' = if (enablePrivateNetworking && deployJumpBox) {
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

resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, principalId, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    principalId: principalId
    roleDefinitionId: keyVaultSecretsUserRoleId
  }
}

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, principalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    principalId: principalId
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

output foundryProjectEndpoint string = 'https://${foundryProvisioning.outputs.foundryName}.services.ai.azure.com/api/projects/${foundryProvisioning.outputs.projectName}'
output foundryResourceId string = foundry.id
output foundryResourceName string = foundry.name
output modelEndpoint string = 'https://${foundry.name}.openai.azure.com/'
output modelDeploymentName string = foundryProvisioning.outputs.modelDeploymentName
output keyVaultName string = keyVault.name
output sharepointHostname string = sharepointHostname
output sharepointSitePath string = sharepointSitePath
output storageAccountName string = storageAccount.name
output virtualNetworkResourceId string = enablePrivateNetworking ? virtualNetwork.id : ''
output privateEndpointSubnetResourceId string = enablePrivateNetworking ? privateEndpointSubnet.id : ''