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

# Deploy malicious containers
malicious:
    kubectl create namespace malicious --dry-run=client -o yaml | kubectl apply -f -
    helm upgrade --install malicious ./deploy/malicious-containers -n malicious

# Cleanup malicious containers
malicious-clean:
    helm uninstall malicious -n malicious || true
    kubectl delete namespace malicious --ignore-not-found

# Port-forward Hubble Relay & Hubble UI
forward-svc:
    kubectl -n kube-system port-forward service/hubble-relay 4245:80 --address 0.0.0.0 &
    kubectl -n kube-system port-forward service/hubble-ui 12000:80 --address 0.0.0.0 &

# Pull the logs (Hubble & Tetragon)
data-pull:
    kubectl -n kube-system exec ds/cilium -- cat /var/run/cilium/hubble/events.log > hubble.json
    kubectl -n kube-system logs ds/tetragon --tail=5000 > tetragon.json

# Process into hybrid dataset (5-gram syscall + network stats)
hybrid-data: data-pull
    python3 feature_engineering/hybrid_processor.py
    @echo "Hybrid dataset ready at: training/hybrid_dataset.csv"

# Legacy: Convert Hubble JSON log to simple CSV
to-csv input="hubble.json" output="dataset.csv":
    python3 feature_engineering/json_to_csv.py {{input}} {{output}}
