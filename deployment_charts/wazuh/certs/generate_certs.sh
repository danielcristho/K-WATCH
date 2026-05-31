#!/bin/bash
# Generate self-signed certificates for Wazuh components
# Run this script before deploying Wazuh

set -euo pipefail

CERTS_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$CERTS_DIR"

echo "Generating Wazuh certificates..."

# Generate Root CA
openssl genrsa -out root-ca-key.pem 2048
openssl req -new -x509 -sha256 -key root-ca-key.pem -out root-ca.pem -days 730 \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=K-IDS/OU=Research/CN=Wazuh Root CA"

# Generate Indexer certificate
openssl genrsa -out node-key.pem 2048
openssl req -new -key node-key.pem -out node.csr \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=K-IDS/OU=Research/CN=wazuh-indexer"
cat > node-ext.cnf << EOF
[v3_req]
subjectAltName = @alt_names
[alt_names]
DNS.1 = wazuh-indexer
DNS.2 = wazuh-indexer-0.wazuh-indexer
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF
openssl x509 -req -in node.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial \
  -out node.pem -days 730 -sha256 -extensions v3_req -extfile node-ext.cnf

# Generate Admin certificate (for indexer security plugin)
openssl genrsa -out admin-key.pem 2048
openssl req -new -key admin-key.pem -out admin.csr \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=K-IDS/OU=Research/CN=admin"
openssl x509 -req -in admin.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial \
  -out admin.pem -days 730 -sha256

# Generate Manager certificate
openssl genrsa -out manager-key.pem 2048
openssl req -new -key manager-key.pem -out manager.csr \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=K-IDS/OU=Research/CN=wazuh-manager"
cat > manager-ext.cnf << EOF
[v3_req]
subjectAltName = @alt_names
[alt_names]
DNS.1 = wazuh-manager
DNS.2 = wazuh-manager-0.wazuh-manager
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF
openssl x509 -req -in manager.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial \
  -out manager.pem -days 730 -sha256 -extensions v3_req -extfile manager-ext.cnf

# Generate Dashboard certificate
openssl genrsa -out dashboard-key.pem 2048
openssl req -new -key dashboard-key.pem -out dashboard.csr \
  -subj "/C=ID/ST=Jakarta/L=Jakarta/O=K-IDS/OU=Research/CN=wazuh-dashboard"
cat > dashboard-ext.cnf << EOF
[v3_req]
subjectAltName = @alt_names
[alt_names]
DNS.1 = wazuh-dashboard
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF
openssl x509 -req -in dashboard.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial \
  -out dashboard.pem -days 730 -sha256 -extensions v3_req -extfile dashboard-ext.cnf

# Cleanup CSR files
rm -f *.csr *.cnf *.srl

echo ""
echo "Certificates generated successfully!"
echo ""
echo "Next steps - create Kubernetes secrets:"
echo ""
echo "  kubectl create namespace wazuh"
echo ""
echo "  kubectl -n wazuh create secret generic indexer-certs \\"
echo "    --from-file=root-ca.pem --from-file=node.pem \\"
echo "    --from-file=node-key.pem --from-file=admin.pem \\"
echo "    --from-file=admin-key.pem"
echo ""
echo "  kubectl -n wazuh create secret generic manager-certs \\"
echo "    --from-file=root-ca.pem --from-file=manager.pem \\"
echo "    --from-file=manager-key.pem"
echo ""
echo "  kubectl -n wazuh create secret generic dashboard-certs \\"
echo "    --from-file=root-ca.pem --from-file=dashboard.pem \\"
echo "    --from-file=dashboard-key.pem"
