"""Argparse entry point for RepoLens CLI."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from repolens import __version__
from repolens.config import Config
from repolens.exceptions import ConfigurationError, InvalidURLError, RepoLensError
from repolens.github.url_parser import parse_github_url
from repolens.pipeline import run_analysis


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
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def _apply_cli_overrides(args: argparse.Namespace, config: Config) -> int | None:
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
    return None


def _default_output_path(repo: str, output_format: str) -> Path:
    suffix = "json" if output_format == "json" else "md"
    return Path(f"{repo}_report.{suffix}")


def _run_analyze(args: argparse.Namespace) -> int:
    try:
        config = Config.from_env(no_ai=args.no_ai)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc.message}", file=sys.stderr)
        return exc.exit_code

    _configure_logging(args.verbose, config)

    override_error = _apply_cli_overrides(args, config)
    if override_error is not None:
        return override_error

    try:
        parsed = parse_github_url(args.repository_url)
    except InvalidURLError as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code

    if not args.no_ai:
        try:
            config.require_llm_api_key()
        except RepoLensError as exc:
            print(exc.message, file=sys.stderr)
            return exc.exit_code

    result = run_analysis(
        args.repository_url,
        config=config,
        output_format=args.format,
        include_interview=args.interview,
        no_ai=args.no_ai,
    )

    if args.output == "-":
        print(result.content)
        return 0

    output_path = Path(args.output) if args.output else _default_output_path(parsed.repo, args.format)
    output_path.write_text(result.content, encoding="utf-8")
    print(f"Report written to {output_path}", file=sys.stderr)
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