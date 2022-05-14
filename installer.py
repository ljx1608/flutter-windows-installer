import argparse
import logging
import os
import re
import subprocess
import sys
from turtle import update
import urllib.request
from shutil import which

import requests
from tqdm import tqdm


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    f = "%(levelname)s: %(message)s"

    FORMATS = {
        logging.DEBUG: grey + f + reset,
        logging.INFO: grey + f + reset,
        logging.WARNING: yellow + f + reset,
        logging.ERROR: red + f + reset,
        logging.CRITICAL: bold_red + f + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class TqdmUpTo(tqdm):
    """Alternative Class-based version of the above.
    Provides `update_to(n)` which uses `tqdm.update(delta_n)`.
    Inspired by [twine#242](https://github.com/pypa/twine/pull/242),
    [here](https://github.com/pypa/twine/commit/42e55e06).
    """

    def update_to(self, b=1, bsize=1, tsize=None):
        """
        b  : int, optional
            Number of blocks transferred so far [default: 1].
        bsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        tsize  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            self.total = tsize
        return self.update(b * bsize - self.n)  # also sets self.n = b * bsize


def update_path():
    os.environ["PATH"] = subprocess.run(
        [
            "pwsh",
            "-c",
            'echo ([System.Environment]::GetEnvironmentVariable("Path","Machine") + ";"'
            ' + [System.Environment]::GetEnvironmentVariable("Path","User"))',
        ],
        capture_output=True,
    ).stdout.decode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A simple Windows installer for Flutter development tools"
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        dest="loglevel",
        help="verbosity level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )

    # TODO: Add option to install to a different path

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.loglevel))
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(CustomFormatter())
    logger = logging.getLogger("logger")
    logger.propagate = False
    logger.addHandler(ch)

    logger.info("Checking for Git...")

    git_path = "git"
    update_path()
    if which("git", path=os.environ["PATH"]):
        git_path = which("git", path=os.environ["PATH"])  # type: ignore
        logger.info("Git found")
    else:
        logger.info("Attempting to install Git with winget...")
        git_winget = subprocess.run(
            ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"]
        )
        update_path()
        if git_winget == 0 and which("git", path=os.environ["PATH"]):
            git_path = which("git", path=os.environ["PATH"])  # type: ignore
            logger.info("Git successfully installed with winget")
        else:
            logger.warning(
                "Failed to install Git with winget (perhaps winget not installed?),"
                " trying manual download"
            )
            git_release = requests.get(
                "https://github.com/git-for-windows/git/releases/latest"
            )
            git_install_re = re.search(
                r"(/git-for-windows/git/releases/download/(\S*)64-bit\.exe)",
                git_release.text,
            )
            if git_install_re is not None:
                git_installer_url = f"https://github.com{git_install_re.group()}"
                git_installer_name = git_installer_url.split("/")[-1]
                with TqdmUpTo(
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    miniters=1,
                    desc=git_installer_name,
                ) as t:
                    urllib.request.urlretrieve(
                        git_installer_url,
                        git_installer_name,
                        reporthook=t.update_to,
                    )
                    t.total = t.n
                git_manual = subprocess.run([git_installer_name])
                update_path()
                if git_manual == 0 and which("git", path=os.environ["PATH"]):
                    git_path = which("git", path=os.environ["PATH"])  # type: ignore
                    logger.info("Git successfully installed")
                else:
                    logger.error(
                        "Failed to install Git, install manually from"
                        " https://git-scm.com/download/win and try running again"
                    )
                    sys.exit(1)
            else:
                logger.error(
                    "Failed to install Git, install manually from"
                    " https://git-scm.com/download/win and try running again"
                )
                sys.exit(1)

    flutter_path = "flutter"
    update_path()
    if which("flutter", path=os.environ["PATH"]):
        flutter_path = which("flutter", path=os.environ["PATH"])  # type: ignore
        logger.info("Flutter SDK is already installed, skipping...")
    else:
        logger.info("Attempting to clone Flutter in C:\\src...")
        subprocess.run(
            [
                git_path,
                "clone",
                "https://github.com/flutter/flutter.git",
                "-b",
                "stable",
                "C:\\src",
            ]
        )
        logger.info("Cloned Flutter to C:\\src\\flutter")
        logger.info("Attempting to update PATH...")
        subprocess.run(
            [
                "pwsh",
                "-c",
                '[Environment]::SetEnvironmentVariable("Path",'
                ' [Environment]::GetEnvironmentVariable("Path",'
                ' [EnvironmentVariableTarget]::Machine) + ";C:\\src\\flutter\\bin",'
                " [System.EnvironmentVariableTarget]::Machine)",
            ]
        )
        logger.info("Updated PATH")
        update_path()
        if which("flutter", path=os.environ["PATH"]):
            flutter_path = which("flutter", path=os.environ["PATH"])  # type: ignore
            logger.info("Flutter SDK successfully installed")

    # TODO: Add installation of Android SDK and related tools

    input("Press enter to exit...")
