#!/bin/bash

# Automation script for scheduled stock analysis
# This script can be run via cron or manually for automated analysis

set -e

IMAGE_NAME="ai-stock-checker"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
OUTPUT_DIR="./analysis_reports"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "AI Stock Checker - Automated Analysis"
echo "Timestamp: $TIMESTAMP"
echo "=========================================="
echo ""

# Build the image if needed
if ! docker images | grep -q "$IMAGE_NAME"; then
    echo "Building Docker image..."
    docker build -t "$IMAGE_NAME" .
    echo ""
fi

# Function to run analysis and save output
run_analysis() {
    local command="$1"
    local output_file="$2"

    echo "Running: $command"
    docker run --rm --network host "$IMAGE_NAME" $command > "$OUTPUT_DIR/$output_file" 2>&1
    echo "Output saved to: $OUTPUT_DIR/$output_file"
    echo ""
}

# 1. Analyze Bitcoin
echo "1. Analyzing Bitcoin for investment..."
run_analysis "python3 -m stock_checker.cli bitcoin --analyze" "bitcoin_${TIMESTAMP}.txt"

# 2. Get top S&P 500 movers
echo "2. Fetching top 10 S&P 500 movers..."
run_analysis "python3 -m stock_checker.cli movers -l 10 -p 1d" "sp500_movers_${TIMESTAMP}.txt"

# 3. Check specific high-profile stocks (optional)
echo "3. Analyzing key tech stocks..."
for symbol in AAPL MSFT GOOGL AMZN TSLA; do
    run_analysis "python3 -m stock_checker.cli info $symbol" "${symbol}_${TIMESTAMP}.txt"
done

echo "=========================================="
echo "Analysis Complete!"
echo "Reports saved in: $OUTPUT_DIR"
echo "=========================================="
echo ""
echo "Latest reports:"
ls -lht "$OUTPUT_DIR" | head -10
