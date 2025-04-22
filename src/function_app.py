import json
import logging
import os

import azure.functions as func
from azure.cosmos import CosmosClient, PartitionKey

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the storage
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"
_COSMOS_CONTAINER_NAME = "snippets"


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


# Define the tool properties using the ToolProperty class
tool_properties_save_snippets_object = [
    ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."),
    ToolProperty(_SNIPPET_PROPERTY_NAME, "string", "The content of the snippet."),
]

tool_properties_get_snippets_object = [ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet.")]

# Convert the tool properties to JSON
tool_properties_save_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_save_snippets_object])
tool_properties_get_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_get_snippets_object])


def get_cosmos_client():
    """Get a Cosmos DB client."""
    endpoint = os.environ.get("CosmosDBEndpoint")
    database_name = os.environ.get("CosmosDBDatabaseName", "snippets-db")
    client = CosmosClient(endpoint)
    database = client.get_database_client(database_name)
    container = database.get_container_client(_COSMOS_CONTAINER_NAME)
    return container


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> str:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_snippet",
    description="Retrieve a snippet by name.",
    toolProperties=tool_properties_get_snippets_json,
)
def get_snippet(context) -> str:
    """
    Retrieves a snippet by name from Azure Cosmos DB.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    try:
        content = json.loads(context)
        snippet_name = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
        
        container = get_cosmos_client()
        query = f"SELECT * FROM c WHERE c.snippetname = '{snippet_name}'"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        if not items:
            return f"Snippet '{snippet_name}' not found"
            
        snippet_content = items[0][_SNIPPET_PROPERTY_NAME]
        logging.info(f"Retrieved snippet: {snippet_content}")
        return snippet_content
    except Exception as e:
        logging.error(f"Error retrieving snippet: {str(e)}")
        return f"Error retrieving snippet: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet",
    description="Save a snippet with a name.",
    toolProperties=tool_properties_save_snippets_json,
)
def save_snippet(context) -> str:
    """
    Saves a snippet with a name to Azure Cosmos DB.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: A success or error message.
    """
    try:
        content = json.loads(context)
        snippet_name = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
        snippet_content = content["arguments"][_SNIPPET_PROPERTY_NAME]

        if not snippet_name:
            return "No snippet name provided"

        if not snippet_content:
            return "No snippet content provided"

        container = get_cosmos_client()
        item = {
            "id": snippet_name,
            _SNIPPET_NAME_PROPERTY_NAME: snippet_name,
            _SNIPPET_PROPERTY_NAME: snippet_content
        }
        container.upsert_item(item)
        
        logging.info(f"Saved snippet: {snippet_name}")
        return f"Snippet '{snippet_name}' saved successfully"
    except Exception as e:
        logging.error(f"Error saving snippet: {str(e)}")
        return f"Error saving snippet: {str(e)}"
