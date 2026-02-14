#!/bin/bash
# Re-ingest all knowledge files into Qdrant
# Run this on EC2 after deploying the new attribute-based tagging feature
#
# Usage:
#   cd /opt/perchspot
#   chmod +x scripts/reingest_knowledge.sh
#   ./scripts/reingest_knowledge.sh

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
KNOWLEDGE_DIR="${KNOWLEDGE_DIR:-/opt/perchspot/backend/knowledge/property}"

echo "=== Knowledge Re-Ingestion Script ==="
echo "API URL: $API_URL"
echo "Knowledge Directory: $KNOWLEDGE_DIR"
echo ""

# Check if API is reachable
echo "Checking API connectivity..."
if ! curl -s -f "$API_URL/api/v1/knowledge/status" -H "X-Admin-Password: $ADMIN_PASSWORD" > /dev/null; then
    echo "ERROR: Cannot connect to API or invalid admin password"
    exit 1
fi
echo "API is reachable."
echo ""

# Get current knowledge status
echo "Current knowledge status:"
curl -s "$API_URL/api/v1/knowledge/status" -H "X-Admin-Password: $ADMIN_PASSWORD" | python3 -m json.tool
echo ""

# Find all .md files in knowledge directory
echo "Finding knowledge files in $KNOWLEDGE_DIR..."
if [ ! -d "$KNOWLEDGE_DIR" ]; then
    echo "ERROR: Knowledge directory not found: $KNOWLEDGE_DIR"
    exit 1
fi

MD_FILES=$(find "$KNOWLEDGE_DIR" -name "*.md" -type f | grep -v "00_MASTER_INDEX.md" | sort)
FILE_COUNT=$(echo "$MD_FILES" | wc -l | tr -d ' ')

echo "Found $FILE_COUNT knowledge files to ingest:"
echo "$MD_FILES" | while read f; do echo "  - $(basename "$f")"; done
echo ""

# Confirm before proceeding
read -p "Proceed with re-ingestion? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Starting ingestion..."
echo ""

# Track job IDs
JOB_IDS=()

# Ingest each file
for FILE in $MD_FILES; do
    FILENAME=$(basename "$FILE")
    echo "Submitting: $FILENAME"

    RESPONSE=$(curl -s "$API_URL/api/v1/knowledge/ingest" \
        -X POST \
        -H "X-Admin-Password: $ADMIN_PASSWORD" \
        -F "file=@$FILE")

    JOB_ID=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")

    if [ -n "$JOB_ID" ]; then
        echo "  Job ID: $JOB_ID"
        JOB_IDS+=("$JOB_ID")
    else
        echo "  ERROR: $RESPONSE"
    fi

    # Small delay to avoid overwhelming the API
    sleep 1
done

echo ""
echo "All jobs submitted. Waiting for completion..."
echo ""

# Wait for all jobs to complete
MAX_WAIT=600  # 10 minutes max
WAIT_INTERVAL=10
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check job statuses
    JOBS_STATUS=$(curl -s "$API_URL/api/v1/knowledge/ingest/jobs" -H "X-Admin-Password: $ADMIN_PASSWORD")

    RUNNING=$(echo "$JOBS_STATUS" | python3 -c "
import json,sys
jobs = json.load(sys.stdin).get('jobs', [])
running = [j for j in jobs if j['status'] == 'running']
print(len(running))
" 2>/dev/null || echo "0")

    if [ "$RUNNING" = "0" ]; then
        echo "All jobs completed!"
        break
    fi

    echo "  $RUNNING jobs still running... (waited ${ELAPSED}s)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "WARNING: Timeout reached. Some jobs may still be running."
fi

echo ""
echo "=== Final Status ==="

# Show final status
curl -s "$API_URL/api/v1/knowledge/status" -H "X-Admin-Password: $ADMIN_PASSWORD" | python3 -m json.tool

echo ""
echo "=== Job Results ==="

# Show job results
curl -s "$API_URL/api/v1/knowledge/ingest/jobs" -H "X-Admin-Password: $ADMIN_PASSWORD" | python3 -c "
import json,sys
jobs = json.load(sys.stdin).get('jobs', [])
for j in jobs[-10:]:  # Last 10 jobs
    status = j['status']
    source = j['source_file']
    if j.get('result'):
        points = j['result'].get('points_ingested', '?')
        print(f'{source}: {status} - {points} points')
    elif j.get('error'):
        print(f'{source}: {status} - ERROR: {j[\"error\"]}')
    else:
        print(f'{source}: {status}')
"

echo ""
echo "Done!"
