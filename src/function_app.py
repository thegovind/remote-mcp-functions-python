import json
import logging
import os

import azure.functions as func
from azure.cosmos import CosmosClient, exceptions as cosmos_exceptions

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"

def get_cosmos_client():
    """Initialize and return a Cosmos DB client using connection settings from app configuration.
    
    Returns:
        CosmosClient or None: Initialized Cosmos DB client or None if initialization fails
    """
    try:
        conn_str = os.environ.get("CosmosDBConnectionString")
        if not conn_str:
            logging.warning("CosmosDBConnectionString not configured, Cosmos DB storage disabled")
            return None
        
        return CosmosClient.from_connection_string(conn_str)
    except Exception as e:
        logging.error(f"Error initializing Cosmos DB client: {str(e)}")
        return None

def save_to_cosmos(snippet_name, snippet_content):
    """Save a snippet to Cosmos DB.
    
    Args:
        snippet_name (str): The name of the snippet.
        snippet_content (str): The content of the snippet.
        
    Returns:
        tuple: (bool, str) - Success status and message
    """
    try:
        client = get_cosmos_client()
        if not client:
            logging.info(f"Cosmos DB client not initialized, would save snippet '{snippet_name}' if available")
            return True, f"Snippet '{snippet_name}' would be saved to Cosmos DB (emulator not available)"
        
        database_name = os.environ.get("CosmosDBDatabaseName", "SnippetsDB")
        container_name = os.environ.get("CosmosDBContainerName", "snippets")
        
        database = client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        
        document = {
            "id": snippet_name,
            _SNIPPET_NAME_PROPERTY_NAME: snippet_name,
            _SNIPPET_PROPERTY_NAME: snippet_content,
            "timestamp": str(func.datetime.utcnow())
        }
        
        container.upsert_item(document)
        return True, f"Snippet '{snippet_name}' saved to Cosmos DB successfully"
    except Exception as e:
        logging.error(f"Error saving to Cosmos DB: {str(e)}")
        return False, f"Failed to save to Cosmos DB: {str(e)}"


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
    logging.info(f"Saved snippet '{snippet_name_from_args}' to Blob Storage")
    
    cosmos_success, cosmos_message = save_to_cosmos(snippet_name_from_args, snippet_content_from_args)
    if cosmos_success:
        logging.info(cosmos_message)
    else:
        logging.warning(cosmos_message)
    
    return f"Snippet '{snippet_content_from_args}' saved successfully" + (
        "" if cosmos_success else " (Note: Saved to Blob Storage only, Cosmos DB save failed)"
    )
