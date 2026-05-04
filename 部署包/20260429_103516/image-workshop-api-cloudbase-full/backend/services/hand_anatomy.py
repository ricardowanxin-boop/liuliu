"""MediaPipe-based hand and manicure anatomy checks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps, ImageStat


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "hand_landmarker.task"
MAX_MEDIAPIPE_SIZE = 1024
SOURCE_HAND_DETECTION_CONFIDENCE = 0.12
RESULT_HAND_DETECTION_CONFIDENCE = 0.32
PALM_SIDE_HIGHLIGHT_THRESHOLD = 18.0
NAIL_KEYWORDS = (
    "指甲",
    "美甲",
    "贴钻",
    "钻甲",
    "透明甲",
    "甲面",
    "甲片",
    "水钻",
    "亮片",
    "nail",
    "manicure",
)


@dataclass(frozen=True, slots=True)
class HandGeometry:
    """A compact hand landmark analysis result."""

    detected: bool
    handedness: str | None
    handedness_score: float
    landmarks: tuple[tuple[float, float, float], ...]
    orientation_sign: float
    palm_center: tuple[float, float] | None
    bbox: tuple[float, float, float, float] | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class HandAnatomyIssue:
    """One local hand anatomy quality issue."""

    reason: str
    penalty: int
    retry_instruction: str


def prompt_needs_hand_anatomy(prompt: str | None) -> bool:
    """Return true when the prompt mentions nails or manicure-like details."""
    text = (prompt or "").lower()
    return any(keyword.lower() in text for keyword in NAIL_KEYWORDS)


def build_source_hand_anatomy_prompt(source_image: Image.Image, *, prompt: str | None) -> str | None:
    """
    Build source-aware constraints from MediaPipe landmarks.

    This is intentionally text-only: it gives the image model a hard anatomy
    contract before the paid generation call, without calling another model.
    """
    if not prompt_needs_hand_anatomy(prompt):
        return None

    source_hand = analyze_hand_geometry(source_image, confidence=SOURCE_HAND_DETECTION_CONFIDENCE)
    if source_hand.error:
        return None
    if not source_hand.detected:
        return None

    handedness = source_hand.handedness or "未知左右手"
    palm_hint = _describe_palm_orientation(source_hand)
    return "\n".join(
        [
            "本地 MediaPipe Hands 手部结构约束：",
            f"- 原图已识别到 1 只手，类型约为 {handedness}，{palm_hint}；生成时必须保持原图手势、手掌朝向、指尖方向和 21 个关键点拓扑关系。",
            "- 这是结构锁定，不是参考建议：不要把手掌重画成另一种姿态，不要改变手指张开角度、掌心/手背朝向、指尖大方向和商品佩戴关系。",
            "- 透明带钻美甲只能附着在指甲盖外表面，也就是手背侧甲面；不得把钻饰画到掌心侧、指腹侧、甲下、指甲内侧或透明甲片背面。",
            "- 如果手心朝上导致外侧甲面不可充分露出，宁可让钻饰少一些、只在可见外甲面边缘出现，也不要把钻移动到掌心侧来展示；透明甲可保留清透边缘高光。",
            "- 商品优先于背景：保留原图吊坠、链条、金属镶边、宝石轮廓和商品在手上的位置，不要为了场景美化而重绘或缩小商品。",
            "- 生成后会用 MediaPipe Hands 复检手部关键点；如果结果图无法稳定识别手部或手势拓扑明显翻转，将视为致命质量错误。",
        ]
    )


def evaluate_hand_anatomy(
    result_image: Image.Image,
    *,
    source_image: Image.Image | None,
    prompt: str | None,
) -> list[HandAnatomyIssue]:
    """Run local MediaPipe hand checks for nail/manicure image generations."""
    if not prompt_needs_hand_anatomy(prompt):
        return []

    result_hand = analyze_hand_geometry(result_image, confidence=RESULT_HAND_DETECTION_CONFIDENCE)
    if result_hand.error:
        return [
            HandAnatomyIssue(
                reason="MediaPipe 手部质检未能稳定运行，涉及美甲/手部编辑的结果需要人工复核",
                penalty=12,
                retry_instruction="保持原图手部结构，不要重绘手掌、指腹、指甲朝向或贴钻位置。",
            )
        ]

    source_hand = (
        analyze_hand_geometry(source_image, confidence=SOURCE_HAND_DETECTION_CONFIDENCE)
        if source_image is not None
        else None
    )
    issues: list[HandAnatomyIssue] = []

    if source_image is not None and source_hand and not source_hand.detected:
        issues.append(
            HandAnatomyIssue(
                reason="原图手部未能被 MediaPipe 稳定识别，涉及美甲/手部改造的结果需要人工复核",
                penalty=10,
                retry_instruction="减少手部改造幅度，保留原图手势、手心朝向和指甲可见边缘。",
            )
        )

    if source_hand and source_hand.detected and not result_hand.detected:
        issues.append(
            HandAnatomyIssue(
                reason="MediaPipe 未能在结果图中稳定识别手部 21 个关键点，手型、指甲朝向或贴钻位置可能已经不符合真实人体结构",
                penalty=26,
                retry_instruction=(
                    "保持原图手心朝向和手指关键点拓扑，不要翻转手掌；透明带钻美甲只能在手背侧甲面，"
                    "掌心侧、指腹侧和指甲内侧禁止出现钻饰。"
                ),
            )
        )
        return issues

    if not result_hand.detected:
        return issues

    if source_hand and source_hand.detected:
        pose_delta = _pose_delta(source_hand, result_hand)
        if pose_delta is not None and pose_delta > 0.38:
            issues.append(
                HandAnatomyIssue(
                    reason=f"MediaPipe 手部关键点相对结构变化过大（{pose_delta:.2f}），可能出现手势翻转、指尖方向错误或美甲贴钻位置穿帮",
                    penalty=18,
                    retry_instruction=(
                        "把原图手势作为硬约束，保持手指张开角度、掌心朝向和商品位置；只做轻度透明甲边缘修饰，"
                        "不要重构手部或让钻饰漂到指腹、掌心侧。"
                    ),
                )
            )

        if _orientation_flipped(source_hand, result_hand):
            issues.append(
                HandAnatomyIssue(
                    reason="MediaPipe 检测到手掌屏幕拓扑方向疑似翻转，手心/手背逻辑可能被画反",
                    penalty=22,
                    retry_instruction=(
                        "重新遵循原图手掌朝向：手心朝上时指腹面向镜头，贴钻只在手背侧甲面，"
                        "不要为了展示美甲而翻转手掌或旋转手指。"
                    ),
                )
            )

        inner_side_score = _inner_side_highlight_score(source_image, result_image, result_hand)
        if inner_side_score > PALM_SIDE_HIGHLIGHT_THRESHOLD:
            issues.append(
                HandAnatomyIssue(
                    reason=f"结果图指尖掌心侧疑似新增异常高亮贴钻痕迹（{inner_side_score:.1f}），可能把钻画到了指甲内侧",
                    penalty=24,
                    retry_instruction=(
                        "把水钻、亮片、闪点全部移回指甲盖外表面；手心朝上时掌心侧和指腹侧只能保留皮肤、自然阴影和透明甲边缘。"
                    ),
                )
            )

    return issues


def analyze_hand_geometry(image: Image.Image | None, *, confidence: float | None = None) -> HandGeometry:
    """Detect the most confident hand with MediaPipe Tasks API."""
    if image is None:
        return _empty_geometry(error="no_image")

    model_path = _model_path()
    if not model_path.exists():
        return _empty_geometry(error=f"missing_model:{model_path}")

    try:
        mp, hand_landmarker, base_options = _mediapipe_imports()
    except Exception as exc:
        return _empty_geometry(error=f"missing_mediapipe:{exc}")

    try:
        sample = _prepare_mediapipe_image(image)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=sample)
        detection_confidence = confidence if confidence is not None else RESULT_HAND_DETECTION_CONFIDENCE
        options = hand_landmarker.HandLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_path=str(model_path)),
            num_hands=2,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=detection_confidence,
            min_tracking_confidence=detection_confidence,
        )
        with hand_landmarker.HandLandmarker.create_from_options(options) as landmarker:
            result = landmarker.detect(mp_image)
    except Exception as exc:
        return _empty_geometry(error=f"mediapipe_error:{exc}")

    if not result.hand_landmarks:
        return _empty_geometry(error=None)

    hand_index = _best_hand_index(result.handedness)
    landmarks = tuple((float(item.x), float(item.y), float(item.z)) for item in result.hand_landmarks[hand_index])
    handedness_name = None
    handedness_score = 0.0
    if result.handedness and result.handedness[hand_index]:
        top = result.handedness[hand_index][0]
        handedness_name = getattr(top, "category_name", None)
        handedness_score = float(getattr(top, "score", 0.0) or 0.0)

    xs = [point[0] for point in landmarks]
    ys = [point[1] for point in landmarks]
    palm_points = [landmarks[index] for index in (0, 5, 9, 13, 17)]
    palm_center = (
        sum(point[0] for point in palm_points) / len(palm_points),
        sum(point[1] for point in palm_points) / len(palm_points),
    )

    return HandGeometry(
        detected=True,
        handedness=handedness_name,
        handedness_score=handedness_score,
        landmarks=landmarks,
        orientation_sign=_orientation_sign(landmarks),
        palm_center=palm_center,
        bbox=(min(xs), min(ys), max(xs), max(ys)),
        error=None,
    )


def _empty_geometry(*, error: str | None) -> HandGeometry:
    return HandGeometry(
        detected=False,
        handedness=None,
        handedness_score=0.0,
        landmarks=(),
        orientation_sign=0.0,
        palm_center=None,
        bbox=None,
        error=error,
    )


def _model_path() -> Path:
    configured = os.getenv("MEDIAPIPE_HAND_LANDMARKER_MODEL")
    return Path(configured).expanduser() if configured else DEFAULT_MODEL_PATH


@lru_cache(maxsize=1)
def _mediapipe_imports() -> tuple[Any, Any, Any]:
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import mediapipe as mp  # type: ignore
    from mediapipe.tasks.python.core import base_options  # type: ignore
    from mediapipe.tasks.python.vision import hand_landmarker  # type: ignore

    try:
        from absl import logging as absl_logging  # type: ignore

        absl_logging.set_verbosity(absl_logging.ERROR)
    except Exception:
        pass

    return mp, hand_landmarker, base_options


def _prepare_mediapipe_image(image: Image.Image) -> Any:
    import numpy as np

    rgb = ImageOps.exif_transpose(image).convert("RGB")
    rgb.thumbnail((MAX_MEDIAPIPE_SIZE, MAX_MEDIAPIPE_SIZE), Image.Resampling.LANCZOS)
    return np.ascontiguousarray(np.array(rgb))


def _best_hand_index(handedness: list[list[Any]]) -> int:
    if not handedness:
        return 0
    scores = [float(items[0].score) if items else 0.0 for items in handedness]
    return max(range(len(scores)), key=lambda index: scores[index])


def _orientation_sign(landmarks: tuple[tuple[float, float, float], ...]) -> float:
    wrist = landmarks[0]
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]
    return (index_mcp[0] - wrist[0]) * (pinky_mcp[1] - wrist[1]) - (
        index_mcp[1] - wrist[1]
    ) * (pinky_mcp[0] - wrist[0])


def _orientation_flipped(source_hand: HandGeometry, result_hand: HandGeometry) -> bool:
    if abs(source_hand.orientation_sign) < 0.00045 or abs(result_hand.orientation_sign) < 0.00045:
        return False
    return source_hand.orientation_sign * result_hand.orientation_sign < 0


def _pose_delta(source_hand: HandGeometry, result_hand: HandGeometry) -> float | None:
    if len(source_hand.landmarks) != 21 or len(result_hand.landmarks) != 21:
        return None

    source_norm = _normalized_landmarks(source_hand.landmarks)
    result_norm = _normalized_landmarks(result_hand.landmarks)
    if not source_norm or not result_norm:
        return None

    distances = [
        ((source_point[0] - result_point[0]) ** 2 + (source_point[1] - result_point[1]) ** 2) ** 0.5
        for source_point, result_point in zip(source_norm, result_norm)
    ]
    return sum(distances) / len(distances)


def _normalized_landmarks(landmarks: tuple[tuple[float, float, float], ...]) -> list[tuple[float, float]]:
    wrist = landmarks[0]
    xs = [point[0] for point in landmarks]
    ys = [point[1] for point in landmarks]
    scale = max(max(xs) - min(xs), max(ys) - min(ys), 0.001)
    return [((point[0] - wrist[0]) / scale, (point[1] - wrist[1]) / scale) for point in landmarks]


def _inner_side_highlight_score(
    source_image: Image.Image | None,
    result_image: Image.Image,
    result_hand: HandGeometry,
) -> float:
    if source_image is None or not result_hand.landmarks or result_hand.palm_center is None:
        return 0.0

    result_gray, source_gray = _aligned_gray_images(result_image, source_image)
    diff = ImageChops.difference(result_gray, source_gray)
    scores: list[float] = []
    width, height = result_gray.size
    palm_center = result_hand.palm_center

    for mcp_index, dip_index, tip_index in ((5, 7, 8), (9, 11, 12), (13, 15, 16), (17, 19, 20)):
        mcp = result_hand.landmarks[mcp_index]
        dip = result_hand.landmarks[dip_index]
        tip = result_hand.landmarks[tip_index]
        axis_x = tip[0] - mcp[0]
        axis_y = tip[1] - mcp[1]
        axis_len = max((axis_x * axis_x + axis_y * axis_y) ** 0.5, 0.001)
        normal_x = -axis_y / axis_len
        normal_y = axis_x / axis_len
        palm_side = (palm_center[0] - tip[0]) * normal_x + (palm_center[1] - tip[1]) * normal_y
        if palm_side < 0:
            normal_x *= -1
            normal_y *= -1

        center_x = (tip[0] * 0.62 + dip[0] * 0.38 + normal_x * 0.018) * width
        center_y = (tip[1] * 0.62 + dip[1] * 0.38 + normal_y * 0.018) * height
        radius = max(8, int(min(width, height) * 0.028))
        box = (
            max(0, int(center_x - radius)),
            max(0, int(center_y - radius)),
            min(width, int(center_x + radius)),
            min(height, int(center_y + radius)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        diff_mean = float(ImageStat.Stat(diff.crop(box)).mean[0])
        scores.append(diff_mean)

    return max(scores) if scores else 0.0


def _aligned_gray_images(result_image: Image.Image, source_image: Image.Image) -> tuple[Image.Image, Image.Image]:
    result = ImageOps.exif_transpose(result_image).convert("RGB")
    source = ImageOps.exif_transpose(source_image).convert("RGB").resize(result.size, Image.Resampling.LANCZOS)
    result.thumbnail((MAX_MEDIAPIPE_SIZE, MAX_MEDIAPIPE_SIZE), Image.Resampling.LANCZOS)
    source = source.resize(result.size, Image.Resampling.LANCZOS)
    return ImageOps.grayscale(result), ImageOps.grayscale(source)


def _describe_palm_orientation(hand: HandGeometry) -> str:
    if abs(hand.orientation_sign) < 0.00045:
        return "手掌平面接近镜头方向"
    return "手掌拓扑方向已记录"
