#!/bin/bash
# SSH Tunnel for Remote Ollama Server (bl6.cs.fsu.edu)
# Forwards localhost:11434 -> localhost:11434 on bl6.cs.fsu.edu
# Used for orchestration and MongoDB querying with LLM
# Ollama typically listens on 127.0.0.1:11434 on the target server
# Designed to run with nohup for background operation

TARGET_HOST="bl6.cs.fsu.edu"
TARGET_PORT="11434"
LOCAL_PORT="11434"
TARGET_USER="sai"

# Log file and PID file locations
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/tunnel2.log"
PID_FILE="${SCRIPT_DIR}/tunnel2.pid"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if tunnel is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        log "Tunnel appears to be already running (PID: $OLD_PID)"
        log "If this is incorrect, delete $PID_FILE and try again"
        exit 1
    else
        log "Stale PID file found, removing it"
        rm -f "$PID_FILE"
    fi
fi

log "Starting SSH tunnel for bl6.cs.fsu.edu..."
log "Local port: $LOCAL_PORT"
log "Target: localhost:$TARGET_PORT on $TARGET_USER@$TARGET_HOST"
log "Log file: $LOG_FILE"
log "PID file: $PID_FILE"
log ""

# Check if local port is already in use
if lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    log "ERROR: Port $LOCAL_PORT is already in use"
    exit 1
fi

# Forward to localhost:11434 on bl6.cs.fsu.edu
# Using key-based authentication
ssh -N -L ${LOCAL_PORT}:localhost:${TARGET_PORT} \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o PreferredAuthentications=publickey \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    ${TARGET_USER}@${TARGET_HOST} >> "$LOG_FILE" 2>&1 &

SSH_PID=$!

# Save PID
echo $SSH_PID > "$PID_FILE"

# Wait a moment to check if SSH started successfully
sleep 3

if ps -p $SSH_PID > /dev/null 2>&1; then
    log "Tunnel started successfully (PID: $SSH_PID)"
    log "To stop the tunnel, run: kill $SSH_PID or kill \$(cat $PID_FILE)"
    log "To view logs: tail -f $LOG_FILE"
else
    log "ERROR: Tunnel failed to start. Check $LOG_FILE for details."
    rm -f "$PID_FILE"
    exit 1
fi
