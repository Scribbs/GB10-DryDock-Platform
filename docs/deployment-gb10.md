# GB10 Cluster Deployment

## Physical Connection

1. Power off both Dell Pro Max with GB10 systems.
2. Connect a QSFP112 400G-rated passive DAC cable (0.5 m recommended) between the **same physical QSFP port** on each unit (typically the port closer to the power button / Port 0).
3. Power on both nodes.

## Network Configuration

On each node:

```bash
# Discover interfaces
ibdev2netdev
ip link show

# Example static addressing (run on node 1)
sudo ip addr add 192.168.100.11/24 dev enp1s0f0np0
sudo ip link set enp1s0f0np0 up
sudo ip link set enp1s0f0np0 mtu 9000

# On node 2
sudo ip addr add 192.168.100.12/24 dev enp1s0f0np0
sudo ip link set enp1s0f0np0 up
sudo ip link set enp1s0f0np0 mtu 9000
```

Alternatively use the provided `scripts/setup-gb10-cluster.sh`.

Enable passwordless SSH and verify with `ping` and `ibstat`.

## Software Stack

- NVIDIA Container Toolkit must be installed so containers can access the Blackwell GPU.
- For self-hosted NIMs that benefit from the dual-node memory (up to ~256 GB unified), use multi-node launch modes (vLLM tensor-parallel or NIM multi-node) with `NCCL_SOCKET_IFNAME` pointed at the QSFP interface.
- The analysis pipeline itself can run on a single node while the NIM inference is distributed.

## Docker Compose Overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.gb10.yml up --build -d
```

Adjust GPU reservations and NIM image tags to match the models you have licensed / cached.

## Validation

- `nvidia-smi` on both nodes
- `ibstat` / `ib_write_bw` between nodes
- Submit a small image through the UI and confirm the job reaches the analysis API
