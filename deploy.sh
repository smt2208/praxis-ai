#!/bin/bash

echo "🚀 Starting deployment..."

echo "📥 Fetching and resetting to latest code from git..."
cd "$(dirname "$0")" || exit
git fetch --all
git reset --hard origin/main

echo "📦 Building new Docker image..."
docker build -t praxis-backend .

echo "🛑 Stopping and removing old container..."
docker stop praxis-api-container || true
docker rm praxis-api-container || true

echo "▶️ Starting new container..."
docker run -d --restart unless-stopped --name praxis-api-container -p 8000:8000 --env-file .env praxis-backend

echo "🧹 Pruning unused Docker images..."
docker image prune -f

echo "⏳ Waiting for container to start..."
sleep 3
STATUS=$(docker inspect --format='{{.State.Status}}' praxis-api-container 2>/dev/null)
echo "Container status: $STATUS"

echo "✅ Deployment complete! Showing recent logs..."
echo "------------------------------------------------"
docker logs --tail 50 praxis-api-container
