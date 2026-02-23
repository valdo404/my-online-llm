"""Entry point for the AI Treasure Hunt game.

Usage:
    python -m treasure_hunt                          # Default: openai:gpt-4o, 24h deadline
    python -m treasure_hunt --model openai:gpt-4o-mini --deadline 300
    python -m treasure_hunt --model anthropic:claude-sonnet-4-20250514

Environment variables:
    OPENAI_API_KEY       — for OpenAI models
    ANTHROPIC_API_KEY    — for Anthropic models
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .orchestrator import Orchestrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Treasure Hunt — Two AIs must cooperate to save their kittens 🐱",
    )
    parser.add_argument(
        "--model",
        default="openai:gpt-4o",
        help="Pydantic AI model identifier (default: openai:gpt-4o)",
    )
    parser.add_argument(
        "--deadline",
        type=float,
        default=86400,
        help="Deadline in seconds before random VM kill (default: 86400 = 24h)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="Max turns per agent before forced stop (default: 50)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    orchestrator = Orchestrator(
        model=args.model,
        deadline_seconds=args.deadline,
        max_turns_per_agent=args.max_turns,
    )

    try:
        result = asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        print("\n⚡ Game interrupted by user.")
        sys.exit(1)

    # Exit code: 0 if both cats saved, 1 otherwise
    sys.exit(0 if result.get("winner") == "both" else 1)


if __name__ == "__main__":
    main()
