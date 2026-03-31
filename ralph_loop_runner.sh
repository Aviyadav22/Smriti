#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# RALPH LOOP RUNNER — Launch overnight codebase audit
# ═══════════════════════════════════════════════════════════════
#
# Usage:
#   chmod +x ralph_loop_runner.sh
#   ./ralph_loop_runner.sh              # Run in foreground
#   ./ralph_loop_runner.sh --background # Run in background (overnight)
#   ./ralph_loop_runner.sh --status     # Check if running
#   ./ralph_loop_runner.sh --stop       # Stop the loop
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCANNER="$SCRIPT_DIR/ralph_loop_scanner.py"
CONFIG="$SCRIPT_DIR/ralph_loop_config.json"
OUTPUT_DIR="$SCRIPT_DIR/ralph_loop_reports"
LOG_FILE="$OUTPUT_DIR/ralph_loop.log"
PID_FILE="$OUTPUT_DIR/ralph_loop.pid"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# ── Functions ──

start_foreground() {
    echo "═══════════════════════════════════════════════════════════"
    echo "  RALPH LOOP — Starting in foreground"
    echo "  Output: $OUTPUT_DIR"
    echo "  Log: $LOG_FILE"
    echo "  Press Ctrl+C to stop"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    python3 "$SCANNER" "$CONFIG" 2>&1 | tee "$LOG_FILE"
}

start_background() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "⚠️  Ralph Loop is already running (PID: $PID)"
            echo "    Use --stop to stop it first."
            exit 1
        fi
    fi

    echo "═══════════════════════════════════════════════════════════"
    echo "  RALPH LOOP — Starting in background"
    echo "  Output: $OUTPUT_DIR"
    echo "  Log: $LOG_FILE"
    echo ""
    echo "  Monitor with:  tail -f $LOG_FILE"
    echo "  Stop with:     $0 --stop"
    echo "  Status:        $0 --status"
    echo "═══════════════════════════════════════════════════════════"

    nohup python3 "$SCANNER" "$CONFIG" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo ""
    echo "✅ Started with PID: $(cat "$PID_FILE")"
    echo "   Run 'tail -f $LOG_FILE' to watch progress"
}

check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ Ralph Loop is RUNNING (PID: $PID)"
            echo ""
            echo "Latest output:"
            tail -5 "$LOG_FILE" 2>/dev/null
            echo ""
            # Show checkpoint progress
            LATEST_CHECKPOINT=$(ls -t "$OUTPUT_DIR"/checkpoint_iter_*.json 2>/dev/null | head -1)
            if [ -n "$LATEST_CHECKPOINT" ]; then
                echo "Latest checkpoint: $LATEST_CHECKPOINT"
                python3 -c "
import json
with open('$LATEST_CHECKPOINT') as f:
    d = json.load(f)
print(f'  Iteration: {d[\"iteration\"]}')
print(f'  Elapsed: {d[\"elapsed_hours\"]:.2f} hours')
print(f'  Issues found: {d[\"total_issues\"]}')
" 2>/dev/null
            fi
        else
            echo "❌ Ralph Loop is NOT running (stale PID: $PID)"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ Ralph Loop is NOT running (no PID file found)"
    fi
}

stop_loop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping Ralph Loop (PID: $PID)..."
            kill "$PID"
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                echo "Force killing..."
                kill -9 "$PID"
            fi
            rm -f "$PID_FILE"
            echo "✅ Stopped."
            echo ""
            echo "Partial results may be in: $OUTPUT_DIR"
        else
            echo "Process already stopped."
            rm -f "$PID_FILE"
        fi
    else
        echo "No running instance found."
    fi
}

# ── Main ──

case "${1:-}" in
    --background|-b)
        start_background
        ;;
    --status|-s)
        check_status
        ;;
    --stop|-k)
        stop_loop
        ;;
    --help|-h)
        echo "Usage: $0 [--background|--status|--stop|--help]"
        echo ""
        echo "  (no args)     Run in foreground"
        echo "  --background  Run in background (for overnight)"
        echo "  --status      Check if running"
        echo "  --stop        Stop the loop"
        ;;
    *)
        start_foreground
        ;;
esac
