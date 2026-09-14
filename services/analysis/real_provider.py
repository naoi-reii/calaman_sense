import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from .types import AnalysisProvider, ScanAnalysisResult

class RealAnalysisProvider(AnalysisProvider):
    def __init__(self):
        # Load the pre-trained YOLOv8 small model (smarter than nano)
        # It will download automatically on first run
        self.model = YOLO(str(Path(__file__).resolve().parents[2] / 'yolov8s.pt'))

    @staticmethod
    def _merge_boxes(boxes):
        """Remove repeat views of a fruit while preserving offset, overlapping fruit."""
        kept = []
        for box in sorted(boxes, key=lambda b: ((b[2]-b[0])*(b[3]-b[1]), *b)):
            area = (box[2]-box[0]) * (box[3]-box[1])
            duplicate = False
            for other in kept:
                intersection = max(0, min(box[2], other[2])-max(box[0], other[0])) * max(0, min(box[3], other[3])-max(box[1], other[1]))
                other_area = (other[2]-other[0]) * (other[3]-other[1])
                iou = intersection / max(1, area + other_area - intersection)
                # Containment alone is insufficient: occluded fruits can overlap.
                close_center = all(abs((box[k]+box[k+2])-(other[k]+other[k+2])) / 2 <= 0.2 * min(box[k+2]-box[k], other[k+2]-other[k]) for k in (0, 1))
                containment = intersection / max(1, min(area, other_area))
                if iou >= 0.65 or containment >= 0.92 or (close_center and containment >= 0.85):
                    duplicate = True
                    break
            # A loose cluster box is not an additional fruit. It encloses the
            # centers and most of at least two tighter detections.
            enclosed = sum(
                max(0, min(box[2], b[2])-max(box[0], b[0]))
                * max(0, min(box[3], b[3])-max(box[1], b[1]))
                / max(1, (b[2]-b[0])*(b[3]-b[1])) > 0.8
                for b in kept
            )
            if not duplicate and enclosed < 2:
                kept.append(box)
        return sorted(kept, key=lambda b: (b[1], b[0], b[3], b[2]))

    def _detect_boxes(self, img):
        """Scan full image and overlapping detail views with fixed inference settings."""
        height, width = img.shape[:2]
        views = [(0, 0, width, height)]
        if min(height, width) >= 160:
            for scale in (0.8, 0.5):
                tile_w, tile_h = int(width * scale), int(height * scale)
                views += [(x, y, x+tile_w, y+tile_h)
                          for y in sorted({0, (height-tile_h)//2, height-tile_h})
                          for x in sorted({0, (width-tile_w)//2, width-tile_w})]
        candidates = []
        for left, top, right, bottom in views:
            results = self.model(img[top:bottom, left:right], conf=0.03,
                                 iou=0.7, imgsz=960, device='cpu',
                                 augment=False, agnostic_nms=True, verbose=False)
            for detection in results[0].boxes:
                cls_id = int(detection.cls[0].cpu().numpy())
                # This checkpoint uses COCO labels: only apple/orange candidates.
                if cls_id not in (47, 49):
                    continue
                x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy()
                # Ignore fruit clipped by an internal tile edge; overlapping views
                # provide another opportunity to detect the complete visible fruit.
                margin_x, margin_y = (right-left)*0.05, (bottom-top)*0.05
                if ((left > 0 and x1 <= margin_x) or (top > 0 and y1 <= margin_y)
                        or (right < width and x2 >= right-left-margin_x)
                        or (bottom < height and y2 >= bottom-top-margin_y)):
                    continue
                x1, y1 = max(0, int(x1+left)), max(0, int(y1+top))
                x2, y2 = min(width, int(x2+left)), min(height, int(y2+top))
                if self._is_valid_fruit_crop(img[y1:y2, x1:x2], x1, y1, x2, y2, width, height):
                    candidates.append(np.array([x1, y1, x2, y2]))
        return candidates

    def _recover_visible_regions(self, img, boxes):
        """Recover compact citrus-colored regions beside already detected fruit.

        Only uncovered pixels are considered. Size is relative to detected fruit,
        and shape checks reject thin stems, elongated leaves and diffuse shadows.
        This supplements the generic detector; it does not infer invisible fruit.
        """
        if not boxes:
            return []
        height, width = img.shape[:2]
        reference_area = float(np.median([(b[2]-b[0])*(b[3]-b[1]) for b in boxes]))
        mask = cv2.inRange(cv2.cvtColor(img, cv2.COLOR_BGR2HSV),
                           np.array([10, 40, 35]), np.array([90, 255, 255]))
        covered = np.zeros((height, width), dtype=np.uint8)
        for x1, y1, x2, y2 in boxes:
            covered[y1:y2, x1:x2] = 255
        mask[covered > 0] = 0
        radius = max(2, int(np.sqrt(reference_area) * 0.08))
        nearby = cv2.dilate(covered, np.ones((2*radius+1, 2*radius+1), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        recovered = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not 0.12 * reference_area <= area <= 0.8 * reference_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if not 0.55 <= w / max(1, h) <= 1.8:
                continue
            hull_area = cv2.contourArea(cv2.convexHull(contour))
            perimeter = cv2.arcLength(contour, True)
            if area / max(1, hull_area) < 0.75 or 4*np.pi*area / max(1, perimeter**2) < 0.30:
                continue
            region = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(region, [contour - np.array([[[x, y]]])], -1, 255, -1)
            if not np.any((region > 0) & (nearby[y:y+h, x:x+w] > 0)):
                continue
            if self._is_valid_fruit_crop(img[y:y+h, x:x+w], x, y, x+w, y+h, width, height):
                recovered.append(np.array([x, y, x+w, y+h]))
        return recovered

    def _is_valid_fruit_crop(self, crop, x1, y1, x2, y2, img_width, img_height):
        """
        Validates if a bounding box crop represents a Calamansi fruit rather than
        a sheet of paper, table surface, camera frame, or background shadow.
        """
        w_px = x2 - x1
        h_px = y2 - y1
        if w_px <= 0 or h_px <= 0:
            return False

        box_area = w_px * h_px
        img_area = img_width * img_height

        # Rule 1: Area Filtering - Reject boxes taking > 35% of total image
        if (box_area / img_area) > 0.35:
            return False

        # Rule 2: Frame Span Filtering - Reject boxes covering > 60% of width or height
        if (w_px / img_width) > 0.60 or (h_px / img_height) > 0.60:
            return False

        # Rule 3: Aspect Ratio Filtering - Calamansi fruits are roundish/elliptical
        aspect_ratio = float(w_px) / float(h_px)
        if aspect_ratio > 3.2 or aspect_ratio < 0.31:
            return False

        # Rule 4: Citrus Color & Saturation Validation in HSV
        if crop is None or crop.size == 0:
            return False

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        
        # Calamansi spectrum: Green (unripe), Lime (ripe), Yellow/Orange (overripe)
        # H: 10-90, S: 30-255, V: 35-255
        lower_citrus = np.array([10, 30, 35])
        upper_citrus = np.array([90, 255, 255])
        
        citrus_mask = cv2.inRange(hsv, lower_citrus, upper_citrus)
        citrus_pixels = cv2.countNonZero(citrus_mask)
        total_pixels = w_px * h_px

        citrus_ratio = citrus_pixels / float(total_pixels)
        
        # White paper, gray background, dark borders have S < 30 or H outside citrus range.
        # Require at least 12% of crop pixels to have citrus color saturation.
        if citrus_ratio < 0.12:
            return False

        return True

    @staticmethod
    def ripeness_label(crop):
        """Color-based ripeness score for saved scans."""
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        green = cv2.countNonZero(cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255])))
        yellow = cv2.countNonZero(cv2.inRange(hsv, np.array([15, 40, 40]), np.array([35, 255, 255])))
        if not green + yellow:
            return 'ripe', 'Ripe 50%'
        ratio = green / (green + yellow)
        if ratio > .6:
            return 'unripe', f'Unripe {ratio * 100:.0f}%'
        if ratio < .3:
            return 'overripe', f'Overripe {(1 - ratio) * 100:.0f}%'
        score = max(0.0, 100 - abs(ratio - .45) / .15 * 100)
        return 'ripe', f'Ripe {score:.0f}%'

    def analyze(self, image_path: str) -> ScanAnalysisResult:
        # Load image with OpenCV for processing
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        img_height, img_width = img.shape[:2]

        raw_boxes = self._detect_boxes(img)

        # 2. Fallback to OpenCV Watershed if YOLO found no candidates
        if len(raw_boxes) == 0:
            # Convert to Grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Thresholding (Inverted because background is white, objects are darker)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Noise removal
            kernel = np.ones((3,3), np.uint8)
            opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

            # Sure background area
            sure_bg = cv2.dilate(opening, kernel, iterations=3)

            # Finding sure foreground area using Distance Transform
            dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)

            # The multiplier (0.3) dictates how strictly it separates touching objects
            _, sure_fg = cv2.threshold(dist_transform, 0.3 * dist_transform.max(), 255, 0)
            sure_fg = np.uint8(sure_fg)

            # Finding unknown region
            unknown = cv2.subtract(sure_bg, sure_fg)

            # Marker labelling
            ret, markers = cv2.connectedComponents(sure_fg)

            # Add one to all labels so that sure background is not 0, but 1
            markers = markers + 1

            # Now, mark the region of unknown with zero
            markers[unknown == 255] = 0

            # Apply watershed
            markers = cv2.watershed(img, markers)

            # Extract bounding boxes for each distinct component
            for label in range(2, ret + 1):
                component_mask = np.zeros(gray.shape, dtype=np.uint8)
                component_mask[markers == label] = 255

                contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    c = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(c)

                    # Filter out tiny artifacts (must be at least 20x20 pixels)
                    if w > 20 and h > 20:
                        raw_boxes.append(np.array([x, y, x+w, y+h]))

        # 3. Filter boxes using Fruit Crop Validation
        valid_boxes = []
        for box in raw_boxes:
            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            # Clamp coordinates
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_width, x2), min(img_height, y2)

            crop = img[y1:y2, x1:x2]
            if self._is_valid_fruit_crop(crop, x1, y1, x2, y2, img_width, img_height):
                valid_boxes.append(np.array([x1, y1, x2, y2]))

        final_boxes = self._merge_boxes(valid_boxes)
        final_boxes = self._merge_boxes(final_boxes + self._recover_visible_regions(img, final_boxes))

        total_fruits = len(final_boxes)
        annotations = []

        # Stats tracking
        unripe_count = 0
        ripe_count = 0
        overripe_count = 0

        for box_xyxy in final_boxes:
            # Unpack the box
            x1, y1, x2, y2 = box_xyxy

            # Convert to percentages for the UI (cast to float to fix JSON serialization)
            w_px = x2 - x1
            h_px = y2 - y1
            x_pct = float((x1 / img_width) * 100)
            y_pct = float((y1 / img_height) * 100)
            w_pct = float((w_px / img_width) * 100)
            h_pct = float((h_px / img_height) * 100)

            # Crop the fruit for OpenCV analysis
            crop = img[int(y1):int(y2), int(x1):int(x2)]

            if crop.size == 0:
                continue

            css_class, label = self.ripeness_label(crop)
            if css_class == 'unripe':
                unripe_count += 1
            elif css_class == 'overripe':
                overripe_count += 1
            else:
                ripe_count += 1

            annotations.append({
                'x': x_pct,
                'y': y_pct,
                'width': w_pct,
                'height': h_pct,
                'label': label,
                'css_class': css_class
            })

        green_ratio = unripe_count / total_fruits if total_fruits > 0 else 0
        if green_ratio >= 0.75:
            grade = 'Best Quality'
        elif green_ratio >= 0.50:
            grade = 'Good Quality'
        else:
            grade = 'Average'

        def safe_pct(count):
            return round((count / total_fruits) * 100, 2) if total_fruits > 0 else 0.0

        return ScanAnalysisResult(
            quality_grade=grade,
            fruit_count_total=total_fruits,
            fruit_count_good=0,
            fruit_count_defective=0,
            size_small_pct=25.0,
            size_medium_pct=50.0,
            size_large_pct=20.0,
            size_xl_pct=5.0,

            ripeness_unripe_pct=safe_pct(unripe_count),
            ripeness_ripe_pct=safe_pct(ripe_count),
            ripeness_overripe_pct=safe_pct(overripe_count),

            defect_blemished_pct=0.0,
            defect_mold_pct=0.0,
            defect_cracked_pct=0.0,
            defect_insect_pct=0.0,
            defect_bruised_pct=0.0,
            defect_foreign_matter_pct=0.0,

            mock_annotations=annotations,
            model_version='yolov8s-visible-regions-v3'
        )
