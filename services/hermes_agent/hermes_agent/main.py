# SPDX-License-Identifier: LGPL-3.0-only
import argparse
import sys

from .client import HermesOdooClient, build_recommendation_payload
from .config import load_config
from .service import run_passive_service


def _normalize_argv(argv):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in {"check", "recommend", "serve"}:
        return ["recommend"] + args
    return args


def _add_recommendation_args(parser):
    parser.add_argument("--name", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--type", default="note", dest="recommendation_type")
    parser.add_argument("--priority", default="normal")
    parser.add_argument("--proposed-action")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the HERMES sidecar.")
    subparsers = parser.add_subparsers(dest="command")

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Create one draft recommendation in Odoo.",
    )
    _add_recommendation_args(recommend_parser)

    subparsers.add_parser(
        "serve",
        help="Run a passive long-running sidecar process.",
    )
    subparsers.add_parser(
        "check",
        help="Validate sidecar runtime configuration.",
    )

    args = parser.parse_args(_normalize_argv(argv))
    if args.command == "check":
        load_config()
        return 0
    if args.command == "serve":
        config = load_config()
        run_passive_service(config)
        return 0

    config = load_config()
    payload = build_recommendation_payload(
        name=args.name,
        summary=args.summary,
        recommendation_type=args.recommendation_type,
        priority=args.priority,
        proposed_action=args.proposed_action,
        model_provider=config.model_provider,
        model_name=config.model_name,
    )
    result = HermesOdooClient(config).create_recommendation(payload)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
