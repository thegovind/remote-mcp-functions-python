import json
import logging
import base64

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"

# Constants for multi-modal content
_IMAGE_NAME_PROPERTY_NAME = "imagename"
_IMAGE_PROPERTY_NAME = "image"
_IMAGE_BLOB_PATH = "images/{mcptoolargs." + _IMAGE_NAME_PROPERTY_NAME + "}.bin"


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

# Define tool properties for multi-modal content
tool_properties_save_image_object = [
    ToolProperty(_IMAGE_NAME_PROPERTY_NAME, "string", "The name of the image."),
    ToolProperty(_IMAGE_PROPERTY_NAME, "string", "The base64-encoded image content."),
]

tool_properties_get_image_object = [ToolProperty(_IMAGE_NAME_PROPERTY_NAME, "string", "The name of the image.")]

# Convert the multi-modal tool properties to JSON
tool_properties_save_image_json = json.dumps([prop.to_dict() for prop in tool_properties_save_image_object])
tool_properties_get_image_json = json.dumps([prop.to_dict() for prop in tool_properties_get_image_object])


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
    toolName="save_image",
    description="Save an image with a name.",
    toolProperties=tool_properties_save_image_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_IMAGE_BLOB_PATH)
def save_image(file: func.Out[bytes], context) -> str:
    """
    Saves a base64-encoded image to Azure Blob Storage.
    
    Args:
        file (func.Out[bytes]): The output binding to save the image to Azure Blob Storage.
        context: The trigger context containing the input arguments.
        
    Returns:
        str: A success message or an error message.
    """
    content = json.loads(context)
    image_name_from_args = content["arguments"][_IMAGE_NAME_PROPERTY_NAME]
    image_content_from_args = content["arguments"][_IMAGE_PROPERTY_NAME]
    
    if not image_name_from_args:
        return "No image name provided"
    
    if not image_content_from_args:
        return "No image content provided"
    
    try:
        binary_content = base64.b64decode(image_content_from_args)
        file.set(binary_content)
        logging.info(f"Saved image: {image_name_from_args}")
        return f"Image '{image_name_from_args}' saved successfully"
    except Exception as e:
        error_message = f"Error saving image: {str(e)}"
        logging.error(error_message)
        return error_message


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_image",
    description="Retrieve an image by name.",
    toolProperties=tool_properties_get_image_json,
)
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_IMAGE_BLOB_PATH)
def get_image(file: func.InputStream, context) -> str:
    """
    Retrieves an image by name from Azure Blob Storage and returns it as a base64-encoded string.
    
    Args:
        file (func.InputStream): The input binding to read the image from Azure Blob Storage.
        context: The trigger context containing the input arguments.
        
    Returns:
        str: The base64-encoded image content or an error message.
    """
    try:
        binary_content = file.read()
        
        base64_content = base64.b64encode(binary_content).decode('utf-8')
        
        logging.info(f"Retrieved image with size: {len(binary_content)} bytes")
        return base64_content
    except Exception as e:
        error_message = f"Error retrieving image: {str(e)}"
        logging.error(error_message)
        return error_message
