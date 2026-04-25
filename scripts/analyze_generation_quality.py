#!/usr/bin/env python3
"""Build a quality error analysis report and knowledge database for generated images."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.quality_control import evaluate_generated_image

DEFAULT_RESULTS_DIR = PROJECT_ROOT / "日志" / "测试结果"
LOG_DIR = PROJECT_ROOT / "日志" / "质量错误分析日志"
DATABASE_PATH = LOG_DIR / "quality_error_knowledge_base.json"


SEVERITY_LEVELS = {
    "P0": "致命逻辑错误：人体结构、商品结构、物理常识、品牌/合规错误，原则上不可交付。",
    "P1": "严重交付错误：商品主体变弱、材质错、关键细节丢失、水印残留，需重试或人工修。",
    "P2": "主要质感问题：AI 平滑、阴影假、背景抢主体、皮肤/甲面塑料感，影响可信度。",
    "P3": "轻微审美问题：色调、构图、装饰、风格一致性可优化，但不一定阻断演示。",
}


@dataclass(frozen=True, slots=True)
class ImagePair:
    sequence: int
    source_path: Path
    result_path: Path
    label: str


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--known-issue",
        action="append",
        default=[],
        help="人工确认的问题类型，可带序号，例如 nail_decoration_wrong_side 或 nail_decoration_wrong_side:6",
    )
    args = parser.parse_args()

    pairs = find_pairs(args.results_dir)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    database = load_database()

    report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = LOG_DIR / f"质量错误分析_{report_time}.md"
    issues = analyze_pairs(pairs=pairs, known_issues=parse_known_issues(args.known_issue))

    update_database(database=database, issues=issues)
    DATABASE_PATH.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(pairs=pairs, issues=issues), encoding="utf-8")

    print(json.dumps({
        "report": str(report_path),
        "database": str(DATABASE_PATH),
        "pairs": len(pairs),
        "issues": len(issues),
    }, ensure_ascii=False, indent=2))


def find_pairs(results_dir: Path) -> list[ImagePair]:
    pairs: list[ImagePair] = []
    for source_path in sorted(results_dir.glob("原图*_*.png")):
        sequence = parse_sequence(source_path.name, "原图")
        if sequence is None:
            continue
        result_candidates = sorted(results_dir.glob(f"结果{sequence}_*.png"))
        if not result_candidates:
            continue
        result_path = result_candidates[-1]
        label = "GPT" if "GPT" in result_path.name else "Doubao" if "Doubao" in result_path.name else "unknown"
        pairs.append(ImagePair(sequence=sequence, source_path=source_path, result_path=result_path, label=label))
    return pairs


def parse_sequence(filename: str, prefix: str) -> int | None:
    if not filename.startswith(prefix):
        return None
    digits = []
    for char in filename[len(prefix):]:
        if not char.isdigit():
            break
        digits.append(char)
    if not digits:
        return None
    return int("".join(digits))


def parse_known_issues(raw_items: list[str]) -> dict[str, set[int] | None]:
    parsed: dict[str, set[int] | None] = {}
    for raw_item in raw_items:
        name, _, sequence_text = raw_item.partition(":")
        name = name.strip()
        if not name:
            continue
        if not sequence_text:
            parsed[name] = None
            continue
        sequence_set = parsed.setdefault(name, set())
        if sequence_set is None:
            continue
        for chunk in sequence_text.split(","):
            try:
                sequence_set.add(int(chunk.strip()))
            except ValueError:
                continue
    return parsed


def analyze_pairs(*, pairs: list[ImagePair], known_issues: dict[str, set[int] | None]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for pair in pairs:
        source_image = Image.open(pair.source_path)
        result_image = Image.open(pair.result_path)
        assessment = evaluate_generated_image(result_image, source_image=source_image, threshold=72)

        for reason in assessment.reasons:
            severity = classify_reason(reason)
            issues.append({
                "id": stable_issue_id(reason),
                "severity": severity,
                "title": reason,
                "pair_sequence": pair.sequence,
                "provider_label": pair.label,
                "source_path": str(pair.source_path),
                "result_path": str(pair.result_path),
                "score": assessment.score,
                "status": "auto_detected",
                "root_cause": root_cause_for_reason(reason),
                "fix_strategy": fix_strategy_for_reason(reason),
            })

    nail_issue_sequences = known_issues.get("nail_decoration_wrong_side")
    if "nail_decoration_wrong_side" in known_issues:
        for pair in pairs:
            if nail_issue_sequences is not None and pair.sequence not in nail_issue_sequences:
                continue
            issues.append({
                "id": "nail_decoration_wrong_side",
                "severity": "P0",
                "title": "手心朝上时，美甲贴钻被画到指甲内侧/掌心侧",
                "pair_sequence": pair.sequence,
                "provider_label": pair.label,
                "source_path": str(pair.source_path),
                "result_path": str(pair.result_path),
                "score": None,
                "status": "human_confirmed",
                "root_cause": (
                    "图生图模型把可见的透明甲尖误判为可贴钻的甲面，缺少手心/手背方向和指甲盖外侧的解剖约束。"
                ),
                "fix_strategy": (
                    "在提示词编译层强制追加手部与美甲方向约束；贴钻只能位于手背侧甲面。"
                    "质检复盘时将人体结构错误列为 P0，不允许作为可交付结果。"
                ),
            })

    return issues


def classify_reason(reason: str) -> str:
    if any(keyword in reason for keyword in ("人体", "手心", "指甲内侧", "掌心侧", "结构")):
        return "P0"
    if any(keyword in reason for keyword in ("商品主体", "链条", "吊坠", "金属", "珠宝", "水印")):
        return "P1"
    if any(keyword in reason for keyword in ("纹理", "柔化", "降噪", "棚拍", "阴影", "过曝")):
        return "P2"
    return "P3"


def stable_issue_id(reason: str) -> str:
    if "商品主体" in reason or "链条" in reason or "吊坠" in reason:
        return "product_subject_detail_loss"
    if "纹理" in reason or "微纹理" in reason:
        return "background_microtexture_loss"
    if "全局边缘" in reason or "柔化" in reason or "降噪" in reason:
        return "global_detail_softening"
    if "尺寸" in reason:
        return "output_resolution_loss"
    return "misc_quality_issue"


def root_cause_for_reason(reason: str) -> str:
    if "商品主体" in reason:
        return "模型优先优化整体画面氛围，商品局部高频细节没有被作为第一优化目标。"
    if "纹理" in reason:
        return "图生图整体重绘倾向会把真实照片里的噪点、桌面纹理和局部不完美当成瑕疵抹掉。"
    if "全局边缘" in reason:
        return "模型生成过程带来整体柔化或降噪，导致真实拍摄边缘和材质细节下降。"
    if "尺寸" in reason:
        return "输出尺寸或裁切策略导致结果低于原图交付清晰度。"
    return "需要人工复盘确认。"


def fix_strategy_for_reason(reason: str) -> str:
    if "商品主体" in reason:
        return "提示词和质检中提高商品主体权重：链条、吊坠、金属高光、珠宝边缘必须优先于背景美化。"
    if "纹理" in reason:
        return "降低整体重绘强度，明确保留桌面纹理、噪点、皮肤纹理、甲面反光和局部不完美。"
    if "全局边缘" in reason:
        return "增加原图参照质检，低于原图边缘细节阈值时自动重试或拒绝交付。"
    if "尺寸" in reason:
        return "提高输出尺寸策略，避免主体缩小和结果尺寸明显低于原图。"
    return "进入人工错题集，补充专门约束。"


def load_database() -> dict[str, Any]:
    if not DATABASE_PATH.exists():
        return {
            "version": 1,
            "updated_at": None,
            "severity_levels": SEVERITY_LEVELS,
            "issues": {},
        }
    try:
        return json.loads(DATABASE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = DATABASE_PATH.with_suffix(f".broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        DATABASE_PATH.replace(backup)
        return {
            "version": 1,
            "updated_at": None,
            "severity_levels": SEVERITY_LEVELS,
            "issues": {},
        }


def update_database(*, database: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    database["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.setdefault("severity_levels", SEVERITY_LEVELS)
    issue_map = database.setdefault("issues", {})

    for issue in issues:
        item = issue_map.setdefault(
            issue["id"],
            {
                "id": issue["id"],
                "severity": issue["severity"],
                "title": issue["title"],
                "count": 0,
                "root_causes": [],
                "fix_strategies": [],
                "examples": [],
            },
        )
        item["severity"] = min_severity(item.get("severity", issue["severity"]), issue["severity"])
        item["count"] = int(item.get("count", 0)) + 1
        append_unique(item["root_causes"], issue["root_cause"])
        append_unique(item["fix_strategies"], issue["fix_strategy"])
        item["examples"].append({
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pair_sequence": issue["pair_sequence"],
            "provider_label": issue["provider_label"],
            "source_path": issue["source_path"],
            "result_path": issue["result_path"],
            "score": issue["score"],
            "status": issue["status"],
        })
        item["examples"] = item["examples"][-20:]


def min_severity(left: str, right: str) -> str:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return left if order.get(left, 9) <= order.get(right, 9) else right


def append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def render_report(*, pairs: list[ImagePair], issues: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {"P0": [], "P1": [], "P2": [], "P3": []}
    for issue in issues:
        grouped.setdefault(issue["severity"], []).append(issue)

    lines = [
        f"# 质量错误分析 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- 分析图片组数：{len(pairs)}",
        f"- 错误知识数据库：{DATABASE_PATH}",
        "",
        "## 严重性定义",
        *[f"- {level}：{description}" for level, description in SEVERITY_LEVELS.items()],
        "",
    ]

    for severity in ("P0", "P1", "P2", "P3"):
        bucket = grouped.get(severity, [])
        lines.extend([f"## {severity} 问题（{len(bucket)}）"])
        if not bucket:
            lines.extend(["- 暂无", ""])
            continue
        for issue in bucket:
            lines.append(
                f"- #{issue['pair_sequence']} `{issue['provider_label']}` {issue['title']} "
                f"({issue['status']})"
            )
            lines.append(f"  - 原因：{issue['root_cause']}")
            lines.append(f"  - 改进：{issue['fix_strategy']}")
            lines.append(f"  - 结果图：{issue['result_path']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
