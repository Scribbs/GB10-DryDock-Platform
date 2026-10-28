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
    cves: Optional[list[str]] = None

class ProcessResponse(BaseModel):
    job_id: str
    pipeline_input: dict
    sbom_path: Optional[str] = None

def clean_image_ref(raw: str) -> str:
    raw = raw.strip()
    if raw.lower().startswith("docker pull "):
        raw = raw[len("docker pull "):].strip()
    return raw

def run_syft(image: str, output: Path) -> None:
    cmd = ["syft", image, "-o", f"cyclonedx-json={output}"]
    subprocess.run(cmd, check=True, capture_output=True)

def run_trivy_cves(image: str) -> list[str]:
    cmd = ["trivy", "image", "--format", "json", "--quiet", image]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    cves = set()
    for result_item in data.get("Results", []):
        for vuln in result_item.get("Vulnerabilities", []):
            if vuln_id := vuln.get("VulnerabilityID"):
                cves.add(vuln_id)
    return sorted(cves)

def build_pipeline_input(image: str, cves: list[str]) -> dict:
    return {
        "image_name": image.split(":")[0] if ":" in image else image,
        "image_tag": image.split(":")[1] if ":" in image else "latest",
        "vulns": [{"vuln_id": cve} for cve in cves],
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
            image = clean_image_ref(req.image)
            run_syft(image, sbom_file)
            if not cves:
                cves = run_trivy_cves(image)
            cves = cves[:20]          # safety cap
            target = image

        pipeline_input = build_pipeline_input(target, cves)
        print("DEBUG payload:", json.dumps(pipeline_input)[:2000])

        analysis_url = "http://192.168.1.111:26466/v1/workflow/async"
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(analysis_url, json=pipeline_input)
            if resp.status_code >= 400:
                print("DEBUG response:", resp.status_code, resp.text[:2000])
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
