param name string
param location string = resourceGroup().location
param tags object = {}

@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    publicNetworkAccess: publicNetworkAccess
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      { name: 'EnableServerless' }
    ]
  }
}

output name string = cosmosAccount.name
output endpoint string = cosmosAccount.properties.documentEndpoint
