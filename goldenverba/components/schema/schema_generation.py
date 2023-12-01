import re
import os
from dotenv import load_dotenv
from wasabi import msg  # type: ignore[import]
from weaviate import Client, Tenant

load_dotenv()

VECTORIZERS = {"text2vec-openai", "text2vec-cohere"}  # Needs to match with Weaviate modules
EMBEDDINGS = {"MiniLM"}  # Custom Vectors

TENANT = os.getenv('WEAVIATE_TENANT',default='default_tenant')

def strip_non_letters(s: str):
    return re.sub(r"[^a-zA-Z0-9]", "_", s)

def create_if_not_exists(
    client: Client,
    class_name: str, 
    class_schema: str, 
    tenant_name: str, 
    reset: bool =False
) -> None:
    """Ensures that a schema exists for the specified class_name within the client. Creates the schema if it does not exist, 
    optionally resets it for the tenant, and adds the class to the tenant if it's not already present. 
    @param client: Client - The client instance to interact with the schema.
    @param class_name: str - The name of the class to check or create in the schema.
    @param class_schema: str - The schema definition to create if the class does not exist.
    @param tenant_name: str - The name of the tenant to add the class to or remove from.
    @param reset: bool - A flag to determine whether the class tenants should be reset (default is False).
    @returns None
    """
    if not client.schema.exists(class_name):
        client.schema.create(class_schema)
        msg.good(f"{class_name} schema created")
    if reset:
        client.schema.remove_class_tenants(class_name=class_name,tenants=[tenant_name])
        msg.good(f"tenant {tenant_name} class {class_name} removed")
    if not tenant_name in [tenant.name for tenant in client.schema.get_class_tenants(class_name)]:
        client.schema.add_class_tenants(class_name=class_name,tenants=[Tenant(name=tenant_name)])
        msg.good(f"{class_name} schema added to tenant {tenant_name}")

def verify_vectorizer(
    schema: dict, vectorizer: str, skip_properties: list[str] = None
) -> dict:
    """Verifies if the vectorizer is available and adds it to a schema, also skips vectorization if list is provided
    @parameter schema : dict - Schema json
    @parameter vectorizer : str - Name of the vectorizer
    @parameter skip_properties: list[str] - List of property names that should not get vectorized
    @returns dict - Modified schema if vectorizer is available.
    """
    if skip_properties is None:
        skip_properties = []
    modified_schema = schema.copy()

    #adding specific config for Azure OpenAI
    vectorizer_config = None
    if os.getenv("OPENAI_API_TYPE") == "azure" and vectorizer=="text2vec-openai":
        resourceName = os.getenv("AZURE_OPENAI_RESOURCE_NAME")
        model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL")
        if resourceName is None or model is None:
            raise Exception("AZURE_OPENAI_RESOURCE_NAME and AZURE_OPENAI_EMBEDDING_MODEL should be set when OPENAI_API_TYPE is azure. Resource name is XXX in http://XXX.openai.azure.com")
        vectorizer_config = { 
            "text2vec-openai": {
                    "deploymentId": model,
                    "resourceName": resourceName
            }
        }

    # Verify Vectorizer
    if vectorizer in VECTORIZERS:
        modified_schema["classes"][0]["vectorizer"] = vectorizer
        if vectorizer_config is not None:
            modified_schema["classes"][0]["moduleConfig"] = vectorizer_config
        for property in modified_schema["classes"][0]["properties"]:
            if property["name"] in skip_properties:
                moduleConfig = {
                    vectorizer: {
                        "skip": True,
                        "vectorizePropertyName": False,
                    }
                }
                property["moduleConfig"] = moduleConfig
    elif vectorizer in EMBEDDINGS:
        pass
    elif vectorizer is not None:
        msg.warn(f"Could not find matching vectorizer: {vectorizer}")

    return modified_schema


def add_suffix(schema: dict, vectorizer: str) -> tuple[dict, str]:
    """Adds the suffixof the vectorizer to the schema name
    @parameter schema : dict - Schema json
    @parameter vectorizer : str - Name of the vectorizer
    @returns dict - Modified schema if vectorizer is available.
    """
    modified_schema = schema.copy()
    # Verify Vectorizer and add suffix
    modified_schema["classes"][0]["class"] = (
        modified_schema["classes"][0]["class"] + "_" + strip_non_letters(vectorizer)
    )
    return modified_schema, modified_schema["classes"][0]["class"]

# REMARK : we don"t need this function anymore
def reset_schemas(
    client: Client = None,
    vectorizer: str = None,
):
    doc_name = "Document_" + strip_non_letters(vectorizer)
    chunk_name = "Chunk_" + strip_non_letters(vectorizer)
    cache_name = "Cache_" + strip_non_letters(vectorizer)

    client.schema.delete_class(doc_name)
    client.schema.delete_class(chunk_name)
    client.schema.delete_class(cache_name)

def init_schemas(
    client: Client = None,
    vectorizer: str = None,
    force: bool = False,
    check: bool = False,
    reset: bool = False
) -> bool:
    """Initializes a weaviate client and initializes all required schemas
    @parameter client : Client - Weaviate Client
    @parameter vectorizer : str - Name of the vectorizer
    @parameter force : bool - Delete existing schema without user input
    @parameter check : bool - Only create if not exist
    @parameter reset : bool - Reset tenant
    @returns tuple[dict, dict] - Tuple of modified schemas.
    """
    try:
        init_documents(client, vectorizer, force, check, reset=reset)
        init_cache(client, vectorizer, force, check, reset=reset)
        init_suggestion(client, vectorizer, force, check, reset=reset)
        return True
    except Exception as e:
        msg.fail(f"Schema initialization failed {str(e)}")
        return False


def init_documents(
    client: Client, vectorizer: str = None, force: bool = False, check: bool = False, reset: bool = False
) -> tuple[dict, dict]:
    """Initializes the Document and Chunk class
    @parameter client : Client - Weaviate client
    @parameter vectorizer : str - Name of the vectorizer
    @parameter force : bool - Delete existing schema without user input
    @parameter check : bool - Only create if not exist
    @parameter reset : bool - Reset tenant
    @returns tuple[dict, dict] - Tuple of modified schemas.
    """
    SCHEMA_CHUNK = {
        "classes": [
            {
                "class": "Chunk",
                'multiTenancyConfig': {'enabled': True},                
                "description": "Chunks of Documentations",
                "properties": [
                    {
                        "name": "text",
                        "dataType": ["text"],
                        "description": "Content of the document",
                    },
                    {
                        "name": "doc_name",
                        "dataType": ["text"],
                        "description": "Document name",
                    },
                    {
                        # Skip
                        "name": "doc_type",
                        "dataType": ["text"],
                        "description": "Document type",
                    },
                    {
                        # Skip
                        "name": "doc_uuid",
                        "dataType": ["text"],
                        "description": "Document UUID",
                    },
                    {
                        # Skip
                        "name": "chunk_id",
                        "dataType": ["number"],
                        "description": "Document chunk from the whole document",
                    },
                ],
            }
        ]
    }

    SCHEMA_DOCUMENT = {
        "classes": [
            {
                "class": "Document",
                'multiTenancyConfig': {'enabled': True},
                "description": "Documentation",
                "properties": [
                    {
                        "name": "text",
                        "dataType": ["text"],
                        "description": "Content of the document",
                    },
                    {
                        "name": "doc_name",
                        "dataType": ["text"],
                        "description": "Document name",
                    },
                    {
                        "name": "doc_type",
                        "dataType": ["text"],
                        "description": "Document type",
                    },
                    {
                        "name": "doc_link",
                        "dataType": ["text"],
                        "description": "Link to document",
                    },
                    {
                        "name": "timestamp",
                        "dataType": ["text"],
                        "description": "Timestamp of document",
                    },
                    {
                        "name": "chunk_count",
                        "dataType": ["number"],
                        "description": "Number of chunks",
                    },
                ],
            }
        ]
    }

    # Verify Vectorizer
    chunk_schema = verify_vectorizer(
        SCHEMA_CHUNK,
        vectorizer,
        ["doc_type", "doc_uuid", "chunk_id"],
    )

    # Add Suffix
    document_schema, document_name = add_suffix(SCHEMA_DOCUMENT, vectorizer)
    chunk_schema, chunk_name = add_suffix(chunk_schema, vectorizer)

    create_if_not_exists(client, document_name, document_schema, TENANT, reset=reset)
    create_if_not_exists(client, chunk_name, chunk_schema, TENANT, reset=reset)    

    return document_schema, chunk_schema


def init_cache(
    client: Client, vectorizer: str = None, force: bool = False, check: bool = False, reset: bool = False
) -> dict:
    """Initializes the Cache
    @parameter client : Client - Weaviate client
    @parameter vectorizer : str - Name of the vectorizer
    @parameter force : bool - Delete existing schema without user input
    @parameter check : bool - Only create if not exist
    @parameter reset : bool - Reset tenant
    @returns dict - Modified schema.
    """
    SCHEMA_CACHE = {
        "classes": [
            {
                "class": "Cache",
                "multiTenancyConfig": {"enabled": True},                
                "description": "Cache of Documentations and their queries",
                "properties": [
                    {
                        "name": "query",
                        "dataType": ["text"],
                        "description": "Query",
                    },
                    {
                        # Skip
                        "name": "system",
                        "dataType": ["text"],
                        "description": "System message",
                    },
                ],
            }
        ]
    }

    # Verify Vectorizer
    cache_schema = verify_vectorizer(
        SCHEMA_CACHE,
        vectorizer,
        ["system", "results"],
    )

    # Add Suffix
    cache_schema, cache_name = add_suffix(cache_schema, vectorizer)

    create_if_not_exists(client, cache_name, cache_schema, TENANT, reset=reset)

    return cache_schema


def init_suggestion(
    client: Client, vectorizer: str = None, force: bool = False, check: bool = False, reset: bool = False
) -> dict:
    """Initializes the Suggestion schema
    @parameter client : Client - Weaviate client
    @parameter vectorizer : str - Name of the vectorizer
    @parameter force : bool - Delete existing schema without user input
    @parameter check : bool - Only create if not exist
    @parameter reset : bool - Reset tenant
    @returns dict - Modified schema.
    """
    SCHEMA_SUGGESTION = {
        "classes": [
            {
                "class": "Suggestion",
                "multiTenancyConfig": {"enabled": True},                
                "description": "List of possible prompts",
                "properties": [
                    {
                        "name": "suggestion",
                        "dataType": ["text"],
                        "description": "Query",
                    },
                ],
            }
        ]
    }

    suggestion_schema = SCHEMA_SUGGESTION
    suggestion_name = "Suggestion"

    create_if_not_exists(client, suggestion_name, suggestion_schema, TENANT, reset=reset)

    return suggestion_schema
