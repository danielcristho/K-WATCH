# K-IDS - Task Runner
# Run tasks with: just <task-name>

# Display all available commands
default:
    @just --list

# Provison configuration (k8s setup, cillium, tetragon deployment) 
ansible:
    cd ansible && ansible-playbook -i hosts playbook.yml

# Ping all nodes in the cluster
ansible-ping:
    cd ansible && ansible al -m ping

export KUBECONFIG := "ansible/kubeconfig"

# Deploy malicious containers
malicious:
    kubectl create namespace malicious --dry-run=client -o yaml | kubectl apply --validate=false -f -
    helm upgrade --install malicious ./deployment_charts/malicious-containers -n malicious

# Cleanup malicious containers
malicious-clean:
    helm uninstall malicious -n malicious || true
    kubectl delete namespace malicious --ignore-not-found

# Port-forward Hubble Relay & Hubble UI
forward-svc:
    kubectl -n kube-system port-forward service/hubble-relay 4245:80 --address 0.0.0.0 &
    kubectl -n kube-system port-forward service/hubble-ui 12000:80 --address 0.0.0.0 &


# Deploy tetragon policy & bpf-library
tetra-tp:
    kubectl apply -f deployment_charts/tetragon/tracing-policy-ids.yaml
    kubectl apply -f deployment_charts/tetragon/bpf-library-policy.yaml
    kubectl get tracingpolicies

# Check tetragon logs (bpf policy & syscall)
tetra-logs:
    # kubectl -n kube-system logs ds/tetragon -c export-stdout -f | grep process_kprobe
    kubectl -n kube-system logs ds/tetragon -c export-stdout --tail=100 | grep process_kprobe | wc -l
    kubectl -n kube-system logs ds/tetragon -c tetragon --tail=100 | grep -i bpf-library-policy
    kubectl -n kube-system logs ds/tetragon -c tetragon --tail=100 | grep -i ids-syscall-monitoring

# Run benign workload
benign-deploy:
    helm upgrade --install benign deployment_charts/benign-containers/benign-workloads -n benign-workloads --create-namespace

# Delete benign workload
benign-clean:
    helm uninstall benign -n benign-workloads || true
    kubectl delete namespace benign-workloads --ignore-not-found

# Collect data: multi-session with workload stimulation (5 sessions, 5 min interval)
collect-data:
    cd feature_engineering && ./collect_data.sh --sessions 5 --interval 300 --stimulate

# Quick collect: fewer sessions for testing (3 sessions, 3 min interval)
collect-quick:
    cd feature_engineering && ./collect_data.sh --sessions 3 --interval 180 --stimulate

# Collect only (no stimulation): useful when workloads are already active
collect-passive sessions="5" interval="300":
    cd feature_engineering && ./collect_data.sh --sessions {{sessions}} --interval {{interval}}

# Kubeconfig:
kubeconfig:
    export KUBECONFIG=ansible/kubeconfig

