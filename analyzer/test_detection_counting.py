"""Regression tests use synthetic detections, without downloading weights."""
import os
import tempfile
import unittest
from unittest.mock import Mock

import cv2
import numpy as np

from services.analysis.real_provider import RealAnalysisProvider


def detection(coords):
    box = Mock()
    box.cls = [Mock()]
    box.cls[0].cpu.return_value.numpy.return_value = np.array(49)
    box.xyxy = [Mock()]
    box.xyxy[0].cpu.return_value.numpy.return_value = np.array(coords)
    return box


class CountingTests(unittest.TestCase):
    def setUp(self):
        self.provider = RealAnalysisProvider.__new__(RealAnalysisProvider)

    def test_duplicate_views_are_counted_once(self):
        boxes = [np.array(b) for b in [(10, 10, 60, 60), (12, 11, 61, 61)]]
        self.assertEqual(len(self.provider._merge_boxes(boxes)), 1)

    def test_offset_overlapping_fruits_survive(self):
        boxes = [np.array(b) for b in [(10, 10, 60, 60), (28, 10, 78, 60)]]
        self.assertEqual(len(self.provider._merge_boxes(boxes)), 2)

    def test_detail_pass_recovers_fruit_and_repeat_scan_matches(self):
        img = np.full((400, 400, 3), 255, dtype=np.uint8)
        cv2.circle(img, (70, 70), 25, (30, 160, 50), -1)
        cv2.circle(img, (190, 190), 20, (30, 160, 50), -1)

        def predict(*args, **kwargs):
            # Full image misses the second fruit; first detail pass recovers it.
            index = (self.provider.model.call_count - 1) % 19
            boxes = {0: [detection((45, 45, 95, 95))],
                     1: [detection((45, 45, 95, 95)), detection((170, 170, 210, 210))]}
            result = Mock()
            result.boxes = boxes.get(index, [])
            return [result]

        self.provider.model = Mock(side_effect=predict)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'fruit.png')
            cv2.imwrite(path, img)
            first = self.provider.analyze(path)
            second = self.provider.analyze(path)
        self.assertEqual(first.fruit_count_total, 2)
        self.assertEqual(first.fruit_count_total, len(first.mock_annotations))
        self.assertEqual(first, second)
        self.assertEqual(self.provider.model.call_count, 38)

    def test_nested_stem_box_and_cluster_are_not_extra_fruit(self):
        boxes = [np.array(b) for b in [(20, 20, 70, 70), (80, 20, 130, 70),
                                      (20, 0, 70, 70), (10, 10, 140, 80)]]
        self.assertEqual(len(self.provider._merge_boxes(boxes)), 2)

    def test_uncovered_partial_fruit_recovered_but_leaf_rejected(self):
        img = np.full((300, 300, 3), 255, dtype=np.uint8)
        cv2.circle(img, (145, 100), 25, (30, 160, 50), -1)
        cv2.ellipse(img, (95, 45), (40, 8), 0, 0, 360, (30, 160, 50), -1)
        boxes = [np.array([50, 50, 130, 150])]
        regions = self.provider._recover_visible_regions(img, boxes)
        self.assertEqual(len(regions), 1)
        self.assertGreaterEqual(regions[0][0], 130)

    def test_empty_white_image_has_no_recovered_fruit(self):
        img = np.full((300, 300, 3), 255, dtype=np.uint8)
        self.assertEqual(self.provider._recover_visible_regions(img, []), [])
        self.assertEqual(self.provider._recover_visible_regions(img, [np.array([50, 50, 130, 150])]), [])
