#!/bin/sh

# Start with the default whitelist
cp /etc/tinyproxy/whitelist.default /etc/tinyproxy/whitelist

# If ADDITIONAL_DOMAINS environment variable is set, add those domains
if [ -n "$ADDITIONAL_DOMAINS" ]; then
    echo "Adding additional domains to whitelist: $ADDITIONAL_DOMAINS"
    # Split the comma-separated list and add each domain
    echo "$ADDITIONAL_DOMAINS" | tr ',' '\n' | while read -r domain; do
        # Trim whitespace
        domain=$(echo "$domain" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        if [ -n "$domain" ]; then
            echo "$domain" >> /etc/tinyproxy/whitelist
        fi
    done
fi

# Start tinyproxy
exec tinyproxy -d