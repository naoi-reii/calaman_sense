from django.conf import settings
from .types import AnalysisProvider
from .mock_provider import MockAnalysisProvider
from .real_provider import RealAnalysisProvider

def get_analysis_provider() -> AnalysisProvider:
    provider_name = getattr(settings, 'ANALYSIS_PROVIDER', 'mock').lower()
    if provider_name == 'real':
        return RealAnalysisProvider()
    return MockAnalysisProvider()
