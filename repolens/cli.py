"""Argparse entry point for RepoLens CLI."""

from __future__ import annotations

import argparse
import logging
import sys

from repolens import __version__
from repolens.config import Config
from repolens.exceptions import ConfigurationError, InvalidURLError, RepoLensError
from repolens.github.url_parser import parse_github_url


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repolens",
        description="AI-powered GitHub repository intelligence tool",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze a public GitHub repository and produce a report",
    )
    analyze.add_argument(
        "repository_url",
        help="Public GitHub repository URL (https://github.com/owner/repo)",
    )
    analyze.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Output file path (default: {repo}_report.md)",
    )
    analyze.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )
    analyze.add_argument(
        "--interview",
        action="store_true",
        help="Add interview questions section to the report",
    )
    analyze.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip LLM analysis; produce deterministic-only report",
    )
    analyze.add_argument(
        "--max-files",
        type=int,
        metavar="N",
        help="Override MAX_FILES_ANALYZED",
    )
    analyze.add_argument(
        "--max-file-size",
        type=int,
        metavar="N",
        help="Override MAX_FILE_SIZE_BYTES (bytes)",
    )
    analyze.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging to stderr",
    )

    return parser


def _configure_logging(verbose: bool, config: Config) -> None:
    level = logging.DEBUG if verbose else getattr(logging, config.log_level)
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def _run_analyze(args: argparse.Namespace) -> int:
    """Run the analyze subcommand. Pipeline wired in later phases."""
    try:
        config = Config.from_env(no_ai=args.no_ai)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc.message}", file=sys.stderr)
        return exc.exit_code

    _configure_logging(args.verbose, config)

    # CLI overrides applied after config load
    if args.max_files is not None:
        if args.max_files < 1:
            print("Configuration error: --max-files must be >= 1", file=sys.stderr)
            return 1
        object.__setattr__(config, "max_files_analyzed", args.max_files)
    if args.max_file_size is not None:
        if args.max_file_size < 1:
            print("Configuration error: --max-file-size must be >= 1", file=sys.stderr)
            return 1
        object.__setattr__(config, "max_file_size_bytes", args.max_file_size)

    try:
        parsed = parse_github_url(args.repository_url)
    except InvalidURLError as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code

    logging.info("RepoLens analyze — analysis pipeline starts in Phase 3+")
    logging.info("Parsed repository: %s/%s (ref=%s)", parsed.owner, parsed.repo, parsed.ref)
    logging.info("Options: no_ai=%s, interview=%s, format=%s", args.no_ai, args.interview, args.format)
    print(
        f"Validated {parsed.owner}/{parsed.repo}. "
        "Full analysis pipeline will be available after Phase 3+.",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "analyze":
            return _run_analyze(args)
        parser.print_help()
        return 0
    except RepoLensError as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
