import random
from .types import AnalysisProvider, ScanAnalysisResult

# TODO(v2): This is a temporary mock. Implement real_provider.py against the same AnalysisProvider interface, then flip ANALYSIS_PROVIDER=real. Do not edit call sites.

class MockAnalysisProvider(AnalysisProvider):
    def analyze(self, image_path: str) -> ScanAnalysisResult:
        total = random.randint(10, 50)
        defective = random.randint(0, total)
        good = total - defective
        
        # Calculate grade based on defective ratio
        ratio = defective / total if total > 0 else 0
        if ratio < 0.1:
            grade = 'Best Quality'
        elif ratio < 0.25:
            grade = 'Good Quality'
        else:
            grade = 'Average'

        # Generate some mock bounding boxes
        num_boxes = random.randint(2, 6)
        annotations = []
        for _ in range(num_boxes):
            annotations.append({
                'x': random.uniform(10, 80),
                'y': random.uniform(10, 80),
                'width': random.uniform(5, 20),
                'height': random.uniform(5, 20),
                'label': f"Mock {random.randint(80, 99)}%",
                'css_class': 'ripe' if random.random() > 0.5 else 'unripe'
            })

        def _random_distribution(num_buckets: int):
            vals = [random.random() for _ in range(num_buckets)]
            s = sum(vals)
            return [round((v / s) * 100, 2) for v in vals]
            
        sizes = _random_distribution(4)
        ripeness = _random_distribution(3)
        defects = _random_distribution(6)

        return ScanAnalysisResult(
            grade_letter=grade,
            fruit_count_total=total,
            fruit_count_good=good,
            fruit_count_defective=defective,
            size_small_pct=sizes[0],
            size_medium_pct=sizes[1],
            size_large_pct=sizes[2],
            size_xl_pct=sizes[3],
            ripeness_unripe_pct=ripeness[0],
            ripeness_ripe_pct=ripeness[1],
            ripeness_overripe_pct=ripeness[2],
            defect_blemished_pct=defects[0],
            defect_mold_pct=defects[1],
            defect_cracked_pct=defects[2],
            defect_insect_pct=defects[3],
            defect_bruised_pct=defects[4],
            defect_foreign_matter_pct=defects[5],
            mock_annotations=annotations,
            model_version='mock-v0'
        )
