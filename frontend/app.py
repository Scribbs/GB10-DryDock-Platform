"""
Streamlit frontend for the GB10 Vulnerability Analysis Platform.
Inspired by DryDock-style contextual reporting.
"""
import json
import os
from pathlib import Path

import httpx
import streamlit as st
from cluster_status import render_live_sidebar
from export_reports import render_image_export


LOGO = Path(__file__).parent / "assets" / "drydock-logo.png"


st.set_page_config(
    page_title="DryDock Vuln Analysis",
    layout="wide",
    page_icon=str(LOGO) if LOGO.exists() else "🛡️",
)
render_live_sidebar()


ANALYSIS_URL = "http://vuln-analysis-api:26466"  # overridden by env in real compose
PROCESSOR_URL = "http://processor:8080"
OUTPUTS_ROOT = Path(os.getenv("OUTPUTS_DIR", "/app/outputs"))

REPORT_DIRS = {
    "Vulnerability Reports": "vulnerability_reports",
    "Container Reports": "container_reports",
    "Exploitability Reports": "exploitability_reports",
    "VEX Results": "vex_results",
}

if LOGO.exists():
    mark, heading = st.columns([1, 5], vertical_alignment="center")
    with mark:
        st.image(str(LOGO), width=150)
    with heading:
        st.title("DryDock Vulnerability Analysis Platform")
else:
    st.title("DryDock Vulnerability Analysis Platform")
    st.warning(f"Logo not found at {LOGO}")

st.caption("IG Labs Texas customized NVIDIA AI Blueprint + Syft/Trivy pipeline on Dell GB10 Cluster")

tab1, tab2 = st.tabs(["New Analysis", "Reports"])


# ---------------------------------------------------------------------------
# Helpers for Reports tab
# ---------------------------------------------------------------------------
def list_analyzed_images() -> list[str]:
    if not OUTPUTS_ROOT.exists():
        return []
    return sorted(
        [p.name for p in OUTPUTS_ROOT.iterdir() if p.is_dir()],
        reverse=True,
    )


def list_markdown(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return sorted(dir_path.glob("*.md"))


def extract_status_from_vex(vex_path: Path) -> str:
    text = vex_path.read_text(errors="ignore").lower()
    if "not_affected" in text or "not affected" in text:
        return "NOT EXPLOITABLE"
    if "affected" in text:
        return "EXPLOITABLE"
    return "UNKNOWN"


def build_overall_findings(image_dir: Path) -> dict[str, list[str]]:
    findings = {"EXPLOITABLE": [], "NOT EXPLOITABLE": [], "UNKNOWN": []}
    vex_dir = image_dir / "vex_results"
    if not vex_dir.exists():
        return findings

    for md in list_markdown(vex_dir):
        cve = md.stem.split("_")[0]
        status = extract_status_from_vex(md)
        findings[status].append(cve)
    return findings


def render_lower_cve_table(image_dir: Path) -> None:
    inventory_path = image_dir / "cve_inventory.json"
    st.subheader("Medium and Below")
    if not inventory_path.exists():
        st.info("No CVE inventory for this image yet. It is written when the processor finishes the Trivy scan.")
        return

    data = json.loads(inventory_path.read_text())
    findings = data.get("findings", [])
    lower = [row for row in findings if row.get("severity") not in ("CRITICAL", "HIGH")]
    sent = data.get("pipeline_vuln_ids", [])
    held = data.get("high_critical_not_sent", [])
    st.caption(
        f"{len(sent)} High/Critical sent to analysis, "
        f"{len(held)} High/Critical held by the cap, "
        f"{len(lower)} Medium and below listed here."
    )
    if not lower:
        st.success("No Medium, Low, or Unknown CVEs.")
        return

    st.dataframe(
        lower,
        use_container_width=True,
        hide_index=True,
        column_order=[
            "severity",
            "vuln_id",
            "pkg_name",
            "installed_version",
            "fixed_version",
            "title",
            "in_sbom",
            "primary_url",
        ],
    )


# ---------------------------------------------------------------------------
# Tab 1 – New Analysis (unchanged)
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Submit an Image or Repository")
    col1, col2 = st.columns(2)
    with col1:
        image = st.text_input("Docker Image", placeholder="nginx:1.25 or registry.example.com/app:latest")
    with col2:
        github = st.text_input("GitHub Repository (optional)", placeholder="https://github.com/org/repo")
    cve_filter = st.text_area("Specific CVEs (one per line, optional)", height=100)
    if st.button("Start Analysis", type="primary"):
        if not image and not github:
            st.error("Provide at least an image or a GitHub URL.")
        else:
            payload = {}
            if image:
                payload["image"] = image
            if github:
                payload["github"] = github
            if cve_filter.strip():
                payload["cves"] = [c.strip() for c in cve_filter.splitlines() if c.strip()]
            with st.spinner("Generating SBOM + CVEs and submitting job..."):
                try:
                    resp = httpx.post(f"{PROCESSOR_URL}/process", json=payload, timeout=300)
                    resp.raise_for_status()
                    result = resp.json()
                    st.session_state["last_job"] = result["job_id"]
                    st.success(f"Job submitted: `{result['job_id']}`")
                    st.json(result["pipeline_input"])
                except Exception as e:
                    st.error(f"Failed: {e}")


# ---------------------------------------------------------------------------
# Tab 2 – Job Status (removed for further develpoment)
# ---------------------------------------------------------------------------
#with tab2:
#    st.subheader("Check Job Status")
#    job_id = st.text_input("Job ID", value=st.session_state.get("last_job", ""))
#    if job_id and st.button("Refresh"):
#        try:
#            resp = httpx.get(f"{ANALYSIS_URL}/v1/workflow/async/job/{job_id}")
#            resp.raise_for_status()
#            data = resp.json()
#            st.json(data)
#            if data.get("status") == "completed":
#                st.success("Analysis complete. Switch to the Reports tab.")
#        except Exception as e:
#            st.error(str(e))


# ---------------------------------------------------------------------------
# Tab 2 – Reports (updated)
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("View Reports")

    images = list_analyzed_images()
    if not images:
        st.info(
            "No completed analyses found yet. "
            f"Reports are expected under `{OUTPUTS_ROOT}/<image-name>/`."
        )
        st.code("""
# Expected structure (per image):
outputs/
└── <sanitized-image-name>/
    ├── vulnerability_reports/
    ├── container_reports/
    ├── exploitability_reports/
    ├── vex_results/
    ├── cve_inventory.json
    └── failed_reports/          # only when present
""")
    else:
        selected = st.selectbox("Analyzed image", images)
        image_dir = OUTPUTS_ROOT / selected

        # Overall Findings
        st.subheader("Overall Findings")
        findings = build_overall_findings(image_dir)
        cols = st.columns(3)
        cols[0].metric("EXPLOITABLE", len(findings["EXPLOITABLE"]))
        cols[1].metric("NOT EXPLOITABLE", len(findings["NOT EXPLOITABLE"]))
        cols[2].metric("UNKNOWN", len(findings["UNKNOWN"]))

        for status, cves in findings.items():
            if cves:
                with st.expander(f"{status} ({len(cves)})"):
                    st.write(", ".join(sorted(cves)))

        st.divider()
        render_lower_cve_table(image_dir)
        st.divider()
        render_image_export(image_dir)
        st.divider()

        # Report cards
        st.subheader("Reports")
        for title, subdir in REPORT_DIRS.items():
            report_dir = image_dir / subdir
            mds = list_markdown(report_dir)
            if not mds:
                continue

            st.markdown(f"#### {title}")
            for md in mds:
                with st.expander(md.name):
                    st.markdown(md.read_text(errors="ignore"))

        # Failed reports (if any)
        failed_dir = image_dir / "failed_reports"
        failed = list_markdown(failed_dir)
        if failed:
            st.markdown("#### Failed Reports")
            for md in failed:
                with st.expander(md.name):
                    st.markdown(md.read_text(errors="ignore"))


# ---------------------------------------------------------------------------
# Sidebar (System Status)
# ---------------------------------------------------------------------------
@st.fragment(run_every="2s")
def _cluster_body() -> None:
    snap = _load()
    st.header("Cluster")
    if not snap["ok"]:
        st.error("vLLM unreachable")
        st.caption(snap["error"])
        return

    now = time.time()
    prev = st.session_state.get("_vllm_prev")
    gen_rate = prompt_rate = None
    if prev and now > prev["t"]:
        dt = now - prev["t"]
        gen_rate = (snap["gen"] - prev["gen"]) / dt
        prompt_rate = (snap["prompt"] - prev["prompt"]) / dt
    st.session_state["_vllm_prev"] = {"t": now, "gen": snap["gen"], "prompt": snap["prompt"]}

    st.markdown(
    '<div style="font-size:1.15rem;font-weight:700;">Model</div>',
    unsafe_allow_html=True)
    st.code(snap["model"], language=None)
    c1, c2 = st.columns(2)
    c1.metric("Running", f"{snap['running']:.0f}")
    c2.metric("Queued", f"{snap['waiting']:.0f}")
    c1.metric("Gen tok/s", f"{(gen_rate if gen_rate is not None else snap['gen_gauge']):.1f}")
    c2.metric("Prompt tok/s", f"{(prompt_rate if prompt_rate is not None else snap['prompt_gauge']):.1f}")
    st.metric("Generated", f"{snap['gen']:.0f}")
    st.metric("KV cache", f"{snap['kv'] * 100:.0f}%")

    st.markdown(
    '<div style="font-size:1.15rem;font-weight:700;">Nodes</div>',
    unsafe_allow_html=True)

    if not snap["nodes"]:
        st.write("Head up, Ray summary unavailable")
        return
    for node in snap["nodes"]:
        raylet = node.get("raylet") or {}
        state = raylet.get("state", "?")
        gpu = (raylet.get("resourcesTotal") or {}).get("GPU", "?")
        st.write(f"{node.get('hostname', node.get('ip'))}  {state}  GPU {gpu}")

def render_live_sidebar() -> None:
    with st.sidebar:
        _cluster_body()
