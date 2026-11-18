#!/bin/bash
set -e
sudo docker rm -f baseline-server 2>/dev/null || true
sudo docker service rm forecast-app 2>/dev/null || true
sudo docker build -t autoscaling-app:v1 .
sudo docker swarm init 2>/dev/null || true
sudo docker service create --name forecast-app --replicas 1 --publish published=5000,target=5000 autoscaling-app:v1
echo "Forecast autoscaling service created on port 5000."
echo "Test with: curl http://localhost:5000/health"
