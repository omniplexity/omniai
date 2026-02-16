#!/bin/bash
# Start OmniAI Backend with ngrok Tunnel
# Usage: ./start-backend.sh

set -e

echo "=============================================="
echo "  OmniAI Backend + ngrok Tunnel Starter"
echo "=============================================="

# Check if ngrok auth token is set
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo ""
    echo "ERROR: NGROK_AUTHTOKEN is not set"
    echo ""
    echo "Please set your ngrok auth token:"
    echo "  export NGROK_AUTHTOKEN=your_token_here"
    echo ""
    echo "Or add it to the .env file:"
    echo "  NGROK_AUTHTOKEN=your_token_here"
    echo ""
    echo "Get your free token from: https://dashboard.ngrok.com/auth"
    exit 1
fi

echo "Building and starting containers..."
docker-compose -f docker-compose.backend.yml up --build -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "=============================================="
echo "  Services Started!"
echo "=============================================="
echo ""
echo "Local Backend:      http://localhost:8000"
echo "ngrok Dashboard:   http://localhost:4040"
echo ""
echo "To get your public URL, run:"
echo "  curl -s http://localhost:4040/api/tunnels | grep -o 'https://[a-z0-9-]*\.ngrok-free\.app'"
echo ""
echo "Or check the ngrok dashboard at http://localhost:4040"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.backend.yml logs -f"
echo ""
echo "To stop:"
echo "  docker-compose -f docker-compose.backend.yml down"
echo "=============================================="
