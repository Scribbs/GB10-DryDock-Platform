# Architecture

## Data Flow

1. **User** submits Docker image reference or GitHub URL via the Streamlit frontend.
2. **Processor** service:
   - Pulls the image (or clones the repository).
   - Runs **Syft** → CycloneDX SBOM.
   - Runs **Trivy** → list of CVE IDs.
   - Builds a `PipelineInput` JSON matching the schema expected by the NVIDIA blueprint.
   - POSTs the job to `/v1/workflow/async`.
3. **NVIDIA Vulnerability Analysis** (NAT pipeline):
   - CVE Researcher agents gather public intelligence.
   - Container Analyzer inspects the image rootfs (via crane extraction).
   - Exploitability Analyzer determines presence / reachability / exploitability.
   - VEX Categorizer assigns `AFFECTED` / `NOT AFFECTED` + justification.
   - Writes Markdown reports and structured VEX JSON.
4. **Frontend** polls job status and renders the reports (or links to the output volume).

## Why 2-Node GB10?

- Each GB10 has ~128 GB unified memory and a Blackwell GPU.
- Two nodes + QSFP DAC give ~256 GB combined memory and high-bandwidth RoCE for tensor-parallel inference of large NIMs (e.g., 70B+ models).
- Parallelism can also be used to run multiple analysis jobs concurrently or to host both the analysis API and a local NIM.

## Extensibility

- Replace Streamlit with a React/FastAPI frontend that more closely matches the DryDock look-and-feel.
- Add a job queue (Redis + Celery or RQ) for long-running analyses.
- Persist reports in MinIO or a Postgres database for historical search.
- Integrate with existing DryDock / eMASS / SEER workflows by exporting the VEX JSON.
