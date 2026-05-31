#!/bin/bash

# =============================================================================
# Usage:
#   ./collect_data.sh [--sessions N] [--interval SECONDS] [--stimulate]
#
# Example:
#   ./collect_data.sh --sessions 5 --interval 300 --stimulate
#   ./collect_data.sh --sessions 10 --interval 180
# =============================================================================

set -euo pipefail

# Constants
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KUBECONFIG_PATH="$(cd "$SCRIPT_DIR/../.." && pwd)/config/kubeconfig"
RAW_LOGS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/raw_logs"

SESSIONS=5
INTERVAL=300        # seconds between sessions (5 minutes)
STIMULATE=false
TETRAGON_TAIL=0     # 0 = all logs since last collection

# Colors constants
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%H:%M:%S') $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $(date '+%H:%M:%S') $*"; }

# Retry helper for kubectl
with_retry() {
    local max_attempts=3
    local timeout=5
    local attempt=1
    local exitCode=0

    while [ $attempt -le $max_attempts ]; do
        if "$@"; then
            return 0
        fi
        exitCode=$?
        log_warn "Command '$*' failed (attempt $attempt/$max_attempts). Retrying in ${timeout}s..."
        sleep $timeout
        attempt=$((attempt + 1))
        timeout=$((timeout * 2))
    done

    log_error "Command '$*' failed after $max_attempts attempts."
    return $exitCode
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --sessions)   SESSIONS="$2"; shift 2 ;;
        --interval)   INTERVAL="$2"; shift 2 ;;
        --stimulate)  STIMULATE=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--sessions N] [--interval SECONDS] [--stimulate]"
            echo ""
            echo "Options:"
            echo "  --sessions N       Total session that will be collected (default: 5)"
            echo "  --interval SECS    Interval per session in seconds (default: 300)"
            echo "  --stimulate        Run workload stimulators during collection (default: false)"
            echo ""
            echo "Example:"
            echo "  $0 --sessions 5 --interval 300 --stimulate"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

export KUBECONFIG="$KUBECONFIG_PATH"

# Setup Output Directory
mkdir -p "$RAW_LOGS_DIR/sessions"

# Pre-flight Checks
preflight_check() {
    log_step "Running pre-flight checks..."

    # Check kubectl connectivity
    if ! kubectl get nodes &>/dev/null; then
        log_error "Cannot connect to cluster. Check KUBECONFIG."
        exit 1
    fi
    log_info "Cluster connection: OK"

    # Check Tetragon is running
    TETRAGON_PODS=$(kubectl -n kube-system get pods -l app.kubernetes.io/name=tetragon -o name 2>/dev/null | wc -l)
    if [ "$TETRAGON_PODS" -eq 0 ]; then
        log_error "Tetragon is not running!"
        exit 1
    fi
    log_info "Tetragon pods: $TETRAGON_PODS"

    # Check Cilium/Hubble is running
    CILIUM_PODS=$(kubectl -n kube-system get pods -l k8s-app=cilium -o name 2>/dev/null | wc -l)
    if [ "$CILIUM_PODS" -eq 0 ]; then
        log_error "Cilium is not running!"
        exit 1
    fi
    log_info "Cilium pods: $CILIUM_PODS"

    # Check workloads
    echo ""
    log_step "Workload status:"

    echo -e "${BLUE}  Benign workloads:${NC}"
    kubectl -n benign-workloads get pods --no-headers 2>/dev/null | while read -r line; do
        echo "    $line"
    done

    echo -e "${RED}  Malicious workloads:${NC}"
    kubectl -n malicious get pods --no-headers 2>/dev/null | while read -r line; do
        echo "    $line"
    done

    echo ""

    # Count active pods per namespace
    BENIGN_RUNNING=$(kubectl -n benign-workloads get pods --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    MALICIOUS_RUNNING=$(kubectl -n malicious get pods --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)

    log_info "Running pods - Benign: $BENIGN_RUNNING, Malicious: $MALICIOUS_RUNNING"

    if [ "$BENIGN_RUNNING" -lt 3 ]; then
        log_warn "Very few benign pods running. Data diversity will be limited."
    fi
    if [ "$MALICIOUS_RUNNING" -lt 2 ]; then
        log_warn "Very few malicious pods running. Data diversity will be limited."
    fi
}

# Stimulate Workloads
stimulate_workloads() {
    log_step "Stimulating workloads to generate diverse syscall/network patterns..."

    # Flask-Todo: CRUD ops
    FLASK_SVC=$(kubectl -n benign-workloads get svc flask-todo -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    if [ -n "$FLASK_SVC" ]; then
        log_info "Stimulating flask-todo at $FLASK_SVC:5000..."
        kubectl -n benign-workloads run --rm -i --restart=Never \
            stimulator-flask-"$(date +%s)" --image=curlimages/curl -- \
            sh -c "
                for i in \$(seq 1 10); do
                    # CREATE
                    curl -s -X POST http://flask-todo:5000/ -d \"content=Task_\"\$i 2>/dev/null || true
                    # READ
                    curl -s -o /dev/null http://flask-todo:5000/ || true
                    # UPDATE (simulating id)
                    curl -s -X POST http://flask-todo:5000/update/\$i -d \"content=Updated_\"\$i 2>/dev/null || true
                    # DELETE
                    if [ \$((i % 2)) -eq 0 ]; then
                        curl -s -o /dev/null http://flask-todo:5000/delete/\$((i-1)) 2>/dev/null || true
                    fi
                    sleep 1
                done
            " &>/dev/null &
    fi

    # WordPress: Browse & write operations
    WP_SVC=$(kubectl -n benign-workloads get svc wordpress-app -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    if [ -n "$WP_SVC" ]; then
        log_info "Stimulating wordpress at $WP_SVC:80..."
        kubectl -n benign-workloads run --rm -i --restart=Never \
            stimulator-wp-"$(date +%s)" --image=curlimages/curl -- \
            sh -c "
                for i in \$(seq 1 30); do
                    curl -s -o /dev/null http://wordpress-app/ || true
                    curl -s -o /dev/null http://wordpress-app/wp-login.php || true
                    curl -s -o /dev/null http://wordpress-app/wp-admin/ || true
                    curl -s -o /dev/null http://wordpress-app/?p=\$i || true
                    sleep 1
                done
            " &>/dev/null &
    fi

    # Memcached: set/get operations
    MEMCACHED_SVC=$(kubectl -n benign-workloads get svc memcached-service -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    if [ -n "$MEMCACHED_SVC" ]; then
        log_info "Stimulating memcached at $MEMCACHED_SVC:11211..."
        kubectl -n benign-workloads run --rm -i --restart=Never \
            stimulator-mc-"$(date +%s)" --image=busybox -- \
            sh -c "
                for i in \$(seq 1 50); do
                    echo -e 'set key_'\$i' 0 60 5\r\nhello\r' | nc -w1 memcached-service 11211 || true
                    echo -e 'get key_'\$i'\r' | nc -w1 memcached-service 11211 || true
                    sleep 0.5
                done
                echo -e 'stats\r' | nc -w1 memcached-service 11211 || true
            " &>/dev/null &
    fi

    # Media Streaming: HTTP requests
    MEDIA_SVC=$(kubectl -n benign-workloads get svc media-service -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    if [ -n "$MEDIA_SVC" ]; then
        log_info "Stimulating media-streaming at $MEDIA_SVC:80..."
        kubectl -n benign-workloads run --rm -i --restart=Never \
            stimulator-media-"$(date +%s)" --image=curlimages/curl -- \
            sh -c "
                for i in \$(seq 1 20); do
                    curl -s -o /dev/null http://media-service/ || true
                    sleep 1
                done
            " &>/dev/null &
    fi

    # Web-Serving: Creat HTTP requests
    WEB_SVC=$(kubectl -n benign-workloads get svc web-service -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    if [ -n "$WEB_SVC" ]; then
        log_info "Stimulating web-serving at $WEB_SVC:80..."
        kubectl -n benign-workloads run --rm -i --restart=Never \
            stimulator-web-"$(date +%s)" --image=curlimages/curl -- \
            sh -c "
                for i in \$(seq 1 20); do
                    curl -s -o /dev/null http://web-service/ || true
                    sleep 1
                done
            " &>/dev/null &
    fi

    # MariaDB: Run sysbench if Job is completed, re-run
    MARIADB_SVC=$(kubectl -n benign-workloads get svc mariadb-sysbench-service -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    if [ -n "$MARIADB_SVC" ]; then
        log_info "Stimulating mariadb via direct SQL queries..."
        kubectl -n benign-workloads run --rm -i --restart=Never \
            stimulator-db-"$(date +%s)" --image=mariadb:10.6 -- \
            sh -c "
                for i in \$(seq 1 20); do
                    mysql -h mariadb-sysbench-service -u root -pkids_password ids_test \
                        -e 'CREATE TABLE IF NOT EXISTS t_\${i} (id INT PRIMARY KEY AUTO_INCREMENT, data VARCHAR(255)); INSERT INTO t_\${i} (data) VALUES (\"test_data_\${i}\"); SELECT * FROM t_\${i}; DROP TABLE t_\${i};' 2>/dev/null || true
                    sleep 1
                done
            " &>/dev/null &
    fi

    log_info "Workload stimulators launched (running in background)."
    log_info "Waiting 60 seconds for stimulators to generate traffic..."
    sleep 60
}


#Collect Tetragon Logs
collect_tetragon() {
    local session_id="$1"
    local output_file="$RAW_LOGS_DIR/sessions/tetragon_session_${session_id}.json"

    log_info "Collecting Tetragon logs (session $session_id)..."

    # Collect from ALL tetragon pods (daemonset), use --since for
    # get log since last interval + buffer
    local since_seconds=$((INTERVAL + 60))

    # Collect from all tetragon pods, merge into single file
    > "$output_file" # truncate
    local pods
    pods=$(with_retry kubectl -n kube-system get pods -l app.kubernetes.io/name=tetragon -o name)
    for pod in $pods; do
        pod_name=$(basename "$pod")
        log_info "  Collecting from $pod_name..."
        kubectl -n kube-system logs "$pod" -c export-stdout \
            --since="${since_seconds}s" \
            2>/dev/null >> "$output_file" || true
    done

    local line_count
    line_count=$(wc -l < "$output_file")
    log_info "  Tetragon session $session_id: $line_count lines collected"
}

# Collect Hubble Logs
collect_hubble() {
    local session_id="$1"
    local output_file="$RAW_LOGS_DIR/sessions/hubble_session_${session_id}.json"

    log_info "Collecting Hubble logs (session $session_id)..."

    # Collect from cillium events.log
    > "$output_file" # truncate
    local pods
    pods=$(with_retry kubectl -n kube-system get pods -l k8s-app=cilium -o name)
    local pod
    pod=$(echo "$pods" | head -n 1)

    if [ -n "$pod" ]; then
        pod_name=$(basename "$pod")
        log_info "  Collecting from $pod_name..."
        kubectl -n kube-system exec "$pod" -- \
            cat /var/run/cilium/hubble/events.log \
            2>/dev/null >> "$output_file" || true
    fi

    local line_count
    line_count=$(wc -l < "$output_file")
    log_info "  Hubble session $session_id: $line_count lines collected"
}

# Merge all session logs
merge_sessions() {
    log_step "Merging all sessions into consolidated files..."

    # Merge Tetragon
    local tetragon_merged="$RAW_LOGS_DIR/tetragon.json"
    > "$tetragon_merged"  # truncate
    for f in "$RAW_LOGS_DIR/sessions"/tetragon_session_*.json; do
        if [ -f "$f" ]; then
            cat "$f" >> "$tetragon_merged"
        fi
    done
    local tetragon_lines
    tetragon_lines=$(wc -l < "$tetragon_merged")
    log_info "Merged Tetragon: $tetragon_lines total lines"

    # Merge Hubble — deduplicate by sorting unique lines
    local hubble_merged="$RAW_LOGS_DIR/hubble.json"
    > "$hubble_merged"  # truncate

    for f in "$RAW_LOGS_DIR/sessions"/hubble_session_*.json; do
        if [ -f "$f" ]; then
            cat "$f" >> "$hubble_merged.tmp"
        fi
    done

    if [ -f "$hubble_merged.tmp" ]; then
        sort -u "$hubble_merged.tmp" > "$hubble_merged"
        rm -f "$hubble_merged.tmp"
    fi

    local hubble_lines
    hubble_lines=$(wc -l < "$hubble_merged")
    log_info "Merged Hubble: $hubble_lines total lines (deduplicated)"
}

# Summary
print_summary() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN} Collection Summary${NC}"
    echo "=========================================="
    echo ""

    echo "Sessions collected: $SESSIONS"
    echo "Interval between sessions: ${INTERVAL}s"
    echo ""

    echo "Per-session files:"
    for f in "$RAW_LOGS_DIR/sessions"/*.json; do
        if [ -f "$f" ]; then
            local lines
            lines=$(wc -l < "$f")
            echo "  $(basename "$f"): $lines lines"
        fi
    done

    echo ""
    echo "Merged files:"
    for f in "$RAW_LOGS_DIR"/tetragon.json "$RAW_LOGS_DIR"/hubble.json; do
        if [ -f "$f" ]; then
            local lines
            lines=$(wc -l < "$f")
            local size
            size=$(du -h "$f" | cut -f1)
            echo "  $(basename "$f"): $lines lines ($size)"
        fi
    done

    echo ""
    echo -e "${GREEN}Done!${NC} You can now run the pre-processing notebook."
    echo ""
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo -e "${CYAN} K-IDS Multi-Session Data Collector${NC}"
    echo "=========================================="
    echo ""
    echo "  Sessions  : $SESSIONS"
    echo "  Interval  : ${INTERVAL}s"
    echo "  Stimulate : $STIMULATE"
    echo "  Output    : $RAW_LOGS_DIR"
    echo ""

    preflight_check

    echo ""
    log_step "Starting data collection ($SESSIONS sessions, ${INTERVAL}s interval)..."
    echo ""

    for session in $(seq 1 "$SESSIONS"); do
        echo ""
        echo -e "${BLUE}──────────────────────────────────────────${NC}"
        log_step "Session $session/$SESSIONS"
        echo -e "${BLUE}──────────────────────────────────────────${NC}"

        # Stimulate workloads if flag is set
        if [ "$STIMULATE" = true ]; then
            stimulate_workloads
        fi

        # Collect logs
        collect_tetragon "$session"
        collect_hubble "$session"

        # Wait between sessions (except for the last one)
        if [ "$session" -lt "$SESSIONS" ]; then
            log_info "Waiting ${INTERVAL}s before next session..."
            sleep "$INTERVAL"
        fi
    done

    echo ""
    merge_sessions
    print_summary
}

main
