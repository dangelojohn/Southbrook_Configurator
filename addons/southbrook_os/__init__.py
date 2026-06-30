import os

from . import models
from . import controllers
from . import exports


def _post_init_load_canonical(env):
    addon_dir = os.path.dirname(__file__)
    canonical_dir = os.path.join(addon_dir, "canonical")
    env["southbrook.os.loader"].load_canonical_directory(canonical_dir)
