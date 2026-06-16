# SPDX-License-Identifier: LGPL-3.0-only
import argparse

from .client import HermesOdooClient, build_recommendation_payload
from .config import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a draft HERMES recommendation.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--type", default="note", dest="recommendation_type")
    parser.add_argument("--priority", default="normal")
    parser.add_argument("--proposed-action")
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    main()
