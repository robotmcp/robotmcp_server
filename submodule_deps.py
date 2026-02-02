"""Auto-discover and install dependencies from git submodules.

This module scans .gitmodules for submodules with pyproject.toml files
and ensures their dependencies are installed at server startup.
"""

import configparser
import subprocess
import sys
from pathlib import Path
from importlib.metadata import distributions


def init_submodule(root: Path, submodule_path: str, verbose: bool = True) -> bool:
    """Initialize a git submodule if not already initialized.

    Args:
        root: Root directory of the git repository
        submodule_path: Relative path to the submodule
        verbose: Print status messages

    Returns:
        True if submodule is initialized (or was already), False on failure.
    """
    full_path = root / submodule_path

    # Check if already initialized (has .git file/folder)
    git_marker = full_path / ".git"
    if git_marker.exists():
        return True

    # Check if we're in a git repo
    git_dir = root / ".git"
    if not git_dir.exists():
        if verbose:
            print("  [SKIP] Not a git repository, cannot init submodule")
        return False

    if verbose:
        print(f"  [INIT] Initializing submodule {submodule_path}...")

    try:
        result = subprocess.run(
            ["git", "submodule", "update", "--init", submodule_path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            if verbose:
                print(f"  [OK] Submodule {submodule_path} initialized")
            return True
        else:
            if verbose:
                print(
                    f"  [ERROR] Failed to init {submodule_path}: {result.stderr.strip()}"
                )
            return False
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"  [ERROR] Timeout initializing {submodule_path}")
        return False
    except FileNotFoundError:
        if verbose:
            print("  [ERROR] git not found, cannot init submodule")
        return False
    except Exception as e:
        if verbose:
            print(f"  [ERROR] Failed to init {submodule_path}: {e}")
        return False


def parse_gitmodules(root: Path) -> list[dict]:
    """Parse .gitmodules file to find submodule paths and names.

    Returns:
        List of dicts with 'name' and 'path' keys.
    """
    gitmodules_path = root / ".gitmodules"
    if not gitmodules_path.exists():
        return []

    config = configparser.ConfigParser()
    config.read(gitmodules_path)

    submodules = []
    for section in config.sections():
        # Sections are like: submodule "ros-mcp-server"
        if section.startswith('submodule "') and section.endswith('"'):
            name = section[len('submodule "') : -1]
            path = config.get(section, "path", fallback=None)
            if path:
                submodules.append(
                    {
                        "name": name,
                        "path": path,
                    }
                )

    return submodules


def get_package_name_from_pyproject(pyproject_path: Path) -> str | None:
    """Extract package name from pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # Python < 3.11 fallback

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("name")
    except Exception:
        return None


def is_package_installed(package_name: str) -> bool:
    """Check if a package is installed."""
    installed = {dist.metadata["Name"].lower() for dist in distributions()}
    return (
        package_name.lower().replace("_", "-") in installed
        or package_name.lower().replace("-", "_") in installed
    )


def install_submodule(submodule_path: Path, verbose: bool = True) -> bool:
    """Install a submodule as an editable package.

    Returns:
        True if installation succeeded, False otherwise.
    """
    # Try different pip invocation methods
    pip_commands = [
        [sys.executable, "-m", "pip", "install", "-e", str(submodule_path)],
        ["pip", "install", "-e", str(submodule_path)],
        ["pip3", "install", "-e", str(submodule_path)],
    ]

    for cmd in pip_commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        except Exception:
            continue

    if verbose:
        print(f"  [ERROR] Could not install {submodule_path.name} - pip not available")
    return False


def discover_and_install_submodules(
    root: Path | None = None, verbose: bool = True
) -> dict:
    """Discover git submodules with pyproject.toml and install missing ones.

    Args:
        root: Root directory to scan (defaults to current working directory)
        verbose: Print status messages

    Returns:
        Dict with 'found', 'initialized', 'installed', 'failed', 'already_installed' lists.
    """
    if root is None:
        root = Path(__file__).parent

    result = {
        "found": [],
        "initialized": [],
        "installed": [],
        "failed": [],
        "already_installed": [],
    }

    # Parse .gitmodules
    submodules = parse_gitmodules(root)

    if not submodules:
        return result

    if verbose:
        print("\nDiscovering submodule dependencies...")

    for submodule in submodules:
        submodule_path = root / submodule["path"]
        pyproject_path = submodule_path / "pyproject.toml"

        # Check if submodule needs initialization
        # (directory missing, empty, or no .git marker)
        git_marker = submodule_path / ".git"
        was_initialized = git_marker.exists()
        needs_init = (
            not submodule_path.exists()
            or not was_initialized
            or not pyproject_path.exists()
        )

        if needs_init:
            # Try to initialize the submodule
            if not init_submodule(root, submodule["path"], verbose):
                if verbose and not submodule_path.exists():
                    print(
                        f"  [SKIP] {submodule['name']}: could not initialize submodule"
                    )
                continue
            # Track that we initialized this submodule
            if not was_initialized:
                result["initialized"].append(submodule["name"])

        # Re-check paths after potential initialization
        if not submodule_path.exists():
            if verbose:
                print(
                    f"  [SKIP] {submodule['name']}: directory not found after init attempt"
                )
            continue

        # Check if it has pyproject.toml
        if not pyproject_path.exists():
            if verbose:
                print(f"  [SKIP] {submodule['name']}: no pyproject.toml found")
            continue

        result["found"].append(submodule["name"])

        # Get package name from pyproject.toml
        package_name = get_package_name_from_pyproject(pyproject_path)
        if not package_name:
            if verbose:
                print(f"  [SKIP] {submodule['name']}: could not read package name")
            continue

        # Check if already installed
        if is_package_installed(package_name):
            result["already_installed"].append(submodule["name"])
            if verbose:
                print(f"  [OK] {submodule['name']} ({package_name}): already installed")
            continue

        # Install the submodule
        if verbose:
            print(f"  [INSTALLING] {submodule['name']} ({package_name})...")
            print(
                "    WARNING: This will run 'pip install -e' which executes setup code."
            )

        if install_submodule(submodule_path, verbose):
            result["installed"].append(submodule["name"])
            if verbose:
                print(f"  [OK] {submodule['name']}: installed successfully")
        else:
            result["failed"].append(submodule["name"])
            if verbose:
                print(f"  [FAILED] {submodule['name']}: installation failed")

    if verbose and (result["installed"] or result["failed"]):
        print()  # Extra newline after installation

    return result


def ensure_submodule_deps(root: Path | None = None) -> bool:
    """Ensure all submodule dependencies are installed.

    This is the main entry point to call from cli.py.

    Returns:
        True if all dependencies are satisfied, False if any failed.
    """
    result = discover_and_install_submodules(root, verbose=True)

    # Return False if any installations failed
    return len(result["failed"]) == 0


if __name__ == "__main__":
    # Allow running standalone for testing
    success = ensure_submodule_deps()
    sys.exit(0 if success else 1)
