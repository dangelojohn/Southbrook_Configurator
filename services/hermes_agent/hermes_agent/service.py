# SPDX-License-Identifier: LGPL-3.0-only
import time


def run_passive_service(config, sleep_fn=time.sleep, max_iterations=None):
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        sleep_fn(config.service_interval_seconds)
        iterations += 1
    return iterations
