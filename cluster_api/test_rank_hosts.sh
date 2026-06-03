#!/bin/bash
# Submit a job and poll until done, then print rank_hosts to verify multi-node execution.
API=http://localhost:8765
KEY=4efed1dd1182568c7a59408f681390647ca21d88954487c6d960e19e1e214901

PAYLOAD='{
  "entrypoint": "run",
  "source_code": "def run(d, t):\n    return {\"evidence\": d, \"sufficient\": True, \"summary\": str(len(d or [])), \"records\": []}\n",
  "input_data": [1, 2, 3, 4, 5, 6],
  "target": {}
}'

echo "=== Submitting job ==="
RESP=$(curl -s -X POST "$API/jobs" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KEY" \
  -d "$PAYLOAD")
echo "Submit response: $RESP"

JOB_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))")
if [ -z "$JOB_ID" ]; then
  echo "ERROR: no job_id returned"
  exit 1
fi
echo "JOB_ID: $JOB_ID"

echo "=== Polling (up to 60s) ==="
for i in $(seq 1 12); do
  sleep 5
  RESULT=$(curl -s "$API/jobs/$JOB_ID" -H "X-Api-Key: $KEY")
  STATUS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))")
  echo "  [$i] status=$STATUS"
  if [ "$STATUS" = "done" ] || [ "$STATUS" = "error" ]; then
    echo "=== Final result ==="
    echo "$RESULT" | python3 -m json.tool
    echo ""
    echo "=== rank_hosts (proof of multi-node) ==="
    echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
rh = d.get('result', {}).get('rank_hosts') or d.get('rank_hosts')
if rh:
    print('rank_hosts:', json.dumps(rh, indent=2))
    hosts = list(rh.values())
    unique = set(hosts)
    print(f'Unique hosts used: {unique}')
    if len(unique) > 1:
        print('CONFIRMED: job ran on MULTIPLE physical nodes')
    else:
        print('WARNING: all ranks on same host -', unique)
else:
    print('rank_hosts not found in result')
"
    exit 0
  fi
done

echo "ERROR: job did not complete in 60s"
curl -s "$API/jobs/$JOB_ID" -H "X-Api-Key: $KEY" | python3 -m json.tool
