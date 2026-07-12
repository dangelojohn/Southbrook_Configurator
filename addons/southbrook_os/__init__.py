import datetime
import os

from . import models
from . import controllers
from . import exports


def _post_init_load_canonical(env):
    addon_dir = os.path.dirname(__file__)
    canonical_dir = os.path.join(addon_dir, "canonical")
    env["southbrook.os.loader"].load_canonical_directory(canonical_dir)
    # Build an initial publication so the public (read-only) endpoint has a
    # snapshot to reference immediately; the daily cron refreshes it thereafter.
    calendar_key = datetime.date.today().strftime("%Y-%m")
    env["southbrook.os.publication"].publish(calendar_key)
