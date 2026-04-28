# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import os

from pathlib import Path
from subprocess import Popen

_IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"


def run(*command: str | Path) -> None:
    cmd_str = " ".join(str(c) for c in command)
    msg = f"Running {cmd_str}"
    if _IS_GITHUB_ACTIONS:
        print(f"::group::{msg}", flush=True)
    else:
        print(msg)

    process = Popen(command)
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
    finally:
        if _IS_GITHUB_ACTIONS:
            print("::endgroup::", flush=True)

    if process.returncode != 0:
        error_msg = f"'{cmd_str}' failed with exit code {process.returncode}"
        raise RuntimeError(error_msg)


def main() -> None:
    root = Path(__file__).parent
    os.chdir(root)
    os.environ.pop("VIRTUAL_ENV", None)

    parser = argparse.ArgumentParser(description="Main build script for blog")
    parser.add_argument("--skip-install", action="store_true", help="Skip package installs")
    parser.add_argument("--fix", action="store_true", help="Fix issues like linting, formatting, etc.")
    parser.add_argument("--lint", action="store_true", help="Run linting")
    parser.add_argument("--build", action="store_true", help="Run build")
    parser.add_argument("--check", action="store_true", help="Run checks like linting, build")
    args = parser.parse_args()

    do_fix = args.fix
    do_lint = args.check or args.lint
    do_build = args.check or args.build

    os.environ["NODE_OPTIONS"] = "--max_old_space_size=10000"
    os.environ["SKIP_SOURCEMAPS"] = "true"

    if not args.skip_install:
        run("npm", "install")
        run("npm", "run", "astro", "sync")

    if do_fix:
        run("npm", "run", "lint:fix")
        run("npm", "run", "fmt")

    if do_lint:
        run("npm", "run", "typecheck")
        run("npm", "run", "lint")
        run("npm", "run", "fmt:check")

    if do_build:
        run("npm", "run", "build")


if __name__ == "__main__":
    main()
