# K-Watch - Just Recipes
# Run tasks with: just <task-name>

export KUBECONFIG := "ansible/kubeconfig"

# Display all available commands
default:
    @just --list

#! Infrastructure

# Provison configuration (k8s setup, cillium, tetragon deployment) 
ansible:
    cd ansible && ansible-playbook -i hosts playbook.yml

# Ping all nodes in the cluster
ansible-ping:
    cd ansible && ansible all -m ping

# Stop AWS cluster
stop-cluster:
    cd terraform && ./manage-cluster.sh stop

# Start AWS cluster
start-cluster:
    cd terraform && ./manage-cluster.sh start

# Check cluster status
cluster-status:
    cd terraform && ./manage-cluster.sh status

# Destroy infrastructure
destroy:
    cd terraform && terraform destroy


#! Helm chart deployment

# Deploy malicious containers
malicious-deploy:
    kubectl create namespace malicious --dry-run=client -o yaml | kubectl apply --validate=false -f -
    helm upgrade --install malicious ./deployment_charts/malicious-containers -n malicious

# Cleanup malicious containers
malicious-clean:
    helm uninstall malicious -n malicious || true
    kubectl delete namespace malicious --ignore-not-found

# Deploy Compromise containers
compromise-deploy:
    kubectl apply -f deployment_charts/compromised-pods/compromised-deployments.yaml

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

#! Hubble & Tetragon data collection

# Collect data: multi-session with workload stimulation (5 sessions, 5 min interval)
collect-data:
    cd feature_engineering && ./collect_data.sh --sessions 5 --interval 300 --stimulate

# Quick collect: fewer sessions for testing (3 sessions, 3 min interval)
collect-quick:
    cd feature_engineering && ./collect_data.sh --sessions 3 --interval 180 --stimulate

# Collect only (no stimulation): useful when workloads are already active
collect-passive sessions="5" interval="300":
    cd feature_engineering && ./collect_data.sh --sessions {{sessions}} --interval {{interval}}


#! Wazuh stach

# Prepare wazuh dedicated node (run after node joins cluster)
wazuh-prepare-node node:
    kubectl taint nodes {{node}} role=siem:NoSchedule --overwrite
    kubectl label nodes {{node}} node-role.kubernetes.io/siem="" --overwrite
    @echo "Node {{node}} prepared for Wazuh deployment"

# Install local-path provisioner for PVCs
wazuh-storage:
    kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
    kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
    kubectl -n local-path-storage patch deployment local-path-provisioner --type=json -p='[{"op":"add","path":"/spec/template/spec/tolerations","value":[{"operator":"Exists"}]}]'
    @echo "Waiting for local-path provisioner..."
    kubectl wait --for=condition=ready pod -l app=local-path-provisioner -n local-path-storage --timeout=120s

# Generate Wazuh TLS certificates
wazuh-certs:
    cd deployment_charts/wazuh/certs && ./generate_certs.sh

# Create Wazuh namespace and secrets
wazuh-secrets:
    kubectl create namespace wazuh --dry-run=client -o yaml | kubectl apply -f -
    kubectl -n wazuh create secret generic indexer-certs \
        --from-file=deployment_charts/wazuh/certs/root-ca.pem \
        --from-file=deployment_charts/wazuh/certs/node.pem \
        --from-file=deployment_charts/wazuh/certs/node-key.pem \
        --from-file=deployment_charts/wazuh/certs/admin.pem \
        --from-file=deployment_charts/wazuh/certs/admin-key.pem \
        --dry-run=client -o yaml | kubectl apply -f -
    kubectl -n wazuh create secret generic manager-certs \
        --from-file=deployment_charts/wazuh/certs/root-ca.pem \
        --from-file=deployment_charts/wazuh/certs/manager.pem \
        --from-file=deployment_charts/wazuh/certs/manager-key.pem \
        --dry-run=client -o yaml | kubectl apply -f -
    kubectl -n wazuh create secret generic dashboard-certs \
        --from-file=deployment_charts/wazuh/certs/root-ca.pem \
        --from-file=deployment_charts/wazuh/certs/dashboard.pem \
        --from-file=deployment_charts/wazuh/certs/dashboard-key.pem \
        --dry-run=client -o yaml | kubectl apply -f -
    @echo "Wazuh secrets created"

# View Wazuh Manager logs
wazuh-logs:
    kubectl -n wazuh logs -l app=wazuh-manager --tail=50

# Deploy Wazuh (full setup: storage + certs + secrets + helm install)
wazuh-deploy:
    just wazuh-storage
    just wazuh-certs
    just wazuh-secrets
    helm upgrade --install wazuh ./deployment_charts/wazuh -n wazuh
    @echo "Wazuh deployed. Waiting for pods..."
    kubectl -n wazuh get pods -w

# Check Wazuh deployment status
wazuh-status:
    @echo "=== Wazuh Pods ==="
    kubectl -n wazuh get pods -o wide
    @echo ""
    @echo "=== Wazuh Services ==="
    kubectl -n wazuh get svc
    @echo ""
    @echo "=== Wazuh PVCs ==="
    kubectl -n wazuh get pvc

# Uninstall Wazuh
wazuh-clean:
    helm uninstall wazuh -n wazuh || true
    kubectl delete namespace wazuh --ignore-not-found
    @echo "Wazuh uninstalled"

# Port-forward Wazuh Dashboard (access at https://localhost:5601)
wazuh-dashboard:
    @echo "Wazuh Dashboard available at https://localhost:5601"
    @echo "Login: admin / SecretPassword"
    kubectl -n wazuh port-forward svc/wazuh-dashboard 5601:443 --address 0.0.0.0

# Initialize Wazuh Indexer security (run once after fresh deploy)
wazuh-init-security:
    @echo "Waiting for indexer to be ready..."
    kubectl -n wazuh wait --for=condition=ready pod/wazuh-indexer-0 --timeout=120s
    kubectl exec -n wazuh wazuh-indexer-0 -- bash -c '\
      export JAVA_HOME=/usr/share/wazuh-indexer/jdk && \
      /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
        -cd /usr/share/wazuh-indexer/config/opensearch-security/ \
        -cacert /usr/share/wazuh-indexer/config/certs/root-ca.pem \
        -cert /usr/share/wazuh-indexer/config/certs/admin.pem \
        -key /usr/share/wazuh-indexer/config/certs/admin-key.pem \
        -h localhost -nhnv'
    kubectl -n wazuh delete pod -l app=wazuh-dashboard
    @echo "Security initialized. Login: admin / admin"

# Check Wazuh Indexer health
wazuh-health:
    kubectl -n wazuh exec -it wazuh-indexer-0 -- \
        curl -sk -u admin:admin https://localhost:9200/_cluster/health?pretty

# Deploy all (wazuh + benign + malicious)
deploy-all:
    just wazuh-deploy
    just benign-deploy
    just malicious
    @echo "=== All deployments complete ==="
    kubectl get pods -A

# Clean all
clean-all:
    just wazuh-clean
    just benign-clean
    just malicious-clean
    @echo "=== All deployments removed ==="
