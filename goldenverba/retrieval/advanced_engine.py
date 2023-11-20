from goldenverba.retrieval.simple_engine import SimpleVerbaQueryEngine

import os
from wasabi import msg
import openai

TENANT = os.getenv('WEAVIATE_TENANT',default='default_tenant')

class AdvancedVerbaQueryEngine(SimpleVerbaQueryEngine):
    def query(self, query_string: str, model: str) -> tuple:
        """Execute a query to a receive specific chunks from Weaviate
        @parameter query_string : str - Search query
        @returns tuple - (system message, iterable list of results)
        """

        msg.info(f"Using model: {model}")

        # check semantic cache
        results, system_msg = self.retrieve_semantic_cache(query_string)

        if results:
            return (system_msg, results)

#TODO right now it's unclear how the class name will
#be chosen by the Verba team in the definitive 0.3
#version with the new modular design
#as a quick dirty fix we hardcode it to the value that
#we need.
        chunk_class_name = "Chunk_text2vec_openai"

        query_results = (
            SimpleVerbaQueryEngine.client.query.get(
                class_name=chunk_class_name,
                properties=["text", "doc_name", "chunk_id", "doc_uuid", "doc_type"],
            )
            .with_tenant(TENANT)
            .with_hybrid(query=query_string)
            .with_additional(properties=["score"])
            .with_limit(8)
            .do()
        )

        results = query_results["data"]["Get"].get(chunk_class_name)

        if results is None:
            raise Exception(query_results)

        context = self.combine_context(results=results)

        msg.info(
            f"Combined context of all chunks and their weighted windows ({len(context)} characters)"
        )

        openai.api_key = os.environ.get("OPENAI_API_KEY", "")
        if "OPENAI_API_TYPE" in os.environ:
            openai.api_type = os.getenv("OPENAI_API_TYPE")
        if "OPENAI_API_BASE" in os.environ:
            openai.api_base = os.getenv("OPENAI_API_BASE")
        if "OPENAI_API_VERSION" in os.environ:
            openai.api_version = os.getenv("OPENAI_API_VERSION")

        try:
            msg.info(f"Starting API call to answer {query_string}")
            chat_completion_arguments= {
                "model":model,
                "messages":[
                    {
                        "role": "system",
                        "content": f"You are a Retrieval Augmented Generation chatbot. Try to answer this user query {query_string} with only the provided context. If the provided documentation does not provide enough information, say so. Answer in the same language as the language used in the question.",
                    },
                    {"role": "user", "content": context},
                ]
            }
            if openai.api_type=="azure":
                chat_completion_arguments["deployment_id"]=model
            print(chat_completion_arguments)
            completion = openai.ChatCompletion.create(
                **chat_completion_arguments
            )
            print(completion)
            system_msg = str(completion["choices"][0]["message"]["content"])
            self.add_semantic_cache(query_string, results, system_msg)
        except Exception as e:
            system_msg = f"Something went wrong! Please check your API Key. Exception : {str(e)}"
            msg.fail(system_msg)

        return (system_msg, results)

    def combine_context(self, results: list) -> str:
        doc_name_map = {}

        context = ""

        for result in results:
            if result["doc_name"] not in doc_name_map:
                doc_name_map[result["doc_name"]] = {}

            doc_name_map[result["doc_name"]][result["chunk_id"]] = result

        for doc in doc_name_map:
            chunk_map = doc_name_map[doc]
            window = 1
            added_chunks = {}
            for chunk in chunk_map:
                chunk_id = int(chunk)
                all_chunk_range = list(range(chunk_id - window, chunk_id + window + 1))
                for _range in all_chunk_range:
                    if (
                        _range >= 0
                        and _range not in chunk_map
                        and _range not in added_chunks
                    ):
                        chunk_retrieval_results = (
                            SimpleVerbaQueryEngine.client.query.get(
                                class_name="Chunk",
                                properties=[
                                    "text",
                                    "doc_name",
                                    "chunk_id",
                                    "doc_uuid",
                                    "doc_type",
                                ],
                            )
                            .with_tenant(TENANT)                            
                            .with_where(
                                {
                                    "operator": "And",
                                    "operands": [
                                        {
                                            "path": ["chunk_id"],
                                            "operator": "Equal",
                                            "valueNumber": _range,
                                        },
                                        {
                                            "path": ["doc_name"],
                                            "operator": "Equal",
                                            "valueText": str(doc),
                                        },
                                    ],
                                }
                            )
                            .with_limit(1)
                            .do()
                        )

                        if "data" in chunk_retrieval_results:
                            if chunk_retrieval_results["data"]["Get"]["Chunk"]:
                                added_chunks[str(_range)] = chunk_retrieval_results[
                                    "data"
                                ]["Get"]["Chunk"][0]

            for chunk in added_chunks:
                if chunk not in doc_name_map[doc]:
                    doc_name_map[doc][chunk] = added_chunks[chunk]

        for doc in doc_name_map:
            sorted_dict = {
                k: doc_name_map[doc][k]
                for k in sorted(doc_name_map[doc], key=lambda x: int(x))
            }
            msg.info(f"{doc}: {len(sorted_dict)} chunks")
            for chunk in sorted_dict:
                context += sorted_dict[chunk]["text"]

        return context
