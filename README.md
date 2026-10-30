# GB10-DryDock-Platform

Local multi-node deployment of the NVIDIA AI Blueprint for Vulnerability Analysis on a 2-node Dell GB10 (Grace Blackwell) cluster, with a custom processor and web frontend in the style of [DryDock](https://drydock.intelligenesis.us/).

The stack runs the vulnerability-analysis pipeline against local models served by vLLM across the QSFP RoCE interconnect, while a processor service generates SBOMs and CVE lists (Syft + Trivy) and submits properly formatted `PipelineInput` jobs.

## Architecture

- **vLLM head + worker** – multi-node tensor-parallel serving over the QSFP links (10.20.0.11 / 10.20.0.12)
- **vulnerability-analysis API** – NVIDIA blueprint (NAT workflow) listening on port 26466
- **Processor** – FastAPI service that runs Syft/Trivy and posts to the analysis API
- **Frontend** – React UI for submitting images/repos and viewing results
- **Supporting services** – nginx cache, job state, etc.

## Prerequisites

- 2× Dell GB10 nodes with QSFP DAC connected
- Docker + NVIDIA Container Toolkit
- Hugging Face token (for model downloads)
- Docker Hub / registry credentials if pulling private images

## Quick Start

```bash
cd ~/projects/GB10-DryDock-Platform

# Copy and edit environment
cp .env.example .env
# Set HEAD_QSFP_IP, WORKER_QSFP_IP, HF_TOKEN, DEFAULT_MODEL_NAME, etc.

# Bring up the combined stack
docker compose -f docker-compose.combined.yml -f docker-compose.vllm-cluster.yml up --build -d
```

## Per-Image Output Layout

Jobs now write reports under an image-specific directory so multiple images can be analyzed without overwriting results:

```
outputs/<sanitized-image-name>/
├── vulnerability_reports/
├── container_reports/
├── exploitability_reports/
├── vex_results/
└── failed_reports/          # only when present
```

Set `output_dir` in the `PipelineInput` (the processor does this automatically).

## Key Environment Variables

| Variable              | Purpose                              | Example                  |
|-----------------------|--------------------------------------|--------------------------|
| `HEAD_QSFP_IP`        | Head node QSFP address               | `10.20.0.11`             |
| `WORKER_QSFP_IP`      | Worker node QSFP address             | `10.20.0.12`             |
| `DEFAULT_MODEL_NAME`  | Model used by the blueprint          | `nvidia/Qwen3.8-27B-NVFP4` |
| `HF_TOKEN`            | Hugging Face access token            | `hf_...`                 |
| `NCCL_SOCKET_IFNAME`  | RoCE interface                       | `enp1s0f1np1`            |

## Development

See the individual compose files and the `processor/` directory for details.

- `docker-compose.combined.yml` – platform + vulnerability-analysis services
- `docker-compose.vllm-cluster.yml` – vLLM head/worker overlay
- `processor/process.py` – Syft/Trivy → PipelineInput logic

## License & Acknowledgements

This project builds on the [NVIDIA AI Blueprint for Vulnerability Analysis](https://github.com/NVIDIA-AI-Blueprints/vulnerability-analysis). See the upstream repository for license terms and required acknowledgements. The DryDock-style UI and processor are local additions.

## Roadmap

Planned improvements are tracked in [TODO.md](TODO.md).
