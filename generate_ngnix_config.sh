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
header_skipped=false
while IFS=, read -r verba_port url_prefix streamlit_port; do
    if [ "$header_skipped" = false ]; then
        header_skipped=true
        continue  # Skip the first line (header)
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

EOF
done < "$csv_file"

# Finish the Nginx configuration file
if [ "$header_written" = true ]; then
    echo "}" >> "$output_file"
fi

# Final information
echo "Nginx configuration file generated: $output_file"
echo "Please place it in /etc/nginx/sites-enabled/reverse-proxy"
echo "Then run \"sudo service nginx reload\" to apply changes"

