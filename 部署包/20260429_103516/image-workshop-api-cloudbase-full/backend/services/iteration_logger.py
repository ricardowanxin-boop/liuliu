"""Generation iteration logging and milestone summaries."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from PIL import Image, ImageFilter, ImageOps, ImageStat

from backend.services.image_preprocess import load_image_from_bytes, pil_image_to_png_bytes
from backend.services.quality_control import QualityAssessment


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = PROJECT_ROOT / "日志"
ITERATION_DIR = LOG_ROOT / "迭代记录"
SUMMARY_DIR = LOG_ROOT / "阶段总结"
INDEX_PATH = LOG_ROOT / "generation_iteration_index.json"
STAGE_SIZE = 5
SWITCH_REVIEW_LIMIT = 20
_INDEX_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class IterationLogResult:
    """Metadata returned after writing one iteration log."""

    iteration: int
    log_path: str
    result_path: str | None
    source_path: str
    stage_summary_path: str | None = None
    switch_review_path: str | None = None
    switch_warning: str | None = None


def write_generation_iteration_log(
    *,
    source_name: str,
    source_image_bytes: bytes,
    generated_image: Image.Image,
    provider_type: str,
    model: str,
    prompt: str,
    compiled_prompt: str,
    attempt: int,
    status: str,
    assessment: QualityAssessment | None,
    cleanup_note: str | None,
    job_id: str | None = None,
    file_index: int | None = None,
    error: str | None = None,
) -> IterationLogResult:
    """Persist source/result images plus a detailed markdown critique."""
    _ensure_dirs()
    with _INDEX_LOCK:
        index = _load_index()
        iteration = int(index.get("next_iteration", 1))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        folder = ITERATION_DIR / f"{iteration:04d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_safe_name(source_name)}"
        folder.mkdir(parents=True, exist_ok=True)

        source_image = load_image_from_bytes(source_image_bytes)
        source_path = folder / "原图.png"
        result_path = folder / "结果.png"
        source_path.write_bytes(pil_image_to_png_bytes(source_image))
        result_path.write_bytes(pil_image_to_png_bytes(generated_image))

        comparison = _compare_images(source_image, generated_image)
        switch_warning = _build_switch_warning(iteration, assessment)
        log_path = folder / "记录.md"
        log_path.write_text(
            _render_iteration_markdown(
                iteration=iteration,
                now=now,
                source_name=source_name,
                provider_type=provider_type,
                model=model,
                attempt=attempt,
                status=status,
                source_path=source_path,
                result_path=result_path,
                prompt=prompt,
                compiled_prompt=compiled_prompt,
                assessment=assessment,
                comparison=comparison,
                cleanup_note=cleanup_note,
                error=error,
                switch_warning=switch_warning,
                job_id=job_id,
                file_index=file_index,
            ),
            encoding="utf-8",
        )

        record = {
            "iteration": iteration,
            "created_at": now,
            "job_id": job_id,
            "file_index": file_index,
            "source_name": source_name,
            "provider_type": provider_type,
            "model": model,
            "attempt": attempt,
            "status": status,
            "quality_score": assessment.score if assessment else None,
            "quality_passed": assessment.passed if assessment else None,
            "quality_reasons": assessment.reasons if assessment else [],
            "log_path": str(log_path),
            "source_path": str(source_path),
            "result_path": str(result_path),
            "switch_warning": switch_warning,
        }
        index.setdefault("records", []).append(record)
        index["next_iteration"] = iteration + 1
        _save_index(index)

        stage_summary_path = None
        switch_review_path = None
        if iteration % STAGE_SIZE == 0:
            stage_summary_path = str(write_stage_summary(index=index, end_iteration=iteration))

        if iteration >= SWITCH_REVIEW_LIMIT and iteration % STAGE_SIZE == 0:
            switch_review_path = str(write_switch_review(index=index, end_iteration=iteration))

        return IterationLogResult(
            iteration=iteration,
            log_path=str(log_path),
            result_path=str(result_path),
            source_path=str(source_path),
            stage_summary_path=stage_summary_path,
            switch_review_path=switch_review_path,
            switch_warning=switch_warning,
        )


def write_generation_failure_log(
    *,
    source_name: str,
    source_image_bytes: bytes,
    provider_type: str,
    model: str,
    prompt: str,
    compiled_prompt: str,
    attempt: int,
    error: str,
    job_id: str | None = None,
    file_index: int | None = None,
) -> IterationLogResult:
    """Persist a failed provider/preprocess attempt so paid failures are not lost."""
    _ensure_dirs()
    with _INDEX_LOCK:
        index = _load_index()
        iteration = int(index.get("next_iteration", 1))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        folder = ITERATION_DIR / f"{iteration:04d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_safe_name(source_name)}_failed"
        folder.mkdir(parents=True, exist_ok=True)

        source_image = load_image_from_bytes(source_image_bytes)
        source_path = folder / "原图.png"
        source_path.write_bytes(pil_image_to_png_bytes(source_image))
        switch_warning = _build_switch_warning(iteration, None)
        log_path = folder / "记录.md"
        log_path.write_text(
            _render_iteration_markdown(
                iteration=iteration,
                now=now,
                source_name=source_name,
                provider_type=provider_type,
                model=model,
                attempt=attempt,
                status="failed",
                source_path=source_path,
                result_path=None,
                prompt=prompt,
                compiled_prompt=compiled_prompt,
                assessment=None,
                comparison=_empty_comparison(source_image),
                cleanup_note=None,
                error=error,
                switch_warning=switch_warning,
                job_id=job_id,
                file_index=file_index,
            ),
            encoding="utf-8",
        )

        record = {
            "iteration": iteration,
            "created_at": now,
            "job_id": job_id,
            "file_index": file_index,
            "source_name": source_name,
            "provider_type": provider_type,
            "model": model,
            "attempt": attempt,
            "status": "failed",
            "quality_score": None,
            "quality_passed": False,
            "quality_reasons": [error],
            "log_path": str(log_path),
            "source_path": str(source_path),
            "result_path": None,
            "switch_warning": switch_warning,
        }
        index.setdefault("records", []).append(record)
        index["next_iteration"] = iteration + 1
        _save_index(index)

        stage_summary_path = None
        switch_review_path = None
        if iteration % STAGE_SIZE == 0:
            stage_summary_path = str(write_stage_summary(index=index, end_iteration=iteration))
        if iteration >= SWITCH_REVIEW_LIMIT and iteration % STAGE_SIZE == 0:
            switch_review_path = str(write_switch_review(index=index, end_iteration=iteration))

        return IterationLogResult(
            iteration=iteration,
            log_path=str(log_path),
            result_path=None,
            source_path=str(source_path),
            stage_summary_path=stage_summary_path,
            switch_review_path=switch_review_path,
            switch_warning=switch_warning,
        )


def review_log_milestones() -> list[str]:
    """Create any missing stage summaries; safe for a background scheduler."""
    _ensure_dirs()
    index = _load_index()
    records = index.get("records", [])
    created: list[str] = []
    if not isinstance(records, list):
        return created

    max_iteration = max((int(record.get("iteration", 0)) for record in records), default=0)
    for end_iteration in range(STAGE_SIZE, max_iteration + 1, STAGE_SIZE):
        path = _stage_summary_path(end_iteration)
        if not path.exists():
            created.append(str(write_stage_summary(index=index, end_iteration=end_iteration)))

    if max_iteration >= SWITCH_REVIEW_LIMIT:
        review_path = _switch_review_path(max_iteration)
        if not review_path.exists():
            created.append(str(write_switch_review(index=index, end_iteration=max_iteration)))
    return created


def write_stage_summary(*, index: dict[str, Any], end_iteration: int) -> Path:
    """Write one milestone summary for every five generated attempts."""
    records = _records_in_range(index, end_iteration - STAGE_SIZE + 1, end_iteration)
    path = _stage_summary_path(end_iteration)
    if not records:
        return path

    fail_count = sum(1 for record in records if not record.get("quality_passed"))
    avg_score = _average([record.get("quality_score") for record in records])
    reason_counts = _count_reasons(records)
    action_items = _build_stage_action_items(reason_counts, avg_score)

    path.write_text(
        "\n".join(
            [
                f"# 阶段总结 {end_iteration - STAGE_SIZE + 1:04d}-{end_iteration:04d}",
                "",
                f"- 生成次数：{len(records)}",
                f"- 平均质检分：{avg_score:.1f}",
                f"- 不合格次数：{fail_count}",
                f"- 主要问题：{_format_reason_counts(reason_counts)}",
                "",
                "## 细节复盘",
                *[
                    f"- #{record['iteration']:04d} `{record.get('model', '')}` "
                    f"{record.get('quality_score', 'NA')} 分："
                    f"{'；'.join(record.get('quality_reasons') or ['无'])} "
                    f"([记录]({record.get('log_path')}))"
                    for record in records
                ],
                "",
                "## 下一轮改进动作",
                *[f"- {item}" for item in action_items],
                "",
                "## 是否考虑换方案",
                _build_switch_advice(end_iteration=end_iteration, avg_score=avg_score, fail_count=fail_count, reason_counts=reason_counts),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def write_switch_review(*, index: dict[str, Any], end_iteration: int) -> Path:
    """Write a stronger review once the experiment reaches the 20-attempt limit."""
    records = _records_in_range(index, max(1, end_iteration - SWITCH_REVIEW_LIMIT + 1), end_iteration)
    path = _switch_review_path(end_iteration)
    avg_score = _average([record.get("quality_score") for record in records])
    fail_count = sum(1 for record in records if not record.get("quality_passed"))
    reason_counts = _count_reasons(records)
    should_switch = end_iteration >= SWITCH_REVIEW_LIMIT and (
        avg_score < 78
        or fail_count >= max(6, len(records) // 3)
        or any(
            count >= 5 and any(keyword in reason for keyword in ("过度平滑", "商品主体", "透明", "手部"))
            for reason, count in reason_counts.items()
        )
    )
    conclusion = (
        "建议准备切换方案：当前单次图生图流程仍未稳定解决真实纹理和商品质感问题。"
        if should_switch
        else "可以继续优化当前方案，但下一阶段仍需严控真实纹理和商品主体增强。"
    )
    path.write_text(
        "\n".join(
            [
                f"# 20 次迭代换方案评估（截至 #{end_iteration:04d}）",
                "",
                f"- 样本数：{len(records)}",
                f"- 平均质检分：{avg_score:.1f}",
                f"- 不合格次数：{fail_count}",
                f"- 高频问题：{_format_reason_counts(reason_counts)}",
                "",
                "## 结论",
                conclusion,
                "",
                "## 可选替代路径",
                "- 使用局部 mask / 局部重绘：保护商品主体，只轻改背景。",
                "- 拆分流程：去水印、商品局部增强、轻度调色分阶段完成。",
                "- 对珠宝、透明托盘、手部等高难区域使用专门局部修图方案，而不是单次整体图生图。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _render_iteration_markdown(
    *,
    iteration: int,
    now: str,
    source_name: str,
    provider_type: str,
    model: str,
    attempt: int,
    status: str,
    source_path: Path,
    result_path: Path | None,
    prompt: str,
    compiled_prompt: str,
    assessment: QualityAssessment | None,
    comparison: dict[str, Any],
    cleanup_note: str | None,
    error: str | None,
    switch_warning: str | None,
    job_id: str | None,
    file_index: int | None,
) -> str:
    quality_lines = (
        [
            f"- 质检分：{assessment.score}",
            f"- 是否通过：{'是' if assessment.passed else '否'}",
            f"- 质检原因：{'；'.join(assessment.reasons)}",
            f"- 重试建议：{assessment.retry_instruction}",
        ]
        if assessment
        else ["- 质检分：未启用或未生成", "- 是否通过：未知"]
    )
    issue_lines = comparison["issues"] or ["未检测到明显的全局级问题，仍需人工看商品细节。"]
    return "\n".join(
        [
            f"# 生成迭代 #{iteration:04d}",
            "",
            f"- 时间：{now}",
            f"- 原图文件：{source_name}",
            f"- Job ID：{job_id or '无'}",
            f"- 文件序号：{file_index if file_index is not None else '无'}",
            f"- Provider：{provider_type}",
            f"- Model：{model}",
            f"- 尝试次数序号：{attempt}",
            f"- 状态：{status}",
            f"- 原图路径：{source_path}",
            f"- 结果路径：{result_path or '无结果图'}",
            f"- 清理说明：{cleanup_note or '无'}",
            f"- 错误：{error or '无'}",
            "",
            "## 自动质检",
            *quality_lines,
            "",
            "## 原图 vs 结果图差距",
            f"- 原图尺寸：{comparison['source_size']}",
            f"- 结果尺寸：{comparison['result_size']}",
            f"- 亮度变化：{comparison['luma_delta']:+.1f}",
            f"- 饱和度变化：{comparison['saturation_delta']:+.1f}",
            f"- 全局细节变化：{comparison['edge_delta']:+.2f}",
            f"- 背景纹理变化：{comparison['background_texture_delta']:+.2f}",
            f"- 商品主体细节变化：{comparison['center_detail_delta']:+.2f}",
            "",
            "## 找茬记录",
            *[f"- {line}" for line in issue_lines],
            "",
            "## 本轮提示词",
            "```text",
            prompt.strip(),
            "```",
            "",
            "## 实际编译提示词",
            "```text",
            compiled_prompt.strip(),
            "```",
            "",
            "## 换方案提醒",
            switch_warning or "当前仍在 20 次迭代观察期内，继续用日志驱动优化。",
            "",
        ]
    )


def _compare_images(source: Image.Image, result: Image.Image) -> dict[str, Any]:
    source_sample = _prepare_sample(source)
    result_sample = _prepare_sample(result)
    source_metrics = _image_metrics(source_sample)
    result_metrics = _image_metrics(result_sample)

    issues: list[str] = []
    edge_delta = result_metrics["edge"] - source_metrics["edge"]
    bg_delta = result_metrics["background_texture"] - source_metrics["background_texture"]
    center_delta = result_metrics["center_detail"] - source_metrics["center_detail"]
    luma_delta = result_metrics["luma"] - source_metrics["luma"]
    saturation_delta = result_metrics["saturation"] - source_metrics["saturation"]

    if bg_delta < -2.5:
        issues.append("结果图背景/桌面纹理低于原图，可能把真实细节抹平。")
    if center_delta < -1.6:
        issues.append("商品主体边缘和细节弱于原图，珠子/金属/珍珠增强不足。")
    if edge_delta < -2.2:
        issues.append("全局边缘细节下降，存在整体降噪或柔化倾向。")
    if luma_delta > 34:
        issues.append("结果明显变亮，需警惕冷白棚拍或过曝感。")
    if saturation_delta > 32:
        issues.append("结果饱和度提升较大，可能出现 AI 广告图质感。")
    if result_metrics["background_texture"] < 2.7 and result_metrics["luma_std"] < 18:
        issues.append("结果背景过平滑，像被均匀涂抹，缺少桌面反光过渡和噪点。")
    if result_metrics["center_detail"] < 7.4:
        issues.append("结果商品区域细节不够，电商主体没有明显变高级。")

    return {
        "source_size": f"{source.width} x {source.height}",
        "result_size": f"{result.width} x {result.height}",
        "luma_delta": luma_delta,
        "saturation_delta": saturation_delta,
        "edge_delta": edge_delta,
        "background_texture_delta": bg_delta,
        "center_detail_delta": center_delta,
        "issues": issues,
    }


def _empty_comparison(source: Image.Image) -> dict[str, Any]:
    return {
        "source_size": f"{source.width} x {source.height}",
        "result_size": "无结果图",
        "luma_delta": 0,
        "saturation_delta": 0,
        "edge_delta": 0,
        "background_texture_delta": 0,
        "center_detail_delta": 0,
        "issues": ["本轮没有生成有效结果图，先记录失败原因；不进入画质差距判断。"],
    }


def _image_metrics(image: Image.Image) -> dict[str, float]:
    rgb = image.convert("RGB")
    gray = ImageOps.grayscale(rgb)
    hsv = rgb.convert("HSV")
    return {
        "luma": float(ImageStat.Stat(gray).mean[0]),
        "luma_std": float(ImageStat.Stat(gray).stddev[0]),
        "saturation": float(ImageStat.Stat(hsv).mean[1]),
        "edge": float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]),
        "background_texture": _background_texture(gray),
        "center_detail": _center_detail(gray),
    }


def _prepare_sample(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    rgb.thumbnail((480, 480), Image.Resampling.LANCZOS)
    return rgb


def _background_texture(gray: Image.Image) -> float:
    width, height = gray.size
    boxes = [
        (0, 0, int(width * 0.28), int(height * 0.28)),
        (int(width * 0.72), 0, width, int(height * 0.28)),
        (0, int(height * 0.72), int(width * 0.28), height),
        (int(width * 0.72), int(height * 0.72), width, height),
    ]
    values = [
        float(ImageStat.Stat(gray.crop(box).filter(ImageFilter.FIND_EDGES)).mean[0])
        for box in boxes
        if box[2] > box[0] and box[3] > box[1]
    ]
    return sum(values) / len(values) if values else 0


def _center_detail(gray: Image.Image) -> float:
    width, height = gray.size
    center = gray.crop((int(width * 0.22), int(height * 0.20), int(width * 0.78), int(height * 0.82)))
    return float(ImageStat.Stat(center.filter(ImageFilter.FIND_EDGES)).mean[0])


def _records_in_range(index: dict[str, Any], start: int, end: int) -> list[dict[str, Any]]:
    records = index.get("records", [])
    if not isinstance(records, list):
        return []
    return [
        record
        for record in records
        if start <= int(record.get("iteration", 0)) <= end
    ]


def _count_reasons(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for reason in record.get("quality_reasons") or []:
            key = _reason_bucket(str(reason))
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def _reason_bucket(reason: str) -> str:
    if "ZenMux" in reason or "断开" in reason or "连接" in reason or "超时" in reason:
        return "模型通道不稳定"
    if "平滑" in reason or "柔化" in reason or "微纹理" in reason:
        return "过度平滑/微纹理不足"
    if "商品主体" in reason or "珠子" in reason or "金属" in reason or "珍珠" in reason:
        return "商品主体增强不足"
    if "背景" in reason or "棚拍" in reason:
        return "背景棚拍感"
    if "光影" in reason or "阴影" in reason:
        return "光影不自然"
    if "饱和" in reason:
        return "色彩过饱和"
    return reason[:24]


def _format_reason_counts(reason_counts: dict[str, int]) -> str:
    if not reason_counts:
        return "暂无稳定高频问题"
    return "；".join(f"{reason} x{count}" for reason, count in list(reason_counts.items())[:5])


def _build_stage_action_items(reason_counts: dict[str, int], avg_score: float) -> list[str]:
    items: list[str] = []
    if any("模型通道" in key for key in reason_counts):
        items.append("先稳定 GPT-image-2 调用通道：ZenMux 断连时不要继续批量烧调用，优先确认通道状态或准备备用兼容接口。")
    if any("过度平滑" in key for key in reason_counts):
        items.append("下一轮降低整体重绘倾向，继续加强真实纹理、噪点、桌面反光过渡和皮肤/甲面细节保留。")
    if any("商品主体" in key for key in reason_counts):
        items.append("下一轮把商品主体提升为第一优先级：珠子通透度、金属高光、珍珠洁净度和边缘清晰度必须明显提升。")
    if any("背景" in key for key in reason_counts):
        items.append("下一轮限制背景变化幅度，背景只做轻度整理，不允许抢过商品主体。")
    if avg_score < 72:
        items.append("平均分低于阈值，建议减少单轮批量，先用 1 张样图调参数。")
    if not items:
        items.append("保持当前策略，下一轮重点观察透明托盘、手部和商品局部细节。")
    return items


def _build_switch_advice(*, end_iteration: int, avg_score: float, fail_count: int, reason_counts: dict[str, int]) -> str:
    if end_iteration < SWITCH_REVIEW_LIMIT:
        return "未满 20 次，继续按日志错题集迭代。若同类问题连续出现 3 次，应提前考虑局部重绘或分阶段方案。"
    if avg_score < 78 or fail_count >= 6 or any(count >= 5 for count in reason_counts.values()):
        return "已达到 20 次观察点，当前单次整体图生图仍不稳定，建议准备切换到局部 mask / 分阶段修图方案。"
    return "20 次内质量已有改善，可以继续使用当前方案，但仍需保留换方案预案。"


def _build_switch_warning(iteration: int, assessment: QualityAssessment | None) -> str | None:
    if iteration < SWITCH_REVIEW_LIMIT:
        return None
    if assessment and assessment.score >= 80 and assessment.passed:
        return None
    return "已达到 20 次迭代观察线，本轮仍未稳定达标，应考虑切换局部重绘或分阶段修图方案。"


def _average(values: list[Any]) -> float:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return sum(numbers) / len(numbers) if numbers else 0


def _stage_summary_path(end_iteration: int) -> Path:
    start = end_iteration - STAGE_SIZE + 1
    return SUMMARY_DIR / f"阶段总结_{start:04d}-{end_iteration:04d}.md"


def _switch_review_path(end_iteration: int) -> Path:
    return SUMMARY_DIR / f"换方案评估_截至{end_iteration:04d}.md"


def _ensure_dirs() -> None:
    ITERATION_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return {"next_iteration": 1, "records": []}
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = INDEX_PATH.with_suffix(".broken.json")
        INDEX_PATH.replace(backup)
        return {"next_iteration": 1, "records": []}


def _save_index(index: dict[str, Any]) -> None:
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    stem = Path(value).stem or "image"
    cleaned = re.sub(r"[^\w.-]+", "-", stem, flags=re.UNICODE).strip("-.")
    return cleaned[:48] or "image"
