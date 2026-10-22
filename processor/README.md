# Processor: SBOM + CVE → PipelineInput

A small FastAPI service that:

1. Accepts a Docker image reference or GitHub URL.
2. Runs Syft to produce a CycloneDX SBOM.
3. Runs Trivy to extract CVEs.
4. (Optional) Clones the GitHub repo for source context.
5. Constructs the JSON expected by the NVIDIA vulnerability-analysis `/v1/workflow/async` endpoint.
6. Submits the job and returns the job_id.

## Build & Run

```bash
docker build -t vuln-processor .
docker run -p 8080:8080 -v /var/run/docker.sock:/var/run/docker.sock vuln-processor
```

## Endpoints

- `POST /process` – Body: `{"image": "nginx:1.25"}` or `{"github": "https://github.com/org/repo"}`
- `GET /health`

The service expects `syft` and `trivy` binaries in the container image.
