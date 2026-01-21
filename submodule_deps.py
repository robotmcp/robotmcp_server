"""Auto-discover and install dependencies from git submodules.

This module scans .gitmodules for submodules with pyproject.toml files
and ensures their dependencies are installed at server startup.
"""
import configparser
import subprocess
import sys
from pathlib import Path
from importlib.metadata import distributions


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
            name = section[len('submodule "'):-1]
            path = config.get(section, 'path', fallback=None)
            if path:
                submodules.append({
                    'name': name,
                    'path': path,
                })

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
    installed = {dist.metadata['Name'].lower() for dist in distributions()}
    return package_name.lower().replace('_', '-') in installed or \
           package_name.lower().replace('-', '_') in installed


def install_submodule(submodule_path: Path, verbose: bool = True) -> bool:
    """Install a submodule as an editable package.

    Returns:
        True if installation succeeded, False otherwise.
    """
    try:
        cmd = [sys.executable, "-m", "pip", "install", "-e", str(submodule_path), "-q"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"  [TIMEOUT] Installation of {submodule_path.name} timed out")
        return False
    except Exception as e:
        if verbose:
            print(f"  [ERROR] Failed to install {submodule_path.name}: {e}")
        return False


def discover_and_install_submodules(root: Path | None = None, verbose: bool = True) -> dict:
    """Discover git submodules with pyproject.toml and install missing ones.

    Args:
        root: Root directory to scan (defaults to current working directory)
        verbose: Print status messages

    Returns:
        Dict with 'found', 'installed', 'failed', 'already_installed' lists.
    """
    if root is None:
        root = Path(__file__).parent

    result = {
        'found': [],
        'installed': [],
        'failed': [],
        'already_installed': [],
    }

    # Parse .gitmodules
    submodules = parse_gitmodules(root)

    if not submodules:
        return result

    if verbose:
        print(f"\nDiscovering submodule dependencies...")

    for submodule in submodules:
        submodule_path = root / submodule['path']
        pyproject_path = submodule_path / "pyproject.toml"

        # Check if submodule directory exists
        if not submodule_path.exists():
            if verbose:
                print(f"  [SKIP] {submodule['name']}: directory not found (run 'git submodule update --init')")
            continue

        # Check if it has pyproject.toml
        if not pyproject_path.exists():
            if verbose:
                print(f"  [SKIP] {submodule['name']}: no pyproject.toml found")
            continue

        result['found'].append(submodule['name'])

        # Get package name from pyproject.toml
        package_name = get_package_name_from_pyproject(pyproject_path)
        if not package_name:
            if verbose:
                print(f"  [SKIP] {submodule['name']}: could not read package name")
            continue

        # Check if already installed
        if is_package_installed(package_name):
            result['already_installed'].append(submodule['name'])
            if verbose:
                print(f"  [OK] {submodule['name']} ({package_name}): already installed")
            continue

        # Install the submodule
        if verbose:
            print(f"  [INSTALLING] {submodule['name']} ({package_name})...")

        if install_submodule(submodule_path, verbose):
            result['installed'].append(submodule['name'])
            if verbose:
                print(f"  [OK] {submodule['name']}: installed successfully")
        else:
            result['failed'].append(submodule['name'])
            if verbose:
                print(f"  [FAILED] {submodule['name']}: installation failed")

    if verbose and (result['installed'] or result['failed']):
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
    return len(result['failed']) == 0


if __name__ == "__main__":
    # Allow running standalone for testing
    success = ensure_submodule_deps()
    sys.exit(0 if success else 1)
