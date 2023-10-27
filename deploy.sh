#!/bin/bash
export OPENAI_API_TYPE="azure"
export OPENAI_API_BASE="https://worldlinegptfr.openai.azure.com"
export OPENAI_API_VERSION="2023-07-01-preview"
export AZURE_OPENAI_RESOURCE_NAME="worldlinegptfr"
export AZURE_OPENAI_EMBEDDING_MODEL="text-embedding-ada-002"
export VERBA_WAIT_TIME_BETWEEN_INGESTION_QUERIES_MS="500"
export VERBA_MODEL="gpt-4"
export VERBA_URL="http://localhost:8080"

TENANT_NUMBER=$1
#check that the tenant number is not empty and a number
if [ -z "$TENANT_NUMBER" ] || ! [[ "$TENANT_NUMBER" =~ ^[0-9]+$ ]]
then
    echo "Please provide a tenant number as the first argument"
    exit 1
fi

#set the VERBA_URL port as 8080+tenant number
PORT=$(($TENANT_NUMBER+8000))
export WEAVIATE_TENANT='tenant_'$TENANT_NUMBER

#start verba, store std and error logs in verba.$1.log, do not erase the previous logs
verba start --port $PORT >> verba.$1.log 2>&1 



