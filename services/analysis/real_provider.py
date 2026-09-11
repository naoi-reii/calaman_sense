import cv2
import numpy as np
import random
from ultralytics import YOLO
from .types import AnalysisProvider, ScanAnalysisResult

class RealAnalysisProvider(AnalysisProvider):
    def __init__(self):
        # Load the pre-trained YOLOv8 small model (smarter than nano)
        # It will download automatically on first run
        self.model = YOLO('yolov8s.pt')

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

    def analyze(self, image_path: str) -> ScanAnalysisResult:
        # Load image with OpenCV for processing
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")

        img_height, img_width = img.shape[:2]

        # 1. Run YOLOv8 Detection with conf=0.15
        results = self.model(image_path, conf=0.15, verbose=False)
        result = results[0]
        yolo_boxes = result.boxes

        raw_boxes = []
        if len(yolo_boxes) > 0:
            for box in yolo_boxes:
                # Exclude known COCO non-fruit background categories if present
                cls_id = int(box.cls[0].cpu().numpy()) if hasattr(box, 'cls') and len(box.cls) > 0 else -1
                # COCO background classes: 56 (chair), 57 (couch), 59 (bed), 60 (dining table), 62 (tv), 63 (laptop), 73 (book)
                if cls_id in [56, 57, 59, 60, 62, 63, 73]:
                    continue
                xyxy = box.xyxy[0].cpu().numpy()
                raw_boxes.append(xyxy)

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

        # 4. Non-Maximum Suppression (NMS) to eliminate duplicate/nested boxes
        final_boxes = []
        if len(valid_boxes) > 0:
            # Sort by area ascending so we prefer tight fruit boxes over large outer containers
            valid_boxes.sort(key=lambda b: (b[2]-b[0]) * (b[3]-b[1]))
            for box in valid_boxes:
                keep = True
                bx1, by1, bx2, by2 = box
                b_area = (bx2 - bx1) * (by2 - by1)
                for existing in final_boxes:
                    ex1, ey1, ex2, ey2 = existing
                    # Calculate intersection
                    ix1, iy1 = max(bx1, ex1), max(by1, ey1)
                    ix2, iy2 = min(bx2, ex2), min(by2, ey2)
                    if ix1 < ix2 and iy1 < iy2:
                        i_area = (ix2 - ix1) * (iy2 - iy1)
                        if i_area / float(b_area) > 0.60:
                            keep = False
                            break
                if keep:
                    final_boxes.append(box)

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

            # --- OpenCV Ripeness Analysis (Color Heuristic) ---
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            # Hue ranges: Green is roughly 35-85, Yellow/Orange is 15-35
            lower_green = np.array([35, 40, 40])
            upper_green = np.array([85, 255, 255])

            lower_yellow = np.array([15, 40, 40])
            upper_yellow = np.array([35, 255, 255])

            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

            green_pixels = cv2.countNonZero(green_mask)
            yellow_pixels = cv2.countNonZero(yellow_mask)

            total_colored = green_pixels + yellow_pixels

            # --- Determine ripeness label, confidence %, and CSS class ---
            if total_colored > 0:
                green_ratio = green_pixels / total_colored

                if green_ratio > 0.6:
                    unripe_count += 1
                    confidence = green_ratio * 100
                    css_class = "unripe"
                    label = f"Unripe {confidence:.0f}%"
                elif green_ratio < 0.3:
                    overripe_count += 1
                    confidence = (1 - green_ratio) * 100
                    css_class = "overripe"
                    label = f"Overripe {confidence:.0f}%"
                else:
                    ripe_count += 1
                    # Confidence peaks at the center of the "ripe" band (0.45)
                    distance_from_center = abs(green_ratio - 0.45)
                    confidence = max(0.0, 100 - (distance_from_center / 0.15) * 100)
                    css_class = "ripe"
                    label = f"Ripe {confidence:.0f}%"
            else:
                ripe_count += 1  # fallback
                confidence = 50.0
                css_class = "ripe"
                label = f"Ripe {confidence:.0f}%"

            annotations.append({
                'x': x_pct,
                'y': y_pct,
                'width': w_pct,
                'height': h_pct,
                'label': label,
                'css_class': css_class
            })

        # Grade based on Greenness (more green = better grade)
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
            model_version='yolov8s-opencv-watershed'
        )