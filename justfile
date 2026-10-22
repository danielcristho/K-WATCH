# K-Watch - Just Recipes
# Run tasks with: just <task-name>

export KUBECONFIG := env_var_or_default("KUBECONFIG", justfile_directory() / "ansible/kubeconfig")

# Personal, laptop-specific recipes (gitignored); absent on a fresh clone
import? 'demo.local.just'

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


#! Wazuh stack

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
    just wazuh-rules
    helm upgrade --install wazuh ./deployment_charts/wazuh -n wazuh
    @echo "Wazuh deployed. Waiting for pods..."
    kubectl -n wazuh get pods -w

# K-Watch decoder and rules as a ConfigMap, mounted into the manager so they survive restarts
wazuh-rules:
    kubectl create namespace wazuh --dry-run=client -o yaml | kubectl apply -f -
    kubectl -n wazuh create configmap wazuh-kwatch-rules \
        --from-file=kwatch_decoder.xml=wazuh/rules/kwatch_decoder.xml \
        --from-file=kwatch_rules.xml=wazuh/rules/kwatch_rules.xml \
        --dry-run=client -o yaml | kubectl apply -f -

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
    @echo "Login: admin / the indexerAdmin password in deployment_charts/wazuh/values.yaml"
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
    just malicious-deploy
    @echo "All deployments complete"
    kubectl get pods -A

#! Detector chart

# Deploy detector
detector-deploy:
    kubectl apply -f deployment_charts/k-watch/detector.yaml

# Delete detector
detector-clean:
    kubectl uninstall -f deployment_charts/k-watch/detector.yaml

# Run every detector self-check and test
detector-test:
    #!/usr/bin/env bash
    set -euo pipefail
    cd detector
    for m in core.pipeline sources.tetragon sources.hubble sources.tailer alerting.console \
             tests.test_syscall_map tests.test_alert_schema; do
        printf "%-26s " "$m"
        .venv/bin/python -m "$m"
    done

# Clean all
clean-all:
    just wazuh-clean
    just benign-clean
    just malicious-clean
    just detector-clean
    @echo "=== All charts removed ==="


## DEMO

# Deploy the compromised default-namespace pods (app-server + trojan-agent)
compromise-deploy:
    kubectl apply -f deployment_charts/compromised-pods/compromised_chart.yml

# Port-forward Hubble Relay and Hubble UI
forward-svc:
    kubectl -n kube-system port-forward service/hubble-relay 4245:80 --address 0.0.0.0 &
    kubectl -n kube-system port-forward service/hubble-ui 12000:80 --address 0.0.0.0 &

tetra-mal:
    kubectl -n kube-system get pods -l app.kubernetes.io/name=tetragon -o wide

# Summarise what a pod exec'd and which syscalls it hit, from the Tetragon export log
tetra-events pod lines="80000":
    #!/usr/bin/env bash
    set -eu
    read -r node name < <(kubectl get pod -A -o custom-columns=NODE:.spec.nodeName,N:.metadata.name --no-headers | grep -m1 -- "{{pod}}" | awk '{print $1, $2}')
    [ -n "${node:-}" ] || { echo "no pod matching {{pod}}"; exit 1; }
    tp=$(kubectl -n kube-system get pod -l app.kubernetes.io/name=tetragon --field-selector spec.nodeName="$node" -o jsonpath='{.items[0].metadata.name}')
    echo "pod $name on $node, reading via $tp"
    # kubectl exec writes a harmless stream-close error to stderr when tail ends, drop it
    kubectl -n kube-system exec "$tp" -c export-stdout -- tail -n {{lines}} /var/run/cilium/tetragon/tetragon.log 2>/dev/null \
      | python3 {{justfile_directory()}}/scripts/tetra_summary.py "$name"

# Summarise a pod's network flows (destinations, ports, verdict) from the Hubble export log
hubble-events pod lines="60000":
    #!/usr/bin/env bash
    set -eu
    read -r node name < <(kubectl get pod -A -o custom-columns=NODE:.spec.nodeName,N:.metadata.name --no-headers | grep -m1 -- "{{pod}}" | awk '{print $1, $2}')
    [ -n "${node:-}" ] || { echo "no pod matching {{pod}}"; exit 1; }
    cp=$(kubectl -n kube-system get pod -l k8s-app=cilium --field-selector spec.nodeName="$node" -o jsonpath='{.items[0].metadata.name}')
    echo "pod $name on $node, reading via $cp"
    kubectl -n kube-system exec "$cp" -c cilium-agent -- tail -n {{lines}} /var/run/cilium/hubble/kwatch-workloads.log 2>/dev/null \
      | python3 {{justfile_directory()}}/scripts/hubble_summary.py "$name"
