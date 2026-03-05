#!/bin/bash
# Test Runner Script
# Runs all tests with proper configuration

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "                    Running Test Suite                          "
echo "═══════════════════════════════════════════════════════════════"

# Configuration
TEST_DIR="e2e"
REPORT_DIR="test-results"
COVERAGE_DIR="coverage"

# Parse arguments
TEST_TYPE="${1:-all}"
HEADLESS="${2:-true}"

# Create directories
mkdir -p $REPORT_DIR
mkdir -p $COVERAGE_DIR

# Run tests based on type
run_unit_tests() {
    echo "Running unit tests..."
    PYTHONPATH=./src pytest tests/orchestration/ -v --tb=short
}

run_api_tests() {
    echo "Running API tests..."
    PYTHONPATH=./src pytest tests/orchestration/test_api.py -v --tb=short
}

run_e2e_tests() {
    echo "Running E2E tests..."
    cd webapps/seeagent-webui

    # Check if dev server is running
    if ! curl -s http://localhost:5175 > /dev/null 2>&1; then
        echo "Starting dev server..."
        pnpm dev &
        DEV_PID=$!
        sleep 10
    fi

    # Run Playwright tests
    npx playwright test --reporter=html

    # Cleanup dev server if we started it
    if [ ! -z "$DEV_PID" ]; then
        kill $DEV_PID 2>/dev/null || true
    fi

    cd ../..
}

run_demo_skill_tests() {
    echo "Running demo skill tests..."
    PYTHONPATH=./src pytest tests/orchestration/test_demo_skills.py -v --tb=short
}

run_integration_tests() {
    echo "Running integration tests..."
    PYTHONPATH=./src pytest tests/orchestration/test_integration.py tests/orchestration/test_e2e.py -v --tb=short
}

# Main execution
case $TEST_TYPE in
    "unit")
        run_unit_tests
        ;;
    "api")
        run_api_tests
        ;;
    "e2e")
        run_e2e_tests
        ;;
    "demo")
        run_demo_skill_tests
        ;;
    "integration")
        run_integration_tests
        ;;
    "all")
        echo "Running all tests..."
        run_unit_tests
        run_api_tests
        run_demo_skill_tests
        run_integration_tests
        run_e2e_tests
        ;;
    *)
        echo "Unknown test type: $TEST_TYPE"
        echo "Usage: $0 [unit|api|e2e|demo|integration|all] [headless|headed]"
        exit 1
        ;;
esac

echo "═══════════════════════════════════════════════════════════════"
echo "                    Tests Complete                              "
echo "═══════════════════════════════════════════════════════════════"