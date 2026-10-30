# TODO – GB10-DryDock-Platform

Items mentioned as desired future work. Ordered roughly by priority / dependency.

## UI / Reports

- [ ] Add a **Reports** tab (or section) on the vulnerability detail page that appears when a job completes.
- [ ] **Overall Findings** summary that lists CVEs grouped by status:
  - EXPLOITABLE (`affected`)
  - NOT EXPLOITABLE (`not_affected`)
  - UNKNOWN / uncertain
- [ ] Report cards that render the Markdown content from the four output directories:
  - `vulnerability_reports/<cve>.md`
  - `container_reports/<image>.md`
  - `exploitability_reports/<cve>_<image>.md`
  - `vex_results/<cve>_<image>.md` (+ JSON sidecar)
- [ ] Link each finding to the existing DryDock-style detail view (`/vulnerability/<id>?filename=...`).
- [ ] Auto-refresh or webhook-driven update when an async job finishes.

## Pipeline & Outputs

- [ ] Fully wire per-image `output_dir` (`outputs/<sanitized-image-name>/...`) through the processor so concurrent runs never collide.
- [ ] Expose the report tree cleanly via the analysis API (or a thin proxy) so the frontend can list and fetch `.md` / `.json` files without hard-coded paths.
- [ ] Optional job-level index file that records image name, digest, CVE list, and final VEX summary for quick UI loading.

## Processor

- [ ] GitHub repository support (clone + source SBOM path) in addition to container images.
- [ ] Configurable analysis URL (remove hard-coded host IP).
- [ ] Better error surfacing when Syft/Trivy or the workflow API fail.
- [ ] Optional explicit CVE list override from the UI.

## vLLM / Cluster

- [ ] Stabilize multi-node Ray join and tool-calling parser (`qwen` vs `hermes`) for the local model.
- [ ] Document the exact `docker-compose.vllm-cluster.yml` settings that work with the QSFP RoCE links.
- [ ] Consider the official NIM overlay as an alternative to the community vLLM image once multi-node is solid.

## General

- [ ] Clean `.gitignore` (outputs, `.bak` files, accidental curl artifacts).
- [ ] Health-check / readiness dashboard for the full stack (vLLM, API, processor, frontend).
- [ ] Example curl / Postman collection for submitting a job and retrieving reports.
- [ ] License and upstream acknowledgement file that can be included in any redistributed package.
