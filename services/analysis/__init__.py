from django.conf import settings
from .types import AnalysisProvider
from .mock_provider import MockAnalysisProvider
from .real_provider import RealAnalysisProvider

_real_provider_instance = None

def get_analysis_provider() -> AnalysisProvider:
    provider_name = getattr(settings, 'ANALYSIS_PROVIDER', 'mock').lower()
    if provider_name == 'real':
        global _real_provider_instance
        if _real_provider_instance is None:
            _real_provider_instance = RealAnalysisProvider()
        return _real_provider_instance
    return MockAnalysisProvider()
