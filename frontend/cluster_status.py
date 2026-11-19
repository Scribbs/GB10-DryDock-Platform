import os
import time
import httpx
import streamlit as st

VLLM = os.environ.get("VLLM_BASE_URL", "http://10.20.0.11:8001/v1").removesuffix("/v1")
RAY = os.environ.get("RAY_DASHBOARD_URL", "http://10.20.0.11:8265")

def _samples(text: str, name: str) -> float:
    total = 0.0
    for line in text.splitlines():
        if not line.startswith(name):
            continue
        rest = line[len(name):]
        if not rest or rest[0] not in "{ \t":
            continue
        try:
            total += float(line.rsplit(" ", 1)[-1])
        except ValueError:
            pass
    return total

def _load() -> dict:
    out = {"ok": False, "model": "—", "nodes": [], "error": "",
           "running": 0.0, "waiting": 0.0, "gen": 0.0, "prompt": 0.0,
           "kv": 0.0, "gen_gauge": 0.0, "prompt_gauge": 0.0}
    try:
        with httpx.Client(timeout=2.5) as client:
            models = client.get(f"{VLLM}/v1/models").json()
            metrics = client.get(f"{VLLM}/metrics").text
            out["model"] = models["data"][0]["id"]
            out["running"] = _samples(metrics, "vllm:num_requests_running")
            out["waiting"] = _samples(metrics, "vllm:num_requests_waiting")
            out["gen"] = _samples(metrics, "vllm:generation_tokens_total")
            out["prompt"] = _samples(metrics, "vllm:prompt_tokens_total")
            out["kv"] = _samples(metrics, "vllm:kv_cache_usage_perc") or _samples(metrics, "vllm:gpu_cache_usage_perc")
            out["gen_gauge"] = _samples(metrics, "vllm:avg_generation_throughput_toks_per_s")
            out["prompt_gauge"] = _samples(metrics, "vllm:avg_prompt_throughput_toks_per_s")
            try:
                summary = client.get(f"{RAY}/nodes", params={"view": "summary"}).json()
                out["nodes"] = summary.get("data", {}).get("summary", [])
            except Exception:
                out["nodes"] = []
            out["ok"] = True
    except Exception as exc:
        out["error"] = str(exc)
    return out

@st.fragment(run_every="2s")
def _cluster_body() -> None:
    try:
        snap = _load()
        if not snap["ok"]:
            st.error("vLLM unreachable")
            st.caption(snap["error"])
            return
        now = time.time()
        prev = st.session_state.get("_vllm_prev")
        gen_rate = prompt_rate = None
        if prev and now > prev["t"]:
            dt = now - prev["t"]
            gen_rate = max(0.0, (snap["gen"] - prev["gen"]) / dt)
            prompt_rate = max(0.0, (snap["prompt"] - prev["prompt"]) / dt)
        st.session_state["_vllm_prev"] = {"t": now, "gen": snap["gen"], "prompt": snap["prompt"]}
        st.caption("Model")
        st.text(snap["model"])
        st.metric("Running / queued", f"{snap['running']:.0f} / {snap['waiting']:.0f}")
        st.metric("Gen tok/s", f"{(gen_rate if gen_rate is not None else snap['gen_gauge']):.1f}")
        st.metric("Prompt tok/s", f"{(prompt_rate if prompt_rate is not None else snap['prompt_gauge']):.1f}")
        st.metric("Generated", f"{snap['gen']:.0f}")
        st.metric("KV cache", f"{snap['kv'] * 100:.0f}%")
        st.caption("Nodes")
        nodes = snap["nodes"] if isinstance(snap["nodes"], list) else []
        if not nodes:
            st.write("Head up, Ray summary unavailable")
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            raylet = node.get("raylet") or {}
            gpu = (raylet.get("resourcesTotal") or {}).get("GPU", "?")
            st.write(f"{node.get('hostname', node.get('ip'))}  {raylet.get('state', '?')}  GPU {gpu}")
    except Exception as exc:
        st.exception(exc)

def render_live_sidebar() -> None:
    with st.sidebar:
        st.header("Cluster")
        _cluster_body()
