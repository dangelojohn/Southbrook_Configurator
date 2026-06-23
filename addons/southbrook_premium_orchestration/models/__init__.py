from . import sale_order
from . import project_task
from . import southbrook_mi_engine
from . import mrp_workorder
from . import cut_spec_override
from . import gemini_activator
from . import freecad_activator
from . import project_task_template_spawn
from . import data_quality_report
# mrp_planning_run_cron was removed 2026-06-23 (cold-install bug #2 for
# this addon). Its `class MrpPlanningRun(models.Model): _inherit =
# "mrp.planning.run"` failed registry init in any DB without
# openvalue_mrp_planning_engine — which is the external OpenValue base
# that provides the model. Southbrook's prod doesn't have OpenValue,
# so this code never worked there; it only succeeded silently against
# warm registries that had the old in-memory definition.
# Re-enable when OpenValue is vendored: restore the file from git
# history (commit 70185e7^ for the last working version), add the
# import back, and uncomment the cron in data/ir_cron.xml.
from . import order_analytics_cron
