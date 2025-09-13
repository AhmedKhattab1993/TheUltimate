#!/bin/bash
# Test if Docker containers can run in parallel

echo "Starting 3 Docker containers in parallel..."
start_time=$(date +%s)

# Run 3 containers in parallel
docker run --rm alpine sleep 5 &
docker run --rm alpine sleep 5 &
docker run --rm alpine sleep 5 &

# Wait for all to complete
wait

end_time=$(date +%s)
duration=$((end_time - start_time))

echo "Total time: ${duration} seconds"
echo "If parallel: ~5 seconds"
echo "If serial: ~15 seconds"