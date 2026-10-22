"""
SBOM + CVE processor that builds PipelineInput for the NVIDIA vulnerability-analysis blueprint.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Vulnerability Pipeline Processor")

class ProcessRequest(BaseModel):
    image: Optional[str] = None
    github: Optional[str] = None
    cves: Optional[list[str]] = None  # optional explicit CVE list

class ProcessResponse(BaseModel):
    job_id: str
    pipeline_input: dict
    sbom_path: Optional[str] = None

def run_syft(image: str, output: Path) -> None:
    cmd = ["syft", image, "-o", f"cyclonedx-json={output}"]
    subprocess.run(cmd, check=True, capture_output=True)

def run_trivy_cves(image: str) -> list[str]:
    """Return a list of CVE IDs found by Trivy."""
    cmd = ["trivy", "image", "--format", "json", "--quiet", image]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    cves = set()
    for result in data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []):
            if vuln_id := vuln.get("VulnerabilityID"):
                cves.add(vuln_id)
    return sorted(cves)

def build_pipeline_input(image: str, cves: list[str]) -> dict:
    """
    Construct the input expected by the NVIDIA blueprint.
    See upstream data/examples/pipeline_input.json for the exact schema.
    """
    return {
        "image_name": image.split(":")[0] if ":" in image else image,
        "image_tag": image.split(":")[1] if ":" in image else "latest",
        "vulnerabilities": [{"id": cve} for cve in cves],
        # Optional fields the blueprint accepts:
        # "filesystem_path": "/path/to/extracted/rootfs",
        # "source_code": {"url": github_url}
    }

@app.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest):
    if not req.image and not req.github:
        raise HTTPException(400, "Provide either 'image' or 'github'")

    target = req.image or req.github
    with tempfile.TemporaryDirectory() as tmp:
        sbom_file = Path(tmp) / "sbom.cdx.json"
        cves = req.cves or []

        if req.image:
            run_syft(req.image, sbom_file)
            if not cves:
                cves = run_trivy_cves(req.image)
        # TODO: GitHub clone + source SBOM path

        pipeline_input = build_pipeline_input(target, cves)

        # Submit to the analysis API (URL from env in real deployment)
        analysis_url = "http://vuln-analysis-api:26466/v1/workflow/async"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(analysis_url, json=pipeline_input)
            resp.raise_for_status()
            job = resp.json()

        return ProcessResponse(
            job_id=job.get("job_id", "unknown"),
            pipeline_input=pipeline_input,
            sbom_path=str(sbom_file) if sbom_file.exists() else None,
        )

@app.get("/health")
def health():
    return {"status": "ok"}
