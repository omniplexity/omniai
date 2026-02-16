#!/bin/bash
# Startup script that waits for ngrok to be ready and updates CORS

set -e

echo "Waiting for ngrok to be ready..."
sleep 5

# Get the ngrok API URL
NGROK_API="http://ngrok:4040/api/tunnels"
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Try to get tunnel info
    TUNNEL_JSON=$(curl -s $NGROK_API 2>/dev/null || echo '{"tunnels":[]}')
    
    # Extract the first https tunnel URL
    HTTPS_URL=$(echo "$TUNNEL_JSON" | grep -o '"https://[^"]*"' | head -1 | tr -d '"')
    
    if [ -n "$HTTPS_URL" ]; then
        echo "Found ngrok URL: $HTTPS_URL"
        
        # Update CORS in the backend container
        # The backend will pick up this env var on next health check
        echo "Updating CORS to include: $HTTPS_URL"
        export OMNI_CORS_ORIGINS="http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174,$HTTPS_URL"
        
        # Update docker-compose env file for subsequent runs
        echo "OMNI_CORS_ORIGINS=$HTTPS_URL,http://localhost:5173,http://localhost:5174" > .env.cors
        echo "CORS updated successfully!"
        break
    fi
    
    echo "Waiting for ngrok tunnel... (attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Warning: Could not get ngrok URL within timeout"
fi

echo "Starting backend..."
exec "$@"
