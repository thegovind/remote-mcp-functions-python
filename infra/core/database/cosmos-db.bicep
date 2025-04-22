param name string
param location string = resourceGroup().location
param tags object = {}

@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

param containers array = [
  {
    name: 'snippets'
    partitionKey: '/id'
  }
]

resource cosmosDB 'Microsoft.DocumentDB/databaseAccounts@2022-05-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
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
      {
        name: 'EnableServerless'
      }
    ]
    publicNetworkAccess: publicNetworkAccess
  }
  
  resource database 'sqlDatabases' = {
    name: 'SnippetsDB'
    properties: {
      resource: {
        id: 'SnippetsDB'
      }
    }
    
    resource containerList 'containers' = [for container in containers: {
      name: container.name
      properties: {
        resource: {
          id: container.name
          partitionKey: {
            paths: [
              container.partitionKey
            ]
            kind: 'Hash'
          }
        }
      }
    }]
  }
}

output name string = cosmosDB.name
output endpoint string = cosmosDB.properties.documentEndpoint
