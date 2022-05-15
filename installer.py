import argparse
import logging
import os
import re
import subprocess
import sys
import urllib.request
import winreg
import zipfile
from pathlib import Path
from shutil import rmtree, which

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


def append_to_path(path, env="user"):
    if env == "machine":
        m_env = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
        )
        path_update = subprocess.run(
            [
                "pwsh",
                "-c",
                '[Environment]::SetEnvironmentVariable("Path",'
                f' "{winreg.QueryValueEx(m_env, "Path")[0]};{path}",'
                " [System.EnvironmentVariableTarget]::Machine)",
            ]
        )
        m_env.Close()
        return path_update
    elif env == "user":
        u_env = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        path_update = subprocess.run(
            [
                "pwsh",
                "-c",
                '[Environment]::SetEnvironmentVariable("Path",'
                f' "{winreg.QueryValueEx(u_env, "Path")[0]};{path}",'
                " [System.EnvironmentVariableTarget]::User)",
            ]
        )
        u_env.Close()
        return path_update


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
        if git_winget.returncode == 0 and which("git", path=os.environ["PATH"]):
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
            git_installer_re = re.search(
                r"(/git-for-windows/git/releases/download/(\S*)64-bit\.exe)",
                git_release.text,
            )
            if git_installer_re is not None:
                git_installer_url = f"https://github.com{git_installer_re.group()}"
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
                if git_manual.returncode == 0 and which("git", path=os.environ["PATH"]):
                    git_path = which("git", path=os.environ["PATH"])  # type: ignore
                    logger.info("Git successfully installed")
                    logger.info("Cleaning up Git installer...")
                    os.remove(git_installer_name)
                else:
                    logger.error(
                        "Failed to install Git, install manually from"
                        " https://git-scm.com/download/win and try running again"
                    )
                    input("Press enter to exit...")
                    sys.exit(1)

            else:
                logger.error(
                    "Failed to install Git, install manually from"
                    " https://git-scm.com/download/win and try running again"
                )
                input("Press enter to exit...")
                sys.exit(1)

    logger.info("Checking for Flutter...")

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
        path_update = append_to_path("C:\\src\\flutter\\bin", "machine")
        if path_update.returncode == 0:
            logger.info("Updated PATH")
        else:
            logger.warning(
                "Failed to update PATH, may be caused by permission issues, please"
                " update PATH manually"
            )
        update_path()
        if which("flutter", path=os.environ["PATH"]):
            flutter_path = which("flutter", path=os.environ["PATH"])  # type: ignore
            logger.info("Flutter SDK successfully installed")
        else:
            logger.error(
                "Failed to install Flutter SDK, please install manually:"
                " https://docs.flutter.dev/get-started/install/windows"
            )
            input("Press enter to exit...")
            sys.exit(1)

    if (
        input(
            "Do you want to install Android SDK, Android SDK Command-line Tools, and"
            " Android SDK Build-Tools (only install if you do not already have it"
            " installed; if unsure, do not install and opt for manual installation"
            " instead)? [y/N] "
        ).lower()
        == "y"
    ):
        logger.info("Attempting to install Android toolchain..")
        logger.info("Downloading Android command line tools...")
        studio_page = requests.get("https://developer.android.com/studio")
        cmdlinetools_installer_re = re.search(
            r"(commandlinetools-win-(\S*)_latest.zip)",
            studio_page.text,
        )
        if cmdlinetools_installer_re is not None:
            cmdlinetools_installer_url = f"https://dl.google.com/android/repository/{cmdlinetools_installer_re.group()}"
            cmdlinetools_installer_name = cmdlinetools_installer_url.split("/")[-1]
            with TqdmUpTo(
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
                desc=cmdlinetools_installer_name,
            ) as t:
                urllib.request.urlretrieve(
                    cmdlinetools_installer_url,
                    cmdlinetools_installer_name,
                    reporthook=t.update_to,
                )
                t.total = t.n

            sdk_dir = Path(os.path.expandvars("%LOCALAPPDATA%\\Android\\Sdk"))
            logger.info(
                "Downloaded Android command line tools, attempting to unzip to"
                f" {sdk_dir}"
            )
            logger.debug(f"Creating {sdk_dir} if not exists")
            sdk_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Unzipping {cmdlinetools_installer_name} to {sdk_dir}")
            if (sdk_dir / "cmdline-tools").exists():
                logger.warning(
                    f"{sdk_dir / 'cmdline-tools'} already exists, overwrite? [y/N]"
                )
                if input().lower() == "y":
                    rmtree(sdk_dir / "cmdline-tools")
                    (sdk_dir / "cmdline-tools").mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(cmdlinetools_installer_name) as z:
                        z.extractall(sdk_dir / "cmdline-tools")
                    (sdk_dir / "cmdline-tools" / "cmdline-tools").rename(
                        sdk_dir / "cmdline-tools" / "latest"
                    )
                else:
                    logger.info("Skipping Android command line tools installation")

            logger.info("Cleaning up Android command line tools installer...")
            os.remove(cmdlinetools_installer_name)

            logger.info("Attempting to update PATH...")
            path_update = append_to_path(
                "%LocalAppData%\\Android\\Sdk\\cmdline-tools\\latest\\bin", "user"
            )
            if path_update.returncode == 0:
                logger.info("Updated PATH")
            else:
                logger.warning(
                    "Failed to update PATH, may be caused by permission issues, please"
                    " update PATH manually"
                )
            update_path()
            if which("sdkmanager.bat", path=os.environ["PATH"]):
                logger.info("Android command line tools successfully installed")
            else:
                logger.error(
                    "Failed to install Android command line tools, please continue"
                    " install manually:"
                    " https://docs.flutter.dev/get-started/install/windows#android-setup"
                )
                input("Press enter to exit...")
                sys.exit(1)

            logger.info(
                "Attempting to install Android platform-tools, platforms;android-32,"
                " build-tools;32.0.0, emulator, Google USB Driver..."
            )
            sdkmanager_install = subprocess.run(
                [
                    f"{sdk_dir / 'cmdline-tools' / 'latest' / 'bin' / 'sdkmanager.bat'}",
                    "--install",
                    "platform-tools",
                    "platforms;android-32",
                    "build-tools;32.0.0",
                    "emulator",
                    "extras;google;usb_driver",
                ]
            )
            if sdkmanager_install.returncode == 0:
                logger.info(
                    "Android platform-tools, platforms;android-32, build-tools;32.0.0,"
                    " emulator, Google USB Driver successfully installed"
                )
                logger.info("Attempting to update PATH...")
                path_update = append_to_path(
                    "%LocalAppData%\\Android\\Sdk\\platform-tools", "user"
                )
                if path_update.returncode == 0:
                    logger.info("Updated PATH")
                else:
                    logger.warning(
                        "Failed to update PATH, may be caused by permission issues,"
                        " please update PATH manually"
                    )
                update_path()
            else:
                logger.error(
                    "Failed to install Android command line tools, please continue"
                    " install manually:"
                    " https://docs.flutter.dev/get-started/install/windows#android-setup"
                )
                input("Press enter to exit...")
                sys.exit(1)
            sdkmanager_update = subprocess.run(
                [
                    f"{sdk_dir / 'cmdline-tools' / 'latest' / 'bin' / 'sdkmanager.bat'}",
                    "--update",
                ]
            )
            if sdkmanager_update.returncode == 0:
                logger.info("Android toolchain successfully updated")

        else:
            logger.error(
                "Failed to install Android command line tools, please continue"
                " install manually:"
                " https://docs.flutter.dev/get-started/install/windows#android-setup"
            )
            input("Press enter to exit...")
            sys.exit(1)

    else:
        logger.info("Skipping Android toolchain installation")

    android_licenses = subprocess.run([flutter_path, "doctor", "--android-licenses"])
    if android_licenses.returncode == 0:
        logger.info("Android licenses successfully accepted")
    else:
        logger.error(
            "Failed to accept Android licenses (may need Java installation), please"
            " continue manually:"
            " https://docs.flutter.dev/get-started/install/windows#agree-to-android-licenses"
        )

    logger.info("Installation completed, running flutter doctor...")
    subprocess.run([flutter_path, "doctor"])

    input("Press enter to exit...")
