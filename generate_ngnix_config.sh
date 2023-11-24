#!/bin/bash

# Default values
csv_file=""
output_file=""

# Parse command-line options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --csv_file=*)
            csv_file="${1#*=}"
            ;;
        --output_file=*)
            output_file="${1#*=}"
            ;;
        *)
            echo "Invalid option: $1"
            exit 1
            ;;
    esac
    shift
done

# Delete the output file if it already exists
if [ -f "$output_file" ]; then
    rm "$output_file"
fi


# Check if required options are provided
if [ -z "$csv_file" ] || [ -z "$output_file" ]; then
    echo "Usage: $0 --csv_file=<csv_file> --output_file=<output_file>"
    exit 1
fi

# Start generating the Nginx configuration file and write the header if not already written
header_written=false
if [ ! -f "$output_file" ]; then
    cat <<EOF > "$output_file"
server {
    listen 80;
    server_name localhost;  # Your domain or server IP address
EOF
    header_written=true
fi

# Read the CSV file line by line
{
    read
    while IFS=, read -ra cols; do
        verba_port=${cols[0]}
        url_prefix=${cols[1]}
        streamlit_port=${cols[2]}

        # Skip if any of the fields is empty
        if [ -z "$verba_port" ] || [ -z "$url_prefix" ] || [ -z "$streamlit_port" ]; then
            continue
        fi

        # Generate the corresponding location sections
        cat <<EOF >> "$output_file"
        location /$url_prefix/ {
            proxy_pass http://localhost:$streamlit_port/$url_prefix/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_set_header X-Forwarded-Prefix /$url_prefix;
        }
        location /$url_prefix/_stcore { # add auth headers for websocket
            proxy_pass http://localhost:$streamlit_port/$url_prefix/_stcore;
            proxy_http_version 1.1;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header Host \$host;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Sec-WebSocket-Extensions \$http_sec_websocket_extensions;
            proxy_read_timeout 86400;
        }
        location /$url_prefix/docs {
            proxy_pass http://localhost:$verba_port/docs;
        }
        location /$url_prefix/openapi.json {
            proxy_pass http://localhost:$verba_port/openapi.json;
        }
        location /$url_prefix/api {
            proxy_pass http://localhost:$verba_port/api;
        }

EOF
    done
} < <(tail -n +1 "$csv_file" && echo)

# Finish the Nginx configuration file
if [ "$header_written" = true ]; then
    echo "}" >> "$output_file"
fi

# Final information
echo "Generated nginx configuration file : $output_file"
echo "Please place it in /etc/nginx/sites-enabled/reverse-proxy"
echo "Then run \"sudo service nginx reload\" to apply changes"

