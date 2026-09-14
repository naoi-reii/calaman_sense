import unittest
import numpy as np
import cv2
import tempfile
import os
import sys

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analysis.real_provider import RealAnalysisProvider

class RealAnalysisProviderFilteringTest(unittest.TestCase):
    def setUp(self):
        # Filtering tests must not load or download model weights.
        self.provider = RealAnalysisProvider.__new__(RealAnalysisProvider)
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_valid_fruit_crop_rejects_white_background(self):
        # Create 100x100 white crop (paper sheet background)
        white_crop = np.ones((100, 100, 3), dtype=np.uint8) * 240
        valid = self.provider._is_valid_fruit_crop(
            crop=white_crop,
            x1=0, y1=0, x2=100, y2=100,
            img_width=100, img_height=100
        )
        self.assertFalse(valid, "White background crop should be rejected")

    def test_is_valid_fruit_crop_rejects_giant_bounding_box(self):
        # Create green crop that takes up 90% of screen area
        green_crop = np.zeros((900, 900, 3), dtype=np.uint8)
        green_crop[:, :] = (30, 180, 50) # Green color in BGR
        valid = self.provider._is_valid_fruit_crop(
            crop=green_crop,
            x1=0, y1=0, x2=900, y2=900,
            img_width=1000, img_height=1000
        )
        self.assertFalse(valid, "Box taking 81% of total screen area should be rejected")

    def test_is_valid_fruit_crop_accepts_small_green_calamansi(self):
        # Create a small 60x60 calamansi fruit crop in 1000x1000 image
        green_fruit_crop = np.zeros((60, 60, 3), dtype=np.uint8)
        green_fruit_crop[:, :] = (30, 160, 50) # Calamansi green in BGR
        valid = self.provider._is_valid_fruit_crop(
            crop=green_fruit_crop,
            x1=100, y1=100, x2=160, y2=160,
            img_width=1000, img_height=1000
        )
        self.assertTrue(valid, "Small green calamansi crop should be accepted")

    def test_is_valid_fruit_crop_accepts_small_yellow_calamansi(self):
        # Create a small 60x60 ripe yellow calamansi fruit crop in 1000x1000 image
        yellow_fruit_crop = np.zeros((60, 60, 3), dtype=np.uint8)
        yellow_fruit_crop[:, :] = (20, 200, 220) # Calamansi yellow in BGR
        valid = self.provider._is_valid_fruit_crop(
            crop=yellow_fruit_crop,
            x1=200, y1=200, x2=260, y2=260,
            img_width=1000, img_height=1000
        )
        self.assertTrue(valid, "Small ripe yellow calamansi crop should be accepted")

if __name__ == '__main__':
    unittest.main()
