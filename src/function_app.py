import json
import logging
import os

import azure.functions as func
from azure.cosmos import CosmosClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"

# Constants for Cosmos DB
_COSMOS_DB_NAME = "snippets"
_COSMOS_DB_CONTAINER = "items"


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


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
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
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def get_snippet(file: func.InputStream, context) -> str:
    """
    Retrieves a snippet by name from Azure Blob Storage.

    Args:
        file (func.InputStream): The input binding to read the snippet from Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    snippet_content = file.read().decode("utf-8")
    logging.info(f"Retrieved snippet: {snippet_content}")
    return snippet_content


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet",
    description="Save a snippet with a name.",
    toolProperties=tool_properties_save_snippets_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def save_snippet(file: func.Out[str], context) -> str:
    content = json.loads(context)
    snippet_name_from_args = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    snippet_content_from_args = content["arguments"][_SNIPPET_PROPERTY_NAME]

    if not snippet_name_from_args:
        return "No snippet name provided"

    if not snippet_content_from_args:
        return "No snippet content provided"

    file.set(snippet_content_from_args)
    logging.info(f"Saved snippet: {snippet_content_from_args}")
    return f"Snippet '{snippet_content_from_args}' saved successfully"

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_snippet_cosmos",
    description="Retrieve a snippet by name from Cosmos DB.",
    toolProperties=tool_properties_get_snippets_json,
)
def get_snippet_cosmos(context) -> str:
    """
    Retrieves a snippet by name from Azure Cosmos DB.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    content = json.loads(context)
    snippet_name = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    
    connection_string = os.environ.get("CosmosDbConnectionString")
    if not connection_string:
        return "Cosmos DB connection string not configured"
        
    client = CosmosClient.from_connection_string(connection_string)
    database = client.get_database_client(_COSMOS_DB_NAME)
    container = database.get_container_client(_COSMOS_DB_CONTAINER)
    
    query = f"SELECT * FROM c WHERE c.id = '{snippet_name}'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    
    if not items:
        return f"Snippet '{snippet_name}' not found"
        
    return items[0][_SNIPPET_PROPERTY_NAME]

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet_cosmos",
    description="Save a snippet with a name to Cosmos DB.",
    toolProperties=tool_properties_save_snippets_json,
)
def save_snippet_cosmos(context) -> str:
    """
    Saves a snippet with a name to Azure Cosmos DB.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: A message indicating success or failure.
    """
    content = json.loads(context)
    snippet_name = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    snippet_content = content["arguments"][_SNIPPET_PROPERTY_NAME]

    if not snippet_name:
        return "No snippet name provided"

    if not snippet_content:
        return "No snippet content provided"
        
    connection_string = os.environ.get("CosmosDbConnectionString")
    if not connection_string:
        return "Cosmos DB connection string not configured"
        
    client = CosmosClient.from_connection_string(connection_string)
    database = client.get_database_client(_COSMOS_DB_NAME)
    container = database.get_container_client(_COSMOS_DB_CONTAINER)
    
    item = {
        "id": snippet_name,
        _SNIPPET_PROPERTY_NAME: snippet_content
    }
    
    container.upsert_item(item)
    logging.info(f"Saved snippet to Cosmos DB: {snippet_content}")
    return f"Snippet '{snippet_name}' saved successfully to Cosmos DB"
