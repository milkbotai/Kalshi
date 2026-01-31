#!/bin/bash
# Run load tests against dashboard

set -euo pipefail

# Configuration
HOST="${LOAD_TEST_HOST:-http://localhost:8501}"
USERS="${LOAD_TEST_USERS:-100}"
SPAWN_RATE="${LOAD_TEST_SPAWN_RATE:-10}"
RUN_TIME="${LOAD_TEST_RUN_TIME:-5m}"
RESULTS_DIR="tests/performance/results"

# Create results directory
mkdir -p "$RESULTS_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="${RESULTS_DIR}/load_test_${TIMESTAMP}.html"

echo "Starting load test..."
echo "Host: $HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE"
echo "Duration: $RUN_TIME"
echo ""

# Run locust
locust -f tests/performance/locustfile.py \
    --host="$HOST" \
    --users="$USERS" \
    --spawn-rate="$SPAWN_RATE" \
    --run-time="$RUN_TIME" \
    --headless \
    --html="$RESULTS_FILE"

echo ""
echo "Load test completed!"
echo "Results saved to: $RESULTS_FILE"

# Parse results and check against targets
echo ""
echo "Performance Summary:"
echo "==================="

# Extract key metrics from results
# (This is a simplified example - actual parsing would be more robust)
if [ -f "$RESULTS_FILE" ]; then
    echo "✓ Results file generated"
    echo "  Open $RESULTS_FILE in a browser to view detailed results"
else
    echo "✗ Results file not found"
    exit 1
fi

# Check if any failures occurred
if grep -q "Failures: 0" "$RESULTS_FILE" 2>/dev/null; then
    echo "✓ No failures detected"
else
    echo "⚠ Some requests failed - review results file"
fi

echo ""
echo "Next steps:"
echo "1. Review detailed results in browser"
echo "2. Compare against baseline in tests/performance/benchmark_results.md"
echo "3. Investigate any performance regressions"
echo "4. Update baseline if performance improved"
