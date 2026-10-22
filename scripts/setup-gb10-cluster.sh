#!/usr/bin/env bash
# setup-gb10-cluster.sh
# Run on both Dell GB10 / DGX Spark nodes after the QSFP DAC cable is connected.
set -euo pipefail

echo "=== GB10 2-node cluster setup ==="

# 1. Discover the QSFP interface (example names; verify with ibdev2netdev)
IFACE=$(ibdev2netdev | awk '/Up/ {print $5; exit}')
echo "Detected Up interface: ${IFACE:-unknown}"

# 2. Optional static addressing (adjust as needed)
# NODE_ID is passed as first argument (1 or 2)
NODE_ID=${1:-1}
IP="192.168.100.$((10 + NODE_ID))"

echo "Configuring ${IFACE} with ${IP}/24"
sudo ip addr add "${IP}/24" dev "${IFACE}" || true
sudo ip link set "${IFACE}" up
sudo ip link set "${IFACE}" mtu 9000

# 3. Passwordless SSH (run once, then distribute keys)
if [[ ! -f ~/.ssh/id_rsa ]]; then
  ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi

echo "Add the public key to the other node:"
echo "  ssh-copy-id -i ~/.ssh/id_rsa.pub user@192.168.100.$((10 + (3 - NODE_ID)))"

# 4. NCCL / RDMA hints
echo "Export these for multi-node NIM / vLLM:"
echo "  export NCCL_SOCKET_IFNAME=${IFACE}"
echo "  export NCCL_IB_DISABLE=0"
echo "  export NCCL_P2P_DISABLE=0"

echo "Done. Verify with: ping -c 3 192.168.100.$((10 + (3 - NODE_ID)))"
echo "Then run nccl-tests or your multi-node NIM launch."
