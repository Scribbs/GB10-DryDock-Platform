# GB10 / Spark 2-Node Vulnerability Analysis Platform (Updated)

Combined deployment of:

- **NVIDIA AI Blueprint for Vulnerability Analysis** (cloned at `./vulnerability-analysis`)
- Platform frontend + SBOM/CVE processor
- **Local multi-node vLLM** on a 2-node Dell GB10 / DGX Spark cluster (QSFP DAC / RoCE)

## Layout on disk

```
~/projects/GB10-DryDock-Platform/
├── docker-compose.combined.yml      # this file + include of upstream
├── docker-compose.vllm-cluster.yml  # 2-node vLLM overlay
├── .env
├── frontend/
├── processor/
├── vulnerability-analysis/          # cloned NVIDIA blueprint
│   └── deploy/docker-compose.yml
└── ...
```

## Quick Start

```bash
cd ~/projects/GB10-DryDock-Platform

# 1. Ensure the blueprint is cloned
# git clone https://github.com/NVIDIA-AI-Blueprints/vulnerability-analysis.git

# 2. Configure
cp .env.example .env
# Edit .env: NVIDIA_API_KEY, TAVILY_API_KEY, HF_TOKEN, interface names, IPs

# 3. (Optional) Bring up only the analysis + frontend
docker compose -f docker-compose.combined.yml up --build -d

# 4. Full stack with local 2-node vLLM
docker compose -f docker-compose.combined.yml -f docker-compose.vllm-cluster.yml up --build -d
```

## 2-Node Cluster Preconfiguration

The Sparks / GB10 nodes must already be connected with a QSFP DAC cable and have:

- Passwordless SSH between nodes
- QSFP interfaces up with static IPs (or link-local) and MTU 9000
- NCCL environment variables pointing at the RoCE interfaces

See:

- `scripts/setup-gb10-cluster.sh`
- `docs/deployment-gb10.md`
- NVIDIA playbooks: https://github.com/NVIDIA/dgx-spark-playbooks (connect-two-sparks, nccl, vllm)

Community multi-node vLLM references used:

- https://github.com/eugr/spark-vllm-docker
- https://github.com/pfn/spark-vllm-compose
- https://github.com/timothystewart6/vllm-gb10

## How the pieces talk

- Frontend / processor → vulnerability-analysis API (`vuln-analysis-api:26466`)
- vulnerability-analysis agents → local vLLM (`vllm-head:8000/v1`) when `NV_BASE_URL` is set accordingly
- vLLM head + worker communicate over the QSFP RoCE link for tensor-parallel inference

## Notes on multi-node placement

Docker Compose on a single host cannot automatically place the worker container on the second physical node. For production 2-node runs use one of:

1. The community `launch-cluster.sh` scripts from eugr/spark-vllm-docker (recommended)
2. Docker contexts / Swarm / Kubernetes
3. Manual `docker run` on each node with matching NCCL settings

The compose overlay is provided as a clear, reviewable template of the required environment and command lines.

## License & Acknowledgements

See `ACKNOWLEDGEMENTS.md` and `licenses/`. The NVIDIA blueprint remains Apache-2.0.
