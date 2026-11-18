#!/bin/bash
set -e
sudo docker rm -f baseline-server 2>/dev/null || true
sudo docker build -t autoscaling-app:v1 .
sudo docker run -d --restart unless-stopped --name baseline-server -p 5000:5000 autoscaling-app:v1
echo "Baseline server is running on port 5000."
echo "Test with: curl http://localhost:5000/health"
