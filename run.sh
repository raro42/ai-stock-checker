#!/bin/bash

# Build and run the AI Stock Checker in a Docker container

set -e

echo "Building Docker image..."
docker build -t ai-stock-checker .

echo ""
echo "Running AI Stock Checker..."
echo "Usage examples:"
echo "  docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL"
echo "  docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL --analyze"
echo "  docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli history TSLA -p 1mo"
echo ""

# Run the container interactively
docker run --rm -it --network host -v "$(pwd):/app" ai-stock-checker bash
