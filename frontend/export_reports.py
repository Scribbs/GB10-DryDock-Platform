"""Export on-disk vulnerability reports to PDF and an Excel CSV."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from fpdf import FPDF

MEDIUM_AND_BELOW = {
    "medium",
    "low",
    "negligible",
    "none",
    "unknown",
    "info",
    "informational",
    "unscored",
    "",
}

_LABELED_SEV = re.compile(
    r"(?i)\b(?:severity|cvss\s*(?:v?3(?:\.\d)?)?\s*(?:base)?\s*severity)"
    r"\b\s*[:\-|]+\s*(critical|high|medium|low|negligible|none|unknown|info(?:rmational)?)"
)
_SCORE_SEV = re.compile(
    r"(?i)\b(?:cvss[^:\n]{0,24})?base\s+score\s*[:\s]+(\d+(?:\.\d+)?)\s*"
    r"(critical|high|medium|low|negligible|none)?"
)
_SCORE = re.compile(r"(?i)\bcvss[^0-9\n]{0,24}(\d{1,2}(?:\.\d)?)")


def render_image_export(image_dir) -> None:
    """Draw PDF and CSV download buttons for one analyzed image directory."""
    image_dir = Path(image_dir)
    st.subheader("Export")
    only = st.checkbox(
        "CSV includes Medium and below only",
        value=True,
        key=f"csv-filter-{image_dir.name}",
    )
    if st.button("Prepare exports", key=f"export-{image_dir.name}"):
        with st.spinner("Building PDF and CSV from the report files..."):
            bundle = collect_image(image_dir)
            stamp = image_dir.name
            st.session_state["export_bundle"] = {
                "image": stamp,
                "pdf": to_pdf(bundle),
                "csv": to_csv(bundle, only),
                "pdf_name": f"{stamp}.pdf",
                "csv_name": f"{stamp}-medium-and-below.csv" if only else f"{stamp}-findings.csv",
                "shown": sum(
                    1
                    for row in bundle["findings"]
                    if (not only or row["severity"] in MEDIUM_AND_BELOW)
                ),
                "total": len(bundle["findings"]),
            }
    exp = st.session_state.get("export_bundle")
    if not exp or exp.get("image") != image_dir.name:
        return
    st.caption(
        f"CSV rows: {exp['shown']} of {exp['total']}. "
        "Critical and High stay in the PDF. Excel opens the CSV directly (UTF-8 with BOM)."
    )
    left, right = st.columns(2)
    left.download_button(
        "Download PDF",
        data=exp["pdf"],
        file_name=exp["pdf_name"],
        mime="application/pdf",
        key=f"pdf-{image_dir.name}",
    )
    right.download_button(
        "Download CSV",
        data=exp["csv"],
        file_name=exp["csv_name"],
        mime="text/csv",
        key=f"csv-{image_dir.name}",
    )


def collect_image(image_dir) -> dict:
    image_dir = Path(image_dir)
    inventory = _load_inventory(image_dir / "cve_inventory.json")
    vex_by_id = _load_vex(image_dir / "vex_results")
    vuln_by_id = _load_named_markdown(image_dir / "vulnerability_reports")
    exploit_by_id = _load_named_markdown(image_dir / "exploitability_reports")
    ids = sorted(set(inventory) | set(vex_by_id) | set(vuln_by_id) | set(exploit_by_id))
    findings = []
    for vuln_id in ids:
        meta = inventory.get(vuln_id, {})
        vex = vex_by_id.get(vuln_id, {})
        vuln_text = vuln_by_id.get(vuln_id, "")
        severity = str(meta.get("severity") or "").lower()
        cvss = str(meta.get("cvss") or meta.get("cvss_score") or "")
        if not severity:
            severity, parsed_score = _severity(vuln_text)
            cvss = cvss or parsed_score
        findings.append(
            {
                "vuln_id": vuln_id,
                "cve_id": meta.get("cve_id") or (vuln_id if vuln_id.startswith("CVE-") else ""),
                "ghsa_id": meta.get("ghsa_id") or (vuln_id if vuln_id.startswith("GHSA-") else ""),
                "package": meta.get("package") or meta.get("package_name") or "",
                "version": meta.get("version") or meta.get("package_version") or "",
                "severity": severity or "unknown",
                "cvss": cvss,
                "vex_status": vex.get("status") or vex.get("vex_status") or meta.get("vex_status") or "",
                "justification": vex.get("justification")
                or vex.get("vex_justification")
                or meta.get("justification")
                or "",
                "success": meta.get("success", ""),
                "error": str(meta.get("error") or ""),
                "vulnerability_report": vuln_text,
                "exploitability_report": exploit_by_id.get(vuln_id, ""),
                "vex_report": vex.get("_markdown") or "",
            }
        )
    container = "\n\n".join(_load_named_markdown(image_dir / "container_reports").values())
    return {
        "summary": {"image_name": image_dir.name, "image_tag": "", "outcome": ""},
        "findings": findings,
        "container": container,
    }


def to_csv(bundle: dict, medium_and_below_only: bool = True) -> bytes:
    rows = bundle["findings"]
    if medium_and_below_only:
        rows = [row for row in rows if row["severity"] in MEDIUM_AND_BELOW]
    image = bundle["summary"].get("image_name") or "unknown-image"
    buffer = io.StringIO()
    fields = [
        "image",
        "vuln_id",
        "cve_id",
        "ghsa_id",
        "package",
        "version",
        "severity",
        "cvss",
        "vex_status",
        "justification",
        "success",
        "error",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "image": image})
    return buffer.getvalue().encode("utf-8-sig")


def to_pdf(bundle: dict) -> bytes:
    summary = bundle["summary"]
    image = summary.get("image_name") or "unknown-image"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    _write(pdf, f"Vulnerability report  {image}", 9)
    pdf.set_font("Helvetica", size=10)
    _write(
        pdf,
        (
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Findings: {len(bundle['findings'])}"
        ),
        5,
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    _write(pdf, "Findings", 7)
    pdf.set_font("Helvetica", size=9)
    for row in bundle["findings"]:
        _write(
            pdf,
            (
                f"{row['vuln_id']}  {row['severity'].upper()}  "
                f"{row['vex_status']}  {row['justification']}  "
                f"{row['package']} {row['version']}"
            ),
            4.5,
        )
    if bundle["container"]:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        _write(pdf, "Container report", 7)
        pdf.set_font("Helvetica", size=9)
        _write(pdf, bundle["container"], 4.5)
    for row in bundle["findings"]:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        _write(pdf, f"{row['vuln_id']}  {row['severity'].upper()}  {row['vex_status']}", 7)
        for title, body in (
            ("Vulnerability", row["vulnerability_report"]),
            ("Exploitability", row["exploitability_report"]),
            ("VEX", row["vex_report"]),
        ):
            pdf.set_font("Helvetica", "B", 11)
            _write(pdf, title, 6)
            pdf.set_font("Helvetica", size=9)
            _write(pdf, body or "(none)", 4.5)
            pdf.ln(1)
    return bytes(pdf.output())


def _load_inventory(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        rows = data.get("cves") or data.get("vulnerabilities") or data.get("results")
        if not isinstance(rows, list):
            rows = [
                {"id": key, **value} if isinstance(value, dict) else {"id": key, "severity": value}
                for key, value in data.items()
            ]
    else:
        rows = data
    found = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        vuln_id = row.get("vuln_id") or row.get("id") or row.get("cve_id") or row.get("VulnerabilityID") or ""
        if vuln_id:
            found[str(vuln_id)] = row
    return found


def _load_vex(directory: Path) -> dict:
    found = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(errors="ignore"))
        except json.JSONDecodeError:
            continue
        vuln_id = data.get("vuln_id") or data.get("cve_id") or path.stem.split("_")[0]
        found[str(vuln_id)] = data
    for path in sorted(directory.glob("*.md")):
        vuln_id = path.stem.split("_")[0]
        found.setdefault(vuln_id, {})["_markdown"] = path.read_text(errors="ignore")
    return found


def _load_named_markdown(directory: Path) -> dict:
    found = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.md")):
        found[path.stem.split("_")[0]] = path.read_text(errors="ignore")
    return found


def _severity(text: str) -> tuple[str, str]:
    labeled = _LABELED_SEV.search(text or "")
    scored = _SCORE_SEV.search(text or "")
    if labeled:
        severity = labeled.group(1).lower()
    elif scored and scored.group(2):
        severity = scored.group(2).lower()
    else:
        severity = "unknown"
    if severity.startswith("info"):
        severity = "info"
    if scored and scored.group(1):
        return severity, scored.group(1)
    score = _SCORE.search(text or "")
    return severity, score.group(1) if score else ""


def _plain(text: str, limit: int = 12000) -> str:
    text = re.sub(r"```.*?```", "", text or "", flags=re.S)
    text = re.sub(r"[#>*_`]+", "", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > limit:
        text = text[:limit] + "\n\n[truncated]"
    text = text.encode("latin-1", "replace").decode("latin-1")
    text = "\n".join(
        " ".join(_chunk(token, 60) for token in line.split(" ")) for line in text.splitlines()
    )
    return text


def _chunk(token: str, size: int) -> str:
    if len(token) <= size:
        return token
    return " ".join(token[i : i + size] for i in range(0, len(token), size))


def _write(pdf: FPDF, text: str, height: float) -> None:
    text = _plain(text)
    if not text:
        return
    try:
        pdf.multi_cell(0, height, text, wrapmode="CHAR")
    except TypeError:
        pdf.multi_cell(0, height, text)
