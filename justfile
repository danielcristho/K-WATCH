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

# Tarik log mentah dari cluster
data-pull:
    kubectl -n kube-system exec ds/cilium -- cat /var/run/cilium/hubble/events.log > events.json

# Konversi log ke CSV (setelah di-pull)
to-csv input="events.json" output="dataset.csv":
    python3 feature_engineering/json_to_csv.py {{input}} {{output}}

# Jalankan keduanya sekaligus
collect-data: data-pull
    @just to-csv events.json dataset.csv
    @echo "Dataset siap di: dataset.csv"

