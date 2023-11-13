import logging
from typing import Dict

import requests
from pydantic_core._pydantic_core import ValidationError
from pydantic_settings import BaseSettings
from verba_utils.payloads import (
    APIKeyPayload,
    APIKeyResponsePayload,
    GetDocumentPayload,
    GetDocumentResponsePayload,
    LoadPayload,
    LoadResponsePayload,
    QueryPayload,
    QueryResponsePayload,
    SearchQueryPayload,
    SearchQueryResponsePayload,
)

log = logging.getLogger(__name__)


class API_routes(BaseSettings):
    verba_port: str | int
    verba_base_url: str
    health: str = "health"
    query: str = "query"
    get_all_documents: str = "get_all_documents"
    get_document: str = "get_document"
    get_components: str = "get_components"
    load_data: str = "load_data"
    delete_document: str = "delete_document"
    set_openai_key: str = "set_openai_key"
    get_openai_key_preview: str = "get_openai_key_preview"
    unset_openai_key: str = "unset_openai_key"
    test_openai_api_key: str = "test_openai_api_key"

    @property
    def base_api_url(self) -> str:
        return f"{self.verba_base_url}:{self.verba_port}/api"


class APIClient:
    def __init__(self, verba_port: str | int, verba_base_url: str):
        self.api_routes = API_routes(
            verba_port=verba_port, verba_base_url=verba_base_url
        )

    def make_request(
        self, method, endpoint, params=None, data=None
    ) -> requests.Response:
        """Generic method to make any request to the backend

        :param str method: _description_
        :param str endpoint: _description_
        :param params: defaults to None
        :param data: defaults to None
        :return _type_:  requests.Response
        """
        headers = {"Content-Type": "application/json"}
        url = self.build_url(endpoint)
        log.info(f"Sending {method} request to {url}")
        return requests.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
        )

    def build_url(self, endpoint: str) -> str:
        """Helper function to build the endpoint url

        :param str endpoint: one attribute of API_routes
        :return str:
        """
        return f"{self.api_routes.base_api_url}/{endpoint}"

    def health_check(self) -> requests.Response:
        return self.make_request("GET", self.api_routes.health)

    def query(self, data: str) -> QueryResponsePayload:
        response = self.make_request(
            method="POST",
            endpoint=self.api_routes.query,
            data=QueryPayload(query=data).model_dump_json(),
        )
        if response.status_code == requests.status_codes.codes["ok"]:
            try:
                return QueryResponsePayload.model_validate(response.json())
            except ValidationError as e:
                log.warning(
                    f"Impossible to convert query response as QueryResponsePayload : {response.json()}, details : {e}"
                )
        else:
            log.warning(f"POST query returned code [{response.status_code}]")
        return QueryResponsePayload(
            system="Sorry, something went wrong when proceeding your request",
            documents=[],
        )

    def get_all_documents(
        self, query: str = "", doc_type: str = ""
    ) -> SearchQueryResponsePayload:
        response = self.make_request(
            method="POST",
            endpoint=self.api_routes.get_all_documents,
            data=SearchQueryPayload(query=query, doc_type=doc_type).model_dump_json(),
        )
        if response.status_code == requests.status_codes.codes["ok"]:
            try:
                return SearchQueryResponsePayload.model_validate(response.json())
            except ValidationError as e:
                log.warning(
                    f"Impossible to convert get_all_documents response as SearchQueryResponsePayload : {response.json()}, details : {e}"
                )
        else:
            log.warning(f"POST query returned code [{response.status_code}]")
        return SearchQueryResponsePayload([], [], "")

    def get_document(self, document_id: str) -> GetDocumentResponsePayload:
        response = self.make_request(
            method="POST",
            endpoint=self.api_routes.get_document,
            data=GetDocumentPayload(document_id=document_id).model_dump_json(),
        )
        if response.status_code == requests.status_codes.codes["ok"]:
            try:
                return GetDocumentResponsePayload.model_validate(response.json())
            except ValidationError as e:
                log.warning(
                    f"Impossible to convert get_all_documents response as SearchQueryResponsePayload : {response.json()}, details : {e}"
                )
        else:
            log.warning(f"POST query returned code [{response.status_code}]")
        return GetDocumentResponsePayload({})

    def get_components(self) -> requests.Response:
        return self.make_request("GET", self.api_routes.get_components)

    def load_data(self, loadPayload: LoadPayload) -> LoadResponsePayload:
        response = self.make_request(
            method="POST",
            endpoint=self.api_routes.load_data,
            data=loadPayload.model_dump_json(),
        )
        if response.status_code == requests.status_codes.codes["ok"]:
            try:
                return LoadResponsePayload.model_validate(response.json())
            except ValidationError as e:
                log.warning(
                    f"Impossible to convert get_all_documents response as SearchQueryResponsePayload : {response.json()}, details : {e}"
                )
        else:
            log.error(
                f"POST query returned code [{response.status_code}] details {response.content}"
            )
        return LoadResponsePayload(
            status=response.status_code, status_msg=response.text
        )

    def delete_document(self, document_id: str) -> bool:
        response = self.make_request(
            method="POST",
            endpoint=self.api_routes.delete_document,
            data=GetDocumentPayload(document_id=document_id).model_dump_json(),
        )
        if response.status_code == requests.status_codes.codes["ok"]:
            return True
        else:
            log.warning(f"POST query returned code [{response.status_code}]")
            return False

    def set_openai_key(self, api_key: str) -> APIKeyResponsePayload:
        response = self.make_request(
            method="POST",
            endpoint=self.api_routes.set_openai_key,
            data=APIKeyPayload(key=api_key).model_dump_json(),
        )
        if response.status_code == requests.status_codes.codes["ok"]:
            try:
                return APIKeyResponsePayload.model_validate(response.json())
            except ValidationError as e:
                log.warning(
                    f"Impossible to convert set_openai_key response as APIKeyResponsePayload : {response.json()}, details : {e}"
                )
        else:
            log.error(
                f"POST query returned code [{response.status_code}] details {response.content}"
            )
        return LoadResponsePayload(
            status=response.status_code, status_msg=response.text
        )

    def get_openai_key_preview(self) -> str:
        response = self.make_request(
            "GET", self.api_routes.get_openai_key_preview
        ).json()

        if response["status"] == "200":
            return response["status_msg"]
        else:
            return ""

    def unset_openai_key(self) -> bool:
        response = self.make_request("POST", self.api_routes.unset_openai_key).json()
        return response["status"] == "200"

    def test_openai_api_key(self) -> Dict:
        response = self.make_request("GET", self.api_routes.test_openai_api_key)
        return response.json()


def test_api_connection(api_client: APIClient) -> dict:
    """
    Do a curl to the health check api endpoint

    :param APIClient api_client:
    :return dict:
    """
    try:
        response = api_client.health_check()
        if response.status_code == requests.status_codes.codes["ok"]:
            return {"is_ok": True}
        else:
            log.error(f"API health status code :{response.status_code}")
            log.error(f"API health content :{response.json()}")
            return {
                "is_ok": False,
                "error_details": f"API health status code : {response.status_code} - API health content : {response.json()}",
            }
    except requests.exceptions.RequestException as e:
        log.error(f"Connection error, make sure verba is running details : {e}")
        return {
            "is_ok": False,
            "error_details": f"Connection error : {e} Make sure Verba is running or accessible",
        }
