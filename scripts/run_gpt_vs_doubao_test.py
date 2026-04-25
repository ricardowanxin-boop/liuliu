#!/usr/bin/env python3
"""Run 3 GPT-image-2 and 3 Doubao native tests, saving source/result pairs."""

from __future__ import annotations

import base64
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_IMAGE = PROJECT_ROOT / "业务资料" / "提示词" / "原图" / "原图.jpg"
OUTPUT_DIR = PROJECT_ROOT / "日志" / "测试结果"
API_URL = "http://127.0.0.1:8000/api/generations"
PROMPT = "去掉水印，更换背景，ins风，可以改变桌子颜色\n指甲改成通明带钻，全部一样的指甲样式，衣袖也全部更改，换成一样的样式"
WATERMARK_KEYWORDS = "AI生成, 夸克, quark, watermark"


@dataclass(frozen=True, slots=True)
class ProviderRun:
    label: str
    provider: str
    model: str
    size: str


RUNS = [
    ProviderRun(label="GPT", provider="zenmux", model="openai/gpt-image-2", size="1024x1024"),
    ProviderRun(label="Doubao", provider="doubao", model="doubao-seedream-4-5-251128", size="1024x1024"),
]


def main() -> None:
    if not SOURCE_IMAGE.exists():
        raise SystemExit(f"找不到测试原图：{SOURCE_IMAGE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    sequence = 1

    for provider_run in RUNS:
        for attempt in range(1, 4):
            record = run_once(sequence=sequence, attempt=attempt, provider_run=provider_run)
            records.append(record)
            sequence += 1
            time.sleep(1.2)

    summary_path = write_summary(records)
    print(json.dumps({"summary": str(summary_path), "records": records}, ensure_ascii=False, indent=2))


def run_once(*, sequence: int, attempt: int, provider_run: ProviderRun) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = provider_run.label
    source_path = OUTPUT_DIR / f"原图{sequence}_{timestamp}_{safe_label}.png"
    result_path = OUTPUT_DIR / f"结果{sequence}_{timestamp}_{safe_label}.png"
    failure_path = OUTPUT_DIR / f"失败{sequence}_{timestamp}_{safe_label}.txt"
    shutil.copyfile(SOURCE_IMAGE, source_path)

    payload = post_generation(provider_run)
    item = (payload.get("items") or [{}])[0] if isinstance(payload.get("items"), list) else {}
    result_data_url = item.get("resultDataUrl") if isinstance(item, dict) else None

    status = payload.get("status")
    item_status = item.get("status") if isinstance(item, dict) else None
    error = item.get("error") if isinstance(item, dict) else None
    saved_result = False

    if isinstance(result_data_url, str) and result_data_url.startswith("data:image/"):
        result_path.write_bytes(decode_data_url(result_data_url))
        saved_result = True
    else:
        failure_path.write_text(
            "\n".join(
                [
                    f"时间：{timestamp}",
                    f"序号：{sequence}",
                    f"Provider：{provider_run.provider}",
                    f"Model：{provider_run.model}",
                    f"后端状态：{status}",
                    f"图片状态：{item_status}",
                    f"错误：{error or '无结果图'}",
                    "",
                    "原始响应：",
                    json.dumps(payload, ensure_ascii=False, indent=2)[:12000],
                ]
            ),
            encoding="utf-8",
        )

    return {
        "sequence": sequence,
        "timestamp": timestamp,
        "label": provider_run.label,
        "provider": provider_run.provider,
        "model": provider_run.model,
        "attempt": attempt,
        "status": status,
        "item_status": item_status,
        "provider_call_count": payload.get("providerCallCount"),
        "source_path": str(source_path),
        "result_path": str(result_path) if saved_result else None,
        "failure_path": str(failure_path) if not saved_result else None,
        "error": error,
    }


def post_generation(provider_run: ProviderRun) -> dict[str, Any]:
    with SOURCE_IMAGE.open("rb") as handle:
        files = [("files[]", (SOURCE_IMAGE.name, handle, "image/jpeg"))]
        data = {
            "prompt": PROMPT,
            "provider_type": provider_run.provider,
            "provider": provider_run.provider,
            "model": provider_run.model,
            "size": provider_run.size,
            "quality": "standard",
            "output_format": "png",
            "realistic_mode": "true",
            "watermark_cleanup_enabled": "true",
            "watermark_keywords": WATERMARK_KEYWORDS,
            "quality_control_enabled": "false",
            "quality_threshold": "72",
            "quality_max_retries": "0",
        }
        response = requests.post(API_URL, data=data, files=files, timeout=900)

    try:
        payload = response.json()
    except ValueError:
        payload = {"status": "http_error", "detail": response.text}
    if response.status_code >= 400:
        payload.setdefault("status", "http_error")
        payload["httpStatus"] = response.status_code
    return payload


def decode_data_url(data_url: str) -> bytes:
    _header, encoded = data_url.split(",", 1)
    return base64.b64decode(encoded)


def write_summary(records: list[dict[str, Any]]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"测试总结_{timestamp}.md"
    total_calls = sum(int(record.get("provider_call_count") or 0) for record in records)
    lines = [
        f"# GPT-image-2 vs 豆包原生 4.5 测试总结 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- 固定提示词：{PROMPT}",
        f"- 固定原图：{SOURCE_IMAGE}",
        f"- 总真实调用：{total_calls}",
        f"- 成功保存结果图：{sum(1 for record in records if record.get('result_path'))}/6",
        "",
        "## 明细",
    ]
    for record in records:
        lines.append(
            "- "
            f"#{record['sequence']} {record['label']} 第 {record['attempt']} 次："
            f"{record['status']} / {record['item_status']}，"
            f"调用 {record.get('provider_call_count')} 次，"
            f"原图 {record['source_path']}，"
            f"结果 {record.get('result_path') or '无'}，"
            f"失败记录 {record.get('failure_path') or '无'}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
