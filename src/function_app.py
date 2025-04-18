import json
import logging
import os
from typing import Dict, List, Tuple

import azure.functions as func
import numpy as np
import openai
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"


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

_SEARCH_QUERY_PROPERTY_NAME = "query"
tool_properties_search_snippets_object = [ToolProperty(_SEARCH_QUERY_PROPERTY_NAME, "string", "The search query to find relevant snippets.")]

# Convert the tool properties to JSON
tool_properties_save_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_save_snippets_object])
tool_properties_get_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_get_snippets_object])
tool_properties_search_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_search_snippets_object])


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


def list_all_snippets() -> List[Tuple[str, str]]:
    """
    Lists all snippets from Azure Blob Storage.
    
    Returns:
        List[Tuple[str, str]]: A list of tuples containing snippet name and content.
    """
    connection_string = os.environ.get("AzureWebJobsStorage", "")
    if connection_string and connection_string.startswith("UseDevelopment"):
        connection_string = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client("snippets")
    
    snippets = []
    for blob in container_client.list_blobs():
        blob_client = container_client.get_blob_client(blob.name)
        content = blob_client.download_blob().readall().decode("utf-8")
        snippet_name = blob.name.replace(".json", "")
        snippets.append((snippet_name, content))
    
    return snippets


def generate_embeddings(text: str) -> np.ndarray:
    """
    Generate embeddings for a given text using OpenAI.
    
    Args:
        text (str): The input text to generate embeddings for.
        
    Returns:
        np.ndarray: The embedding vector.
    """
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    
    return np.array(response['data'][0]['embedding'])


def calculate_similarity(query_embedding: np.ndarray, snippet_embedding: np.ndarray) -> float:
    """
    Calculate cosine similarity between two embedding vectors.
    """
    return np.dot(query_embedding, snippet_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(snippet_embedding))


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="search_snippets",
    description="Search snippets using AI to find relevant code.",
    toolProperties=tool_properties_search_snippets_json,
)
def search_snippets(context) -> str:
    """
    Searches snippets using AI to find relevant code based on a query.
    
    Args:
        context: The trigger context containing the input arguments.
        
    Returns:
        str: JSON string containing the search results with snippet names, 
             content previews, and relevance scores.
    """
    content = json.loads(context)
    search_query = content["arguments"][_SEARCH_QUERY_PROPERTY_NAME]
    
    if not search_query:
        return json.dumps({"error": "No search query provided"})
    
    try:
        all_snippets = list_all_snippets()
        
        if not all_snippets:
            return json.dumps({"results": [], "message": "No snippets found to search"})
        
        # Generate embeddings for the search query
        query_embedding = generate_embeddings(search_query)
        
        # Calculate similarity with each snippet
        results = []
        for snippet_name, snippet_content in all_snippets:
            snippet_embedding = generate_embeddings(snippet_content)
            similarity = calculate_similarity(query_embedding, snippet_embedding)
            
            if similarity > 0.7:  # Adjust threshold as needed
                preview = snippet_content[:100] + "..." if len(snippet_content) > 100 else snippet_content
                results.append({
                    "name": snippet_name,
                    "preview": preview,
                    "similarity": float(similarity),
                })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return json.dumps({"results": results})
    except Exception as e:
        logging.error(f"Error in search_snippets: {str(e)}")
        return json.dumps({"error": str(e)})
