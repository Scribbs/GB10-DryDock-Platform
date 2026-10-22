# GB10 Vulnerability Analysis Platform

Deploy the [NVIDIA AI Blueprint for Vulnerability Analysis](https://github.com/NVIDIA-AI-Blueprints/vulnerability-analysis) on a 2-node Dell Pro Max with GB10 (or equivalent Grace Blackwell) cluster, with a web frontend that ingests Docker images and GitHub repositories, generates SBOMs + CVEs, feeds them into the agentic pipeline, and presents contextual exploitability / VEX results in a DryDock-style UI.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────────────┐
│   Web Frontend  │────▶│  SBOM + CVE Processor │────▶│ NVIDIA Vulnerability Analysis │
│  (Streamlit /   │     │  (Syft + Trivy)       │     │  (NAT + NIM, self-hosted)   │
│   FastAPI)      │     │  Clones GitHub repos  │     │  2-node GB10 cluster        │
└─────────────────┘     └──────────────────────┘     └─────────────────────────────┘
         ▲                                                      │
         └──────────────────── Reports / VEX JSON ◀─────────────┘
```

- **Frontend**: Users paste a Docker image reference (`nginx:1.25`) or GitHub URL. Jobs are queued and progress is shown.
- **Processor**: Pulls the image (or clones the repo), runs Syft for SBOM (CycloneDX), Trivy for CVE list, and formats a `PipelineInput` JSON for the NVIDIA blueprint.
- **Analysis**: The official NVIDIA vulnerability-analysis blueprint (Docker Compose) performs multi-agent contextual analysis (presence, reachability, exploitability) and emits cited Markdown reports + VEX classification.
- **Cluster**: Two GB10 nodes connected via QSFP DAC (ConnectX-7) for high-bandwidth RoCE. Ideal for self-hosted NIMs (tensor-parallel across nodes) or parallel job execution. Management traffic stays on the 10 GbE / Ethernet interface.

## Prerequisites

### Hardware
- Two Dell Pro Max with GB10 (or DGX Spark / compatible GB10 systems)
- One QSFP112 400G-rated passive DAC cable (e.g., Amphenol NJAAKK-N911 / NJAAKK0006 or Luxshare LMTQF022-SD-R, 0.5 m)
- Sufficient storage (recommend ≥ 2 TB NVMe per node for model caches + image layers)
- Internet access for initial model pulls and Tavily research (or configure air-gapped mirrors)

### Software
- NVIDIA DGX OS 7 (Ubuntu 24.04 based) or equivalent with NVIDIA drivers + Container Toolkit
- Docker Engine + Compose v2.24+
- NVIDIA API key (for hosted NIMs) **or** local NIM containers
- Tavily API key (for web research in the blueprint)

## Quick Start (Single Node)

```bash
# 1. Clone this repository
git clone <your-fork-or-this-repo>
cd gb10-vuln-analysis-platform

# 2. Configure environment
cp .env.example .env
# Edit .env and set NVIDIA_API_KEY, TAVILY_API_KEY, and any local NIM endpoints

# 3. Bring up the stack
docker compose up --build -d

# 4. Open the UI
# http://localhost:8501  (or the host IP)
```

## 2-Node GB10 Cluster Setup

See [docs/deployment-gb10.md](docs/deployment-gb10.md) for full steps. Summary:

1. Physically connect the two nodes with the QSFP DAC cable (same physical port on each, typically Port 0).
2. Configure the RoCE interfaces (link-local or static 192.168.100.0/24).
3. Enable passwordless SSH between nodes.
4. Run `scripts/setup-gb10-cluster.sh` on both nodes.
5. Use `docker-compose.gb10.yml` overlay to pin NIMs / workers to specific nodes or enable multi-node inference.

## Usage

1. Open the web UI.
2. Enter a Docker image (e.g. `python:3.12-slim`) or a GitHub repository URL.
3. Optionally provide a list of specific CVEs to focus on.
4. Submit the job.
5. The processor generates the SBOM + CVE list and posts a job to the NVIDIA analysis API.
6. View progress and, when complete, the cited reports, VEX status (`AFFECTED` / `NOT AFFECTED`), justification, and downloadable artifacts.

## Project Structure

```
├── README.md
├── ACKNOWLEDGEMENTS.md
├── LICENSE
├── .env.example
├── docker-compose.yml
├── docker-compose.gb10.yml
├── frontend/                 # Streamlit web UI
├── processor/                # Syft + Trivy SBOM/CVE service
├── scripts/                  # Cluster setup and helper scripts
├── docs/
│   ├── architecture.md
│   └── deployment-gb10.md
└── licenses/                 # Upstream license texts
```

## Configuration

Key environment variables (see `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_API_KEY` | Yes* | Credential for NVIDIA NIM endpoints |
| `TAVILY_API_KEY` | Yes | Web research for CVE intel |
| `NV_BASE_URL` | No | Override for self-hosted NIM (default: NVIDIA cloud) |
| `VULN_ANALYSIS_URL` | No | Internal URL of the analysis API |
| `PROCESSOR_IMAGE` | No | Image that runs Syft/Trivy |

\* Not required if fully self-hosting NIMs.

## License & Upstream

This project is a deployment and integration layer. The core vulnerability analysis workflow is the NVIDIA AI Blueprint for Vulnerability Analysis (Apache-2.0). See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) and the `licenses/` directory for full attributions.

## Troubleshooting

- **NIM out of memory on single node**: Use the 2-node cluster with tensor parallelism or smaller models (see NVIDIA NIM support matrix).
- **Image pull failures**: Ensure the processor container has access to the Docker socket or a private registry credentials.
- **Slow first run**: Model downloads and vulnerability database updates (Trivy) can take several minutes.

## Support

This is a reference deployment package. For issues with the upstream NVIDIA blueprint, open an issue on the original repository. For GB10 clustering specifics, refer to NVIDIA DGX Spark / Dell documentation.
