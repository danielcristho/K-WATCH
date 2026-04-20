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

malicious:
    helm upgrade --install malicious ./deploy/malicious-containers

malicious-clean:
    helm uninstall malicious

# Port-forward Hubble Relay & Hubble UI
forward-svc:
    kubectl -n kube-system port-forward service/hubble-relay 4245:80 --address 0.0.0.0 &
    kubectl -n kube-system port-forward service/hubble-ui 12000:80 --address 0.0.0.0 &