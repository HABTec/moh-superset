# Docker dev override — loads MoH config from the project root.
#
# Single source of truth: superset_config.py at the repo root (gitignored).
# Copy the template once:
#     cp superset_config.example.py superset_config.py
#
# Falls back to superset_config.example.py when superset_config.py is missing.

import importlib.util
import logging
import os

logger = logging.getLogger(__name__)

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def _load_root_config(filename: str):
    path = os.path.join(_ROOT, filename)
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("_moh_root_superset_config", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cfg = _load_root_config("superset_config.py") or _load_root_config(
    "superset_config.example.py"
)

if _cfg is None:
    raise ImportError(
        "MoH Superset config not found. Run:\n"
        "  cp superset_config.example.py superset_config.py"
    )

logger.info("Loaded MoH config from [%s]", getattr(_cfg, "__file__", "unknown"))

for _name in dir(_cfg):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_cfg, _name)
