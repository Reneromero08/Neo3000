"""Measure rolling minimum decode speed at occupied context targets."""
import statistics, time, json, sys, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.context_matrix import build_prompt, normalize_base_url

BASE = normalize_base_url("http://127.0.0.1:9292/v1")
API = BASE + "/v1"
TARGETS = [2048, 32768, 60000]
WINDOW = 16
MAX_TOKENS = 384

def stream_with_timing(payload, timeout_sec):
    start = time.perf_counter()
    token_times = []
    content_parts = []
    reasoning_parts = []
    first_token = None
    first_content = None

    req = urllib.request.Request(
        API + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = evt.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            text = delta.get("content")
            reason = delta.get("reasoning_content")
            if isinstance(text, str) and text or isinstance(reason, str) and reason:
                now = time.perf_counter()
                token_times.append(now)
                if first_token is None:
                    first_token = now
                if isinstance(text, str) and text:
                    content_parts.append(text)
                    if first_content is None:
                        first_content = now
                if isinstance(reason, str) and reason:
                    reasoning_parts.append(reason)

    elapsed = time.perf_counter() - start
    return token_times, first_token, first_content, "".join(content_parts), elapsed


def rolling_min_ttps(token_times, window, ref_time):
    if len(token_times) < window:
        return None, 0
    min_rate = float("inf")
    for i in range(len(token_times) - window + 1):
        duration = token_times[i + window - 1] - token_times[i]
        if duration > 0:
            rate = window / duration
            if rate < min_rate:
                min_rate = rate
    return min_rate, len(token_times)


results = []
for target in TARGETS:
    print(f"\n=== TARGET {target} ===")
    prompt, actual_tokens, words = build_prompt(BASE, target, 3000 + target, 30)
    print(f"actual prompt tokens: {actual_tokens}")

    payload = {
        "model": "agents-a1",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, "seed": 42,
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "stream_options": {"include_usage": True},
        "cache_prompt": True,
    }

    # Warmup + 3 measured runs
    for run in range(4):
        token_times, first_token, first_content, content, total_time = stream_with_timing(payload, 3600)
        if run == 0:
            print(f"  warmup: tokens={len(token_times)} content={len(content)} ttft={first_token - (time.perf_counter() - total_time):.2f}s" if first_token else "  warmup: no tokens")
            continue

        avg_tps = len(token_times) / (token_times[-1] - token_times[0]) if len(token_times) > 1 else 0
        min_ttps, n_tokens = rolling_min_ttps(token_times, WINDOW, token_times[0] if token_times else 0)
        ttft = (first_token - (time.perf_counter() - total_time)) if first_token else None

        print(f"  run {run}: tokens={n_tokens} avg_tps={avg_tps:.1f} min16_tps={min_ttps:.1f} ttft={ttft:.2f}s")

        if run == 1:  # Record first measured run
            results.append({
                "target": target,
                "actual_prompt_tokens": actual_tokens,
                "completion_tokens": n_tokens,
                "avg_decode_tps": round(avg_tps, 1),
                "rolling_min_16_tps": round(min_ttps, 1),
                "ttft_s": round(ttft, 2) if ttft else None,
                "ratio_min_to_avg": round(min_ttps / avg_tps, 2) if avg_tps > 0 else None,
            })

print("\n=== ROLLING MINIMUM DECODE SPEED ===")
print(f"{'Target':>8} {'Prompt':>8} {'AvgTPS':>8} {'Min16TPS':>10} {'Min/Avg':>8} {'TTFT':>8}")
for r in results:
    print(f"{r['target']:>8} {r['actual_prompt_tokens']:>8} {r['avg_decode_tps']:>8.1f} {r['rolling_min_16_tps']:>10.1f} {r['ratio_min_to_avg']:>8.2f} {r['ttft_s']:>8.2f}")

# Write results
out = Path(__file__).resolve().parents[1] / "lab" / "rolling-decode.local.json"
out.write_text(json.dumps(results, indent=2))
print(f"\nwrote {out}")
