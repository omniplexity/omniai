#!/bin/bash
set -e

echo "Starting OmniAI Backend..."

# Wait for ngrok to be ready if it's running
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check if ngrok is available
    if curl -s http://ngrok:4040/api/tunnels > /dev/null 2>&1; then
        # Get the ngrok HTTPS URL
        NGROK_URL=$(curl -s http://ngrok:4040/api/tunnels | grep -o '"https://[^"]*"' | head -1 | tr -d '"')
        
        if [ -n "$NGROK_URL" ]; then
            echo "Found ngrok URL: $NGROK_URL"
            
            # Update CORS to include ngrok URL
            export OMNI_CORS_ORIGINS="http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174,$NGROK_URL"
            echo "CORS origins updated to: $OMNI_CORS_ORIGINS"
            break
        fi
    fi
    
    echo "Waiting for ngrok... (attempt $((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Warning: ngrok not available, using default CORS"
fi

echo "Starting uvicorn server..."
exec python -m uvicorn omni_backend.main:app --host 0.0.0.0 --port 8000
