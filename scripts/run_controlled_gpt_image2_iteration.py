#!/usr/bin/env python3
"""Run a controlled GPT-image-2 test batch through the local backend."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "业务资料" / "提示词" / "原图"
LOG_ROOT = PROJECT_ROOT / "日志"
RUN_LOG_DIR = LOG_ROOT / "控制变量测试"
INDEX_PATH = LOG_ROOT / "generation_iteration_index.json"
API_URL = "http://127.0.0.1:8000/api/generations"
FIXED_PROMPT = "去掉水印，更换背景，ins风，可以改变桌子颜色\n指甲改成通明带钻，全部一样的指甲样式，衣袖也全部更改，换成一样的样式"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1, help="最多本批处理几张图，不能超过 5")
    parser.add_argument("--offset", type=int, default=0, help="跳过前几张参考图")
    parser.add_argument("--quality-max-retries", type=int, default=0, help="真实测试默认 0，避免预算失控")
    parser.add_argument("--quality-threshold", type=int, default=72)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 5:
        raise SystemExit("--limit 必须在 1 到 5 之间")
    if args.quality_max_retries < 0 or args.quality_max_retries > 1:
        raise SystemExit("--quality-max-retries 本脚本限制在 0 或 1")

    files = _source_files()[args.offset : args.offset + args.limit]
    if not files:
        raise SystemExit(f"没有找到可测试图片：{SOURCE_DIR}")

    before = _load_index()
    before_next = int(before.get("next_iteration", 1))
    response = _post_generation(files=files, args=args)
    after = _load_index()
    after_next = int(after.get("next_iteration", before_next))
    new_records = [
        record
        for record in after.get("records", [])
        if before_next <= int(record.get("iteration", 0)) < after_next
    ]

    run_log = _write_run_log(
        files=files,
        args=args,
        response=response,
        new_records=new_records,
        estimated_calls=max(0, after_next - before_next),
    )
    print(json.dumps({
        "ok": response.get("status") == "completed",
        "source_count": len(files),
        "provider_call_count": response.get("providerCallCount"),
        "estimated_real_calls": max(0, after_next - before_next),
        "response_status": response.get("status"),
        "run_log": str(run_log),
        "records": [
            {
                "iteration": record.get("iteration"),
                "status": record.get("status"),
                "score": record.get("quality_score"),
                "log_path": record.get("log_path"),
                "result_path": record.get("result_path"),
            }
            for record in new_records
        ],
    }, ensure_ascii=False, indent=2))
    if response.get("status") != "completed":
        raise SystemExit(2)


def _post_generation(*, files: list[Path], args: argparse.Namespace) -> dict[str, Any]:
    multipart = []
    handles = []
    try:
        for path in files:
            handle = path.open("rb")
            handles.append(handle)
            multipart.append(("files[]", (path.name, handle, _mime_type(path))))

        data = {
            "prompt": FIXED_PROMPT,
            "provider_type": "zenmux",
            "provider": "zenmux",
            "model": "openai/gpt-image-2",
            "size": "1024x1024",
            "quality": "standard",
            "output_format": "png",
            "realistic_mode": "true",
            "watermark_cleanup_enabled": "true",
            "watermark_keywords": "AI生成, 夸克, quark, watermark",
            "quality_control_enabled": "true",
            "quality_threshold": str(args.quality_threshold),
            "quality_max_retries": str(args.quality_max_retries),
        }
        response = requests.post(API_URL, data=data, files=multipart, timeout=args.timeout)
        try:
            payload = response.json()
        except ValueError:
            payload = {"status": "http_error", "detail": response.text}
        if response.status_code >= 400:
            payload.setdefault("status", "http_error")
            payload.setdefault("httpStatus", response.status_code)
        return payload
    finally:
        for handle in handles:
            handle.close()


def _source_files() -> list[Path]:
    files = sorted(
        [path for path in SOURCE_DIR.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS],
        key=lambda item: item.name,
    )
    preferred = SOURCE_DIR / "原图.jpg"
    if preferred in files:
        files.remove(preferred)
        files.insert(0, preferred)
    return files


def _load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return {"next_iteration": 1, "records": []}
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"next_iteration": 1, "records": []}


def _write_run_log(
    *,
    files: list[Path],
    args: argparse.Namespace,
    response: dict[str, Any],
    new_records: list[dict[str, Any]],
    estimated_calls: int,
) -> Path:
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = RUN_LOG_DIR / f"控制变量测试_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    items = response.get("items") if isinstance(response.get("items"), list) else []
    path.write_text(
        "\n".join(
            [
                f"# 控制变量测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"- 模型：ZenMux / openai/gpt-image-2",
                f"- 固定提示词：{FIXED_PROMPT}",
                f"- 参考标准目录：{SOURCE_DIR}",
                f"- 本批图片数：{len(files)}",
                f"- 质量重试次数：{args.quality_max_retries}",
                f"- 后端返回真实接口调用：{response.get('providerCallCount')}",
                f"- 估算真实接口调用：{estimated_calls}",
                f"- 响应状态：{response.get('status')}",
                "",
                "## 输入图片",
                *[f"- {file}" for file in files],
                "",
                "## 后端响应",
                *[
                    f"- {item.get('sourceName')}：{item.get('status')}，"
                    f"质检 {item.get('qualityScore')}，日志 {item.get('iterationLogPath')}"
                    for item in items
                    if isinstance(item, dict)
                ],
                "",
                "## 新增迭代记录",
                *[
                    f"- #{record.get('iteration'):04d} {record.get('status')} "
                    f"{record.get('quality_score')} 分：{record.get('log_path')}"
                    for record in new_records
                ],
                "",
                "## 原始响应 JSON",
                "```json",
                json.dumps(response, ensure_ascii=False, indent=2)[:8000],
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


if __name__ == "__main__":
    main()
