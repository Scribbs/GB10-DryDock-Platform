# Combined Compose + 2-Node vLLM Notes

## Including the upstream blueprint

`docker-compose.combined.yml` uses Compose's `include:` to pull in:

```
./vulnerability-analysis/deploy/docker-compose.yml
```

This keeps the official services (`vuln-analysis-api`, Jupyter, nginx cache, etc.) intact while adding the platform frontend and processor on the same network.

## Pointing the blueprint at local vLLM

In `.env` set:

```
NV_BASE_URL=http://vllm-head:8000/v1
```

The blueprint's config.yml uses `${NV_BASE_URL}` for its NIM clients, so the agents will call the local multi-node vLLM instead of the NVIDIA cloud endpoint.

## Multi-node caveats

- The vLLM overlay defines both head and worker. In practice the worker must run on the second physical node.
- Preferred production path: use the scripts from https://github.com/eugr/spark-vllm-docker (`setup-cluster.sh`, `launch-cluster.sh`) after the QSFP link is up, then point this stack at the resulting OpenAI-compatible endpoint.
- Interface names (`enp1s0f1np1`, `rocep1s0f1`, etc.) differ by firmware/OS; always verify with `ibdev2netdev` and `ip link`.

## Suggested model sizes for 2×128 GB

- Comfortable: Qwen3.8-27B-NVFP4, Llama-3.1-70B (quantized)
- Larger (TP=2): Qwen3.5-397B-A17B-int4, DeepSeek-V4-Flash variants (community recipes)
