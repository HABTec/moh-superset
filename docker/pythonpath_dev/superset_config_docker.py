# Docker dev override — keep this file thin. All MoH branding/theming/feature
# flag config lives in superset.moh_branding so it works identically when this
# project is deployed natively on Ubuntu (no Docker), where you'd set
# SUPERSET_CONFIG_PATH to a tiny superset_config.py that also does:
#
#     from superset.moh_branding import *
#
# Edit the source of truth:  superset/moh_branding.py

from superset.moh_branding import *  # noqa: F401,F403
