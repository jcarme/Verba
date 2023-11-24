import os
import base64
import shelve

from wasabi import msg  # type: ignore[import]

import openai
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from pathlib import Path
from pydantic import BaseModel
from typing import Optional

from goldenverba.retrieval.advanced_engine import AdvancedVerbaQueryEngine
from goldenverba import verba_manager

from goldenverba.ingestion.reader.interface import Reader
from goldenverba.ingestion.chunking.interface import Chunker
from goldenverba.ingestion.embedding.interface import Embedder


from dotenv import load_dotenv

load_dotenv()

manager = None #
readers = None
chunckers = None
verba_engine = None

option_cache = {}

def check_manager_initialized():
    if manager == None:
        raise HTTPException(503,"Verba not initialized. Please upload a key using /api/set_openai_key")

def store_api_key(key):
    weaviate_tenant = os.getenv('WEAVIATE_TENANT',default='default_tenant')
    with shelve.open("key_cache") as db:
        db[weaviate_tenant] = key

def remove_api_key():
    global manager
    manager = None

    os.environ.pop("OPENAI_API_KEY", None)

    weaviate_tenant = os.getenv("WEAVIATE_TENANT", default="default_tenant")
    with shelve.open("key_cache") as db:
        if weaviate_tenant in db:
            del db[weaviate_tenant]
        else:
            msg.info(f"{weaviate_tenant} is not in the shelve database.")


def check_api_key():
    if "OPENAI_API_KEY" in os.environ:
        return True
    weaviate_tenant = os.getenv('WEAVIATE_TENANT',default='default_tenant')
    with shelve.open("key_cache") as db:
        key = db.get(weaviate_tenant,None)
    if key:
        os.environ["OPENAI_API_KEY"] = key
        return True
    return False


def init_manager():
    global manager
    global readers
    global chunker
    global embedders
    global verba_engine
    global option_cache

    if not check_api_key():
        return

    manager = verba_manager.VerbaManager()

    readers = manager.reader_get_readers()
    for reader in readers:
        available, message = manager.check_verba_component(readers[reader])
        if available:
            manager.reader_set_reader(reader)
            option_cache["last_reader"] = reader
            option_cache["last_document_type"] = "Documentation"
            break

    chunker = manager.chunker_get_chunker()
    for chunk in chunker:
        available, message = manager.check_verba_component(chunker[chunk])
        if available:
            manager.chunker_set_chunker(chunk)
            option_cache["last_chunker"] = chunk
            break


    embedders = manager.embedder_get_embedder()
    embedder_available = False
    for embedder in embedders:
        available, message = manager.check_verba_component(embedders[embedder])
        if available:
            manager.embedder_set_embedder(embedder)
            option_cache["last_embedder"] = embedder
            embedder_available = True
            break
    if not embedder_available:
        raise HTTPException(400,"No embedder available. If you use OpenAI, please check you have uploaded your key using /api/set_openai_key")
    
    # Delete later
    verba_engine = AdvancedVerbaQueryEngine(manager.client)


init_manager()


def create_reader_payload(key: str, reader: Reader) -> dict:
    available, message = manager.check_verba_component(reader)

    return {
        "name": key,
        "description": reader.description,
        "input_form": reader.input_form,
        "available": available,
        "message": message,
    }


def create_chunker_payload(key: str, chunker: Chunker) -> dict:
    available, message = manager.check_verba_component(chunker)

    return {
        "name": key,
        "description": chunker.description,
        "input_form": chunker.input_form,
        "units": chunker.default_units,
        "overlap": chunker.default_overlap,
        "available": available,
        "message": message,
    }


def create_embedder_payload(key: str, embedder: Embedder) -> dict:
    available, message = manager.check_verba_component(embedder)

    return {
        "name": key,
        "description": embedder.description,
        "input_form": embedder.input_form,
        "available": available,
        "message": message,
    }




# FastAPI App
app = FastAPI(root_path=os.environ.get("URL_PREFIX", ""))

if os.environ.get("URL_PREFIX", None):
    msg.info(f"FastAPI started with root_path = {os.environ.get('URL_PREFIX')}")

origins = [
    "http://localhost:3000",
    "https://verba-golden-ragtriever.onrender.com",
    "http://localhost:8000",
]

# Add middleware for handling Cross Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

# Serve the assets (JS, CSS, images, etc.)
app.mount(
    "/static/_next",
    StaticFiles(directory=BASE_DIR / "frontend/out/_next"),
    name="next-assets",
)

# Serve the main page and other static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend/out"), name="app")


class QueryPayload(BaseModel):
    query: str

class APIKeyPayload(BaseModel):
    key: str

class SearchQueryPayload(BaseModel):
    query: Optional[str] = ""
    doc_type: Optional[str] = ""


class GetDocumentPayload(BaseModel):
    document_id: str


class LoadPayload(BaseModel):
    reader: str
    chunker: str
    embedder: str
    fileBytes: list[str]
    fileNames: list[str]
    filePath: str
    document_type: str
    chunkUnits: int
    chunkOverlap: int


class GetComponentPayload(BaseModel):
    component: str


class SetComponentPayload(BaseModel):
    component: str
    selected_component: str


@app.get("/")
@app.head("/")
async def serve_frontend():
    return FileResponse(os.path.join(BASE_DIR, "frontend/out/index.html"))


# Define health check endpoint
@app.get("/api/health")
async def root():
    check_manager_initialized()
    try:
        if verba_engine.get_client().is_ready():
            return JSONResponse(
                content={
                    "message": "Alive!",
                }
            )
        else:
            return JSONResponse(
                content={
                    "message": "Database not ready!",
                },
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
    except Exception as e:
        msg.fail(f"Healthcheck failed with {str(e)}")
        return JSONResponse(
            content={
                "message": f"Healthcheck failed with {str(e)}",
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# Define health check endpoint
@app.get("/api/get_google_tag")
async def get_google_tag():
    tag = os.environ.get("VERBA_GOOGLE_TAG", "")

    if tag:
        msg.good("Google Tag available!")

    return JSONResponse(
        content={
            "tag": tag,
        }
    )


# Get Readers, Chunkers, and Embedders
@app.get("/api/get_components")
async def get_components():
    msg.info("Retrieving components")

    data = {"readers": [], "chunker": [], "embedder": []}

    for key in readers:
        current_reader = readers[key]
        current_reader_data = create_reader_payload(key, current_reader)
        data["readers"].append(current_reader_data)

    for key in chunker:
        current_chunker = chunker[key]
        current_chunker_data = create_chunker_payload(key, current_chunker)
        data["chunker"].append(current_chunker_data)

    for key in embedders:
        current_embedder = embedders[key]
        current_embedder_data = create_embedder_payload(key, current_embedder)
        data["embedder"].append(current_embedder_data)

    data["default_values"] = {
        "last_reader": create_reader_payload(
            option_cache["last_reader"], readers[option_cache["last_reader"]]
        ),
        "last_chunker": create_chunker_payload(
            option_cache["last_chunker"], chunker[option_cache["last_chunker"]]
        ),
        "last_embedder": create_embedder_payload(
            option_cache["last_embedder"], embedders[option_cache["last_embedder"]]
        ),
        "last_document_type": option_cache["last_document_type"],
    }

    return JSONResponse(content=data)


@app.post("/api/get_component")
async def get_component(payload: GetComponentPayload):
    msg.info(f"Retrieving {payload.component} components")

    data = {"components": []}

    if payload.component == "embedders":
        data["selected_component"] = create_embedder_payload(
            manager.embedder_manager.selected_embedder.name,
            manager.embedder_manager.selected_embedder,
        )

        for key in embedders:
            current_embedder = embedders[key]
            current_embedder_data = create_embedder_payload(key, current_embedder)
            data["components"].append(current_embedder_data)

    return JSONResponse(content=data)


@app.post("/api/set_component")
async def set_component(payload: SetComponentPayload):
    msg.info(f"Setting {payload.component} to {payload.selected_component}")

    if payload.component == "embedders":
        manager.embedder_manager.set_embedder(payload.selected_component)
        option_cache["last_embedder"] = payload.selected_component

    return JSONResponse(content={})


# Get Status meta data
@app.get("/api/get_status")
async def get_status():
    msg.info("Retrieving status")

    data = {
        "type": manager.weaviate_type,
        "libraries": manager.installed_libraries,
        "variables": manager.environment_variables,
        "schemas": manager.get_schemas(),
    }

    return JSONResponse(content=data)


# Reset Verba
@app.get("/api/reset")
async def reset_verba():
    msg.info("Resetting verba")

    manager.reset()

    return JSONResponse(status_code=200, content={})


# Receive query and return chunks and query answer
@app.post("/api/load_data")
async def load_data(payload: LoadPayload):
    check_manager_initialized()
    manager.reader_set_reader(payload.reader)
    manager.chunker_set_chunker(payload.chunker)
    manager.embedder_set_embedder(payload.embedder)

    global option_cache

    option_cache["last_reader"] = payload.reader
    option_cache["last_document_type"] = payload.document_type
    option_cache["last_chunker"] = payload.chunker
    option_cache["last_embedder"] = payload.embedder

    # Set new default values based on user input
    current_chunker = manager.chunker_get_chunker()[payload.chunker]
    current_chunker.default_units = payload.chunkUnits
    current_chunker.default_overlap = payload.chunkOverlap

    msg.info(
        f"Received Data to Import: READER({payload.reader}, Documents {len(payload.fileBytes)}, Type {payload.document_type}) CHUNKER ({payload.chunker}, UNITS {payload.chunkUnits}, OVERLAP {payload.chunkOverlap}), EMBEDDER ({payload.embedder})"
    )

    if payload.fileBytes or payload.filePath:
        try:
            documents = manager.import_data(
                payload.fileBytes,
                [],
                [payload.filePath],
                payload.fileNames,
                payload.document_type,
                payload.chunkUnits,
                payload.chunkOverlap,
            )

            if documents == None:
                return JSONResponse(
                    content={
                        "status": 200,
                        "status_msg": f"Succesfully imported {document_count} documents and {chunks_count} chunks",
                    }
                )

            document_count = len(documents)
            chunks_count = sum([len(document.chunks) for document in documents])

            return JSONResponse(
                content={
                    "status": 200,
                    "status_msg": f"Succesfully imported {document_count} documents and {chunks_count} chunks",
                }
            )
        except Exception as e:
            msg.fail(f"Loading data failed {str(e)}")
            return JSONResponse(
                content={
                    "status": "400",
                    "status_msg": str(e),
                }
            )
    return JSONResponse(
        content={
            "status": "200",
            "status_msg": "No documents received",
        }
    )


# Receive query and return chunks and query answer
@app.post("/api/query")
async def query(payload: QueryPayload):
    check_manager_initialized()
    try:
        system_msg, results = verba_engine.query(
            payload.query, os.environ["VERBA_MODEL"]
        )
        msg.good(f"Succesfully processed query: {payload.query}")

        return JSONResponse(
            content={
                "system": system_msg,
                "documents": results,
            }
        )
    except Exception as e:
        msg.fail(f"Query failed")
        print(e)
        return JSONResponse(
            content={
                "system": f"Something went wrong! {str(e)}",
                "documents": [],
            }
        )


# Retrieve auto complete suggestions based on user input
@app.post("/api/suggestions")
async def suggestions(payload: QueryPayload):
    try:
        suggestions = verba_engine.get_suggestions(payload.query)

        return JSONResponse(
            content={
                "suggestions": suggestions,
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "suggestions": [],
            }
        )


# Retrieve specific document based on UUID
@app.post("/api/get_document")
async def get_document(payload: GetDocumentPayload):
    msg.info(f"Document ID received: {payload.document_id}")

    try:
        document = manager.retrieve_document(payload.document_id)
        msg.good(f"Succesfully retrieved document: {payload.document_id}")
        return JSONResponse(
            content={
                "document": document,
            }
        )
    except Exception as e:
        msg.fail(f"Document retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "document": {},
            }
        )


## Retrieve all documents imported to Weaviate
@app.post("/api/get_all_documents")
async def get_all_documents(payload: SearchQueryPayload):
    msg.info(f"Get all documents request received")

    try:
        documents = manager.retrieve_all_documents(payload.doc_type)
        msg.good(f"Succesfully retrieved document: {len(documents)} documents")

        doc_types = set([document["doc_type"] for document in documents])

        return JSONResponse(
            content={
                "documents": documents,
                "doc_types": list(doc_types),
                "current_embedder": manager.embedder_manager.selected_embedder.name,
            }
        )
    except Exception as e:
        msg.fail(f"All Document retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "documents": [],
                "doc_types": [],
                "current_embedder": manager.embedder_manager.selected_embedder.name,
            }
        )


## Search for documentation
@app.post("/api/search_documents")
async def search_documents(payload: SearchQueryPayload):
    try:
        documents = manager.search_documents(payload.query, payload.doc_type)
        return JSONResponse(
            content={
                "documents": documents,
                "current_embedder": manager.embedder_manager.selected_embedder.name,
            }
        )
    except Exception as e:
        msg.fail(f"All Document retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "documents": [],
                "current_embedder": manager.embedder_manager.selected_embedder.name,
            }
        )


# Retrieve specific document based on UUID
@app.post("/api/delete_document")
async def delete_document(payload: GetDocumentPayload):
    msg.info(f"Document ID received: {payload.document_id}")

    manager.delete_document_by_id(payload.document_id)
    return JSONResponse(content={})


#setting openai key
@app.post("/api/set_openai_key")
async def set_openai_key(payload: APIKeyPayload):
    try:
        os.environ["OPENAI_API_KEY"] = payload.key      
        store_api_key(payload.key)
        init_manager()
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "OpenAI key set",
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "400",
                "status_msg": "OpenAI key not set",
            }
        )

@app.post("/api/unset_openai_key")
async def unset_openai_key():
    try:
        remove_api_key()
        init_manager()
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "OpenAI key unset",
            }
        )
    except Exception as e:
        msg.warn(f"Something when wrong when removing OpenAPI key : {e}")
        return JSONResponse(
            content={
                "status": "400",
                "status_msg": "Something went wrong when trying to unset OpenAPI key",
            }
        )


@app.get("/api/get_openai_key_preview")
async def get_openai_key_preview():
    len_preview = 3
    if not "OPENAI_API_KEY" in os.environ:
        return JSONResponse(
            content={
                "status": "400",
                "status_msg": "No OPENAI_API_KEY set",
            }
        )
    else:
        preview = (
            os.environ["OPENAI_API_KEY"][:len_preview]
            + "*" * (len(os.environ["OPENAI_API_KEY"]) - 2 * len_preview)
            + os.environ["OPENAI_API_KEY"][-len_preview:]
        )

        return JSONResponse(
            content={
                "status": "200",
                "status_msg": preview,
            }
        )


@app.get("/api/test_openai_api_key")
async def test_openai_api_key():
    if not "OPENAI_API_KEY" in os.environ:
        return JSONResponse(
            content={
                "status": "400",
                "status_msg": "No OPENAI_API_KEY set",
            }
        )
    else:
        try:
            openai.api_key = os.environ.get("OPENAI_API_KEY", "")
            if "OPENAI_API_TYPE" in os.environ:
                openai.api_type = os.getenv("OPENAI_API_TYPE")
            if "OPENAI_API_BASE" in os.environ:
                openai.api_base = os.getenv("OPENAI_API_BASE")
            if "OPENAI_API_VERSION" in os.environ:
                openai.api_version = os.getenv("OPENAI_API_VERSION")

            chat_completion_arguments = {
                "model": os.environ["VERBA_MODEL"],
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a Teacher/ Professor",
                    },
                    {
                        "role": "user",
                        "content": "hello",
                    },
                ],
            }
            if openai.api_type == "azure":
                chat_completion_arguments["deployment_id"] = os.environ["VERBA_MODEL"]

            _ = openai.ChatCompletion.create(**chat_completion_arguments)
        except (openai.error.AuthenticationError, openai.error.APIError) as e:
            msg.warn(f"Something went wrong when testing your API key : {e}")
            return JSONResponse(
                content={
                    "status": "400",
                    "status_msg": f"Something went wrong when testing your API key : {e}",
                }
            )
        else:
            return JSONResponse(
                content={
                    "status": "200",
                    "status_msg": "OpenAPI key is working",
                }
            )
