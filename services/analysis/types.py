from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ScanAnalysisResult:
    quality_grade: str
    fruit_count_total: int
    fruit_count_good: int
    fruit_count_defective: int
    
    size_small_pct: float
    size_medium_pct: float
    size_large_pct: float
    size_xl_pct: float
    
    ripeness_unripe_pct: float
    ripeness_ripe_pct: float
    ripeness_overripe_pct: float
    
    defect_blemished_pct: float
    defect_mold_pct: float
    defect_cracked_pct: float
    defect_insect_pct: float
    defect_bruised_pct: float
    defect_foreign_matter_pct: float
    
    mock_annotations: List[Dict[str, Any]]
    model_version: str

class AnalysisProvider(ABC):
    @abstractmethod
    def analyze(self, image_path: str) -> ScanAnalysisResult:
        pass
