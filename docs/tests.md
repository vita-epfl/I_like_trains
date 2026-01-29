# Run all tests
python -m tests.run_performance_tests

# Skip live tests (faster)
python -m tests.run_performance_tests --skip-live

# Only live integration tests
python -m tests.run_performance_tests --live-only

# Specific test types
python -m tests.run_performance_tests --server-only
python -m tests.run_performance_tests --client-only

# Custom iterations/duration
python -m tests.run_performance_tests -i 500 -d 10