#!/bin/bash
export OPENAI_API_TYPE="azure"
export OPENAI_API_BASE="https://worldlinegptfr.openai.azure.com"
export OPENAI_API_VERSION="2023-07-01-preview"
export AZURE_OPENAI_RESOURCE_NAME="worldlinegptfr"
export AZURE_OPENAI_EMBEDDING_MODEL="text-embedding-ada-002"
export VERBA_WAIT_TIME_BETWEEN_INGESTION_QUERIES_MS="500"
export VERBA_MODEL="gpt-4"
export VERBA_URL="http://localhost:8080"
export BASE_VERBA_API_URL="http://localhost"

TENANT_NUMBER=$1
#check that the tenant number is not empty and a number
if [ -z "$TENANT_NUMBER" ] || ! [[ "$TENANT_NUMBER" =~ ^[0-9]+$ ]]
then
    echo "Please provide a tenant number as the first argument"
    exit 1
fi

#set the VERBA_URL port as 8080+tenant number
VERBA_PORT=$(($TENANT_NUMBER+8000))
STREAMLIT_PORT=$(($TENANT_NUMBER+8500))
export WEAVIATE_TENANT='tenant_'$TENANT_NUMBER


#start verba, store std and error logs in verba.$1.log, do not erase the previous logs
echo "starting verba on port $VERBA_PORT..."
# verba start --port $VERBA_PORT >> verba.$1.log 2>&1 &

# Wait for verba to start
sleep 1

echo "verba started"

echo "starting streamlit on port $STREAMLIT_PORT..."

# Exécuter streamlit
streamlit run streamlit_rag/app.py --server.port $STREAMLIT_PORT --server.headless true --theme.base dark --theme.primaryColor "4db8a7" -- --verba_port $VERBA_PORT --verba_base_url $BASE_VERBA_API_URL  >> streamlit.$1.log 2>&1 &

# Wait for Streamlit to start
sleep 1

echo "Streamlit started"