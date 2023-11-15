import re

from wasabi import msg  # type: ignore[import]
from weaviate import Client
from weaviate import Tenant
import os

from goldenverba.ingestion.util import setup_client

VECTORIZERS = set(["text2vec-openai"])  # Needs to match with Weaviate modules
EMBEDDINGS = set() #["MiniLM"])  # Custom Vectors

TENANT = os.getenv('WEAVIATE_TENANT',default='default_tenant')

def strip_non_letters(s: str):
    return re.sub(r"[^a-zA-Z0-9]", "_", s)

def create_if_not_exists(client,class_name,class_schema,tenant_name,reset=False):
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
    schema: dict, vectorizer: str, skip_properties: list[str] = []
) -> dict:
    """Verifies if the vectorizer is available and adds it to a schema, also skips vectorization if list is provided
    @parameter schema : dict - Schema json
    @parameter vectorizer : str - Name of the vectorizer
    @parameter skip_properties: list[str] - List of property names that should not get vectorized
    @returns dict - Modified schema if vectorizer is available
    """
    modified_schema = schema.copy()

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
    elif vectorizer != None:
        msg.warn(f"Could not find matching vectorizer: {vectorizer}")

    return modified_schema


def add_suffix(schema: dict, vectorizer: str) -> tuple[dict, str]:
    """Adds the suffixof the vectorizer to the schema name
    @parameter schema : dict - Schema json
    @parameter vectorizer : str - Name of the vectorizer
    @returns dict - Modified schema if vectorizer is available
    """
    modified_schema = schema.copy()
    # Verify Vectorizer and add suffix
    modified_schema["classes"][0]["class"] = (
        modified_schema["classes"][0]["class"] + "_" + strip_non_letters(vectorizer)
    )
    return modified_schema, modified_schema["classes"][0]["class"]

def delete_tenant(
    client: Client, tenant_name: str
):
    """Deletes a tenant
    @parameter client : Client - Weaviate client
    @parameter tenant_name : str - Name of the tenant
    @returns None
    """
    client.schema.remove_class_tenants(class_name=class_name,tenants=[Tenant(name=tenant_name)])

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
    @returns tuple[dict, dict] - Tuple of modified schemas
    """

    try:
        init_documents(client, vectorizer, force, check,reset=reset)
        init_cache(client, vectorizer, force, check, reset=reset)
        # init_suggestion(client, vectorizer, force, check)
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
    @returns tuple[dict, dict] - Tuple of modified schemas
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

    create_if_not_exists(client,document_name,document_schema,TENANT,reset=reset)
    create_if_not_exists(client,chunk_name,chunk_schema,TENANT,reset=reset)

    # If Weaviate Embedded runs
    if client._connection.embedded_db:
        msg.info("Stopping Weaviate Embedded")
        client._connection.embedded_db.stop()

    return document_schema, chunk_schema


def init_cache(
    client: Client, vectorizer: str = None, force: bool = False, check: bool = False, reset: bool = False
) -> dict:
    """Initializes the Cache
    @parameter client : Client - Weaviate client
    @parameter vectorizer : str - Name of the vectorizer
    @parameter force : bool - Delete existing schema without user input
    @parameter check : bool - Only create if not exist
    @returns dict - Modified schema
    """

    SCHEMA_CACHE = {
        "classes": [
            {
                "class": "Cache",
                'multiTenancyConfig': {'enabled': True},                
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
                    {
                        # Skip
                        "name": "results",
                        "dataType": ["text"],
                        "description": "List of results",
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

    create_if_not_exists(client,cache_name,cache_schema,TENANT,reset=reset)

    # If Weaviate Embedded runs
    if client._connection.embedded_db:
        msg.info("Stopping Weaviate Embedded")
        client._connection.embedded_db.stop()

    return cache_schema


def init_suggestion(
    client: Client, vectorizer: str = None, force: bool = False, check: bool = False, reset: bool = False
) -> dict:
    """Initializes the Suggestion schema
    @parameter client : Client - Weaviate client
    @parameter vectorizer : str - Name of the vectorizer
    @parameter force : bool - Delete existing schema without user input
    @parameter check : bool - Only create if not exist
    @returns dict - Modified schema
    """

    SCHEMA_SUGGESTION = {
        "classes": [
            {
                "class": "Suggestion",
                'multiTenancyConfig': {'enabled': True},                
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

    # Add Suffix
    suggestion_schema, suggestion_name = add_suffix(SCHEMA_SUGGESTION, vectorizer)

    create_if_not_exists(client,suggestion_name,suggestion_schema,TENANT,reset=reset)

  

    # If Weaviate Embedded runs
    if client._connection.embedded_db:
        msg.info("Stopping Weaviate Embedded")
        client._connection.embedded_db.stop()

    return suggestion_schema
