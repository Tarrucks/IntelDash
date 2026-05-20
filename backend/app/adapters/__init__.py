from app.adapters.aishub import AISHubAdapter
from app.adapters.barentswatch import BarentsWatchAdapter
from app.adapters.base import SourceAdapter
from app.adapters.exa import ExaAdapter
from app.adapters.fr24 import FR24Adapter
from app.adapters.kaggle import KaggleAdapter
from app.adapters.marinecadastre import MarineCadastreAdapter
from app.adapters.osintframework import OsintFrameworkAdapter
from app.adapters.registry import ADAPTER_CLASSES, all_adapters, get_adapter
from app.adapters.shodan import ShodanAdapter
from app.adapters.wokwi import WokwiAdapter

__all__ = [
    "SourceAdapter",
    "ShodanAdapter",
    "ExaAdapter",
    "AISHubAdapter",
    "BarentsWatchAdapter",
    "MarineCadastreAdapter",
    "FR24Adapter",
    "KaggleAdapter",
    "OsintFrameworkAdapter",
    "WokwiAdapter",
    "ADAPTER_CLASSES",
    "get_adapter",
    "all_adapters",
]
