#!/bin/bash
# Monitor and restart STT/TTS if audio fails
# Run this in background: ./monitor-audio-health.sh &

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_DIR="$SCRIPT_DIR/../ops"

while true; do
    # Check if STT has audio errors
    stt_error=$(docker compose -f "$OPS_DIR/compose.yml" logs --tail=10 stt 2>&1 | grep -c "Audio capture error")
    
    if [ "$stt_error" -gt 0 ]; then
        echo "[$(date)] Detected STT audio error, restarting..."
        docker compose -f "$OPS_DIR/compose.yml" restart stt
        sleep 5
    fi
    
    # Sleep before next check
    sleep 30
done
