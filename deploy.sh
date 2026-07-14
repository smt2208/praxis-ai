#!/bin/bash
set -e  # Exit immediately on any error

echo "🚀 Starting deployment..."

echo "📦 Building new Docker image..."
docker build -t praxis-backend .

echo "🛑 Stopping and removing old container..."
docker stop praxis-api-container || true
docker rm praxis-api-container || true

echo "▶️ Starting new container..."
# --restart unless-stopped ensures the container automatically starts on EC2 reboot
docker run -d \
  --restart unless-stopped \
  --name praxis-api-container \
  -p 8000:8000 \
  --env-file .env \
  praxis-backend

echo "🧹 Pruning unused Docker images..."
docker image prune -f

echo "⏳ Waiting for container to start..."
sleep 5

STATUS=$(docker inspect --format='{{.State.Status}}' praxis-api-container 2>/dev/null)
echo "Container status: $STATUS"

if [ "$STATUS" != "running" ]; then
  echo "❌ Container failed to start! Showing logs..."
  docker logs praxis-api-container
  exit 1
fi

echo "✅ Deployment complete! Showing recent logs..."
echo "------------------------------------------------"
docker logs --tail 50 praxis-api-container
