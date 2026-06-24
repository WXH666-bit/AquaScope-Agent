"""YOLO-based underwater object detection for AquaScope.

Uses a pretrained YOLO model to detect marine organisms and return
bounding-box annotations.  Designed to work with a DUO-trained model
(holothurian / echinus / scallop / starfish) but also accepts custom
class mappings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class YOLODetector:
    """Thin wrapper around an Ultralytics YOLO model for organism detection.

    Parameters
    ----------
    model_path:
        Path to a ``.pt`` weights file (e.g. YOLOv8n trained on DUO).
    class_names:
        Optional mapping from YOLO integer class-id to a human-readable
        label.  Falls back to the model's built-in names.
    """

    def __init__(
        self,
        model_path: str | Path,
        class_names: dict[int, str] | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        if not self._model_path.exists():
            raise FileNotFoundError(
                f"YOLO model not found: {self._model_path}. "
                "Train or download a model first (e.g. yolo train model=yolov8n.pt ...)."
            )

        from ultralytics import YOLO

        self._model = YOLO(str(self._model_path))
        self.class_names = class_names or self._model.names or {}

    # ------------------------------------------------------------------
    def detect(
        self,
        image_path: str | Path,
        output_dir: str | Path | None = None,
        conf_threshold: float = 0.25,
    ) -> dict[str, Any]:
        """Run detection on a single image.

        Parameters
        ----------
        image_path:
            Path to the input image.
        output_dir:
            Directory where the annotated image will be saved.  When
            *None* the annotated image is **not** written to disk.
        conf_threshold:
            Minimum confidence for a detection to be kept.

        Returns
        -------
        dict with keys:
            **detections** (*list[dict]*):
                ``{"label": str, "confidence": float, "bbox": [x1,y1,x2,y2]}``
            **annotated_path** (*str | None*):
                Path to the saved annotated image, or *None* if
                *output_dir* was not provided.
        """
        results = self._model(str(image_path), conf=conf_threshold, verbose=False)

        detections: list[dict[str, Any]] = []
        annotated_path: str | None = None

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = round(boxes.conf[i].item(), 4)
                xyxy = boxes.xyxy[i].tolist()  # [x1, y1, x2, y2]
                detections.append(
                    {
                        "label": self.class_names.get(cls_id, f"class_{cls_id}"),
                        "confidence": conf,
                        "bbox": [round(v, 1) for v in xyxy],
                    }
                )

        # Save annotated image when requested
        if output_dir is not None and detections:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            stem = Path(image_path).stem
            annotated_path = str(out / f"{stem}_detected.jpg")

            # result.plot() returns a BGR numpy array
            annotated = results[0].plot()
            import cv2

            cv2.imwrite(annotated_path, annotated)

        return {
            "detections": detections,
            "annotated_path": annotated_path,
        }
