#!/bin/bash

# Start continuous monitoring service
# This will run in the background and output buy/sell recommendations to docker logs

echo "Starting AI Stock Monitor..."
echo ""
echo "The monitor will:"
echo "  - Check Bitcoin and selected stocks every 5 minutes"
echo "  - Output BUY/SELL recommendations to docker logs"
echo "  - Run continuously until stopped"
echo ""
echo "View logs with:"
echo "  docker logs -f ai-stock-monitor"
echo ""
echo "Stop monitoring with:"
echo "  docker-compose down monitor"
echo ""

# Start the monitor service
docker-compose up -d monitor

echo ""
echo "✅ Monitor started!"
echo ""
echo "View live logs:"
echo "  docker logs -f ai-stock-monitor"
echo ""
