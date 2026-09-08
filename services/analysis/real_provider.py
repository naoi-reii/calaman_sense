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

    def analyze(self, image_path: str) -> ScanAnalysisResult:
        # Load image with OpenCV for processing
        img = cv2.imread(image_path)
        img_height, img_width = img.shape[:2]

        # 1. Run YOLOv8 Detection
        # We use a very low confidence threshold since dark green calamansi don't perfectly match COCO classes
        results = self.model(image_path, conf=0.05, verbose=False)

        # There's only one image, so we take the first result
        result = results[0]
        yolo_boxes = result.boxes

        # We will store the boxes here
        xyxy_boxes = []

        if len(yolo_boxes) > 0:
            for box in yolo_boxes:
                xyxy_boxes.append(box.xyxy[0].cpu().numpy())
        else:
            # YOLO FAILED.
            # Fallback to OpenCV Watershed Algorithm.
            # This is the gold-standard algorithm for separating and counting touching objects!

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
                        xyxy_boxes.append(np.array([x, y, x+w, y+h]))

        total_fruits = len(xyxy_boxes)
        annotations = []

        # Stats tracking
        unripe_count = 0
        ripe_count = 0
        overripe_count = 0

        for box_xyxy in xyxy_boxes:
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