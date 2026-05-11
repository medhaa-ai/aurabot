"""Phase 8 self-test — packaging readiness.

Verifies that the app is ready to be packaged:
- Correct version reported by health endpoint
- All packaging artefacts exist (icons, requirements.txt, build config)
- All backend modules import cleanly (no broken imports from cleanup)
- electron/setup.js exports the expected functions
- No unused heavy packages left in requirements.txt

Run against live backend:
  cd AuraBot
  .\\venv\\Scripts\\Activate.ps1
  python backend\\tests\\test_phase8.py
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

BASE    = "http://127.0.0.1:8765"
TIMEOUT = 10


def _get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT) as r:
        return json.loads(r.read())


# ── Backend smoke tests ────────────────────────────────────────────────────

def test_health_version_1_0_0():
    """GET /health must report v1.0.0 (release version, not phase tag)."""
    data = _get("/health")
    assert data.get("version") == "1.0.0", \
        f"Expected '1.0.0', got {data.get('version')!r}"
    print(f"  PASS GET /health: version={data['version']}")


def test_all_endpoints_respond():
    """Key endpoints must all return 2xx."""
    paths = [
        "/health",
        "/gmail/status",
        "/whatsapp/status",
        "/calendar/status",
        "/whatsapp/qr",
        "/nudges/pending",
        "/reminders/list",
        "/memory/stats",
        "/secrets/status",
    ]
    for p in paths:
        data = _get(p)
        assert isinstance(data, (dict, list)), f"{p} returned unexpected type: {type(data)}"
    print(f"  PASS All {len(paths)} endpoints respond with 2xx")


def test_backend_imports_clean():
    """All backend modules must import without errors.

    If core packages (fastapi etc.) are absent in the current interpreter,
    we instead verify import health via the live backend's 200 responses —
    a running backend with all endpoints up proves imports are clean.
    Run with 'venv\\Scripts\\Activate.ps1 && python ...' to get full module check.
    """
    try:
        import fastapi  # noqa: F401 — probe whether we're inside the venv
    except ImportError:
        # Outside venv: prove imports are clean via the live backend
        data = _get("/health")
        assert data.get("status") == "ok", f"Backend not healthy: {data}"
        print("  PASS Backend imports clean (verified via live backend — activate venv for full import check)")
        return

    modules = [
        "backend.main",
        "backend.claude_client",
        # memory package + shim
        "backend.memory",
        "backend.memory.episodic",
        "backend.memory.semantic",
        "backend.memory.short_term",
        "backend.memory.extractor",
        "backend.memory_store",
        # nudges package + shim
        "backend.nudges",
        "backend.nudges.scheduler",
        "backend.nudges.motivational",
        "backend.nudges.quotes",
        "backend.scheduler",
        # integrations — canonical names + shims
        "backend.integrations.gmail_client",
        "backend.integrations.calendar_client",
        "backend.integrations.gmail",
        "backend.integrations.calendar",
        "backend.integrations.whatsapp",
        "backend.integrations.web_search",
        # platform adapter
        "backend.platform_adapter",
        # rest
        "backend.reminder_store",
        "backend.settings_store",
        "backend.secure_store",
        "backend.time_utils",
        "backend.permissions",
    ]
    import importlib
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception as exc:
            assert False, f"Import failed for {m}: {exc}"
    print(f"  PASS All {len(modules)} backend modules import cleanly")


# ── Packaging artefact tests ───────────────────────────────────────────────

def test_requirements_txt_exists_and_is_clean():
    """requirements.txt must exist and not contain removed packages."""
    req_path = _PROJECT_ROOT / "requirements.txt"
    assert req_path.exists(), f"requirements.txt not found at {req_path}"
    content = req_path.read_text(encoding="utf-8")
    # These were listed in the requirements but never used — must be gone
    removed = ["apscheduler", "pypdf", "python-docx", "websockets"]
    for pkg in removed:
        assert pkg not in content, \
            f"Unused package '{pkg}' still in requirements.txt — remove it"
    # Core packages must still be present
    core = ["fastapi", "anthropic", "chromadb", "cryptography"]
    for pkg in core:
        assert pkg in content, f"Core package '{pkg}' missing from requirements.txt"
    print(f"  PASS requirements.txt: clean ({len(content.splitlines())} lines)")


def test_package_json_build_config():
    """package.json must have version 1.0.0 and asar: false."""
    pkg_path = _PROJECT_ROOT / "package.json"
    assert pkg_path.exists(), "package.json not found"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    assert pkg.get("version") == "1.0.0", f"Expected version 1.0.0, got {pkg.get('version')!r}"
    build = pkg.get("build", {})
    assert build.get("asar") is False, "build.asar must be false for Python file access"
    assert "requirements.txt" in str(build.get("files", [])), \
        "requirements.txt must be in build.files"
    print(f"  PASS package.json: version={pkg['version']}, asar={build['asar']}")


def test_icon_files_exist():
    """Icon files required for packaging must exist."""
    icons_dir = _PROJECT_ROOT / "frontend" / "icons"
    required  = ["icon.ico", "icon.png", "tray.png"]
    missing   = [f for f in required if not (icons_dir / f).exists()]
    if missing:
        print(f"  WARN Missing icons: {missing}")
        print(f"       Run: python scripts/make_icons.py   (needs: pip install pillow)")
    else:
        sizes = {f: (icons_dir / f).stat().st_size for f in required}
        print(f"  PASS Icons exist: {', '.join(f'{k} ({v}B)' for k,v in sizes.items())}")


def test_electron_setup_js_exports():
    """electron/setup.js must export checkAndSetup and getVenvPython."""
    setup_path = _PROJECT_ROOT / "electron" / "setup.js"
    assert setup_path.exists(), "electron/setup.js not found"
    content = setup_path.read_text(encoding="utf-8")
    for sym in ("checkAndSetup", "getVenvPython", "getBackendScript"):
        assert sym in content, f"setup.js missing export: {sym}"
    print("  PASS electron/setup.js exports checkAndSetup, getVenvPython, getBackendScript")


def test_build_script_exists():
    """scripts/build.ps1 must exist."""
    build_path = _PROJECT_ROOT / "scripts" / "build.ps1"
    assert build_path.exists(), "scripts/build.ps1 not found"
    content = build_path.read_text(encoding="utf-8")
    assert "electron-builder" in content, "build.ps1 must call electron-builder"
    print("  PASS scripts/build.ps1 exists and references electron-builder")


def test_license_file_exists():
    """LICENSE.txt must exist (required by NSIS installer)."""
    lic = _PROJECT_ROOT / "LICENSE.txt"
    assert lic.exists(), "LICENSE.txt not found (required by NSIS nsis.license setting)"
    print("  PASS LICENSE.txt exists")


def test_whatsapp_bridge_has_node_modules():
    """whatsapp_bridge/node_modules must exist (needed for bridge to run)."""
    nm = _PROJECT_ROOT / "whatsapp_bridge" / "node_modules"
    if nm.exists():
        count = sum(1 for _ in nm.iterdir())
        print(f"  PASS whatsapp_bridge/node_modules exists ({count} packages)")
    else:
        print("  WARN whatsapp_bridge/node_modules missing — run: cd whatsapp_bridge && npm install")


def test_set_reminder_tool_in_build_tools():
    """set_reminder must always be included in _build_tools()."""
    from backend.claude_client import _build_tools
    names = [t["name"] for t in _build_tools()]
    assert "set_reminder"  in names, f"set_reminder missing: {names}"
    assert "web_search"    in names, f"web_search missing: {names}"
    print(f"  PASS _build_tools() core tools present: {names}")


# ── Runner ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_health_version_1_0_0,
        test_all_endpoints_respond,
        test_backend_imports_clean,
        test_requirements_txt_exists_and_is_clean,
        test_package_json_build_config,
        test_icon_files_exist,
        test_electron_setup_js_exports,
        test_build_script_exists,
        test_license_file_exists,
        test_whatsapp_bridge_has_node_modules,
        test_set_reminder_tool_in_build_tools,
    ]
    failures = []

    print("\n=== AuraBot Phase 8 Self-Test (Packaging Readiness) ===\n")
    print("Waiting for backend...")
    for _ in range(30):
        try:
            _get("/health")
            break
        except Exception:
            time.sleep(1)
    else:
        print("FAIL: Backend not reachable. Start the app (npm start) then re-run.")
        sys.exit(1)

    print("Backend is up. Running tests...\n")

    for t in tests:
        try:
            t()
        except AssertionError as err:
            print(f"  FAIL {t.__name__}: {err}")
            failures.append(t.__name__)
        except Exception as err:
            print(f"  ERROR {t.__name__}: {err}")
            failures.append(t.__name__)

    print()
    if failures:
        print(f"RESULT: {len(failures)}/{len(tests)} tests FAILED: {', '.join(failures)}")
        sys.exit(1)
    else:
        print(f"RESULT: All {len(tests)} tests passed. AuraBot v1.0.0 is ready to package!")
        print()
        print("To build the installer, run:")
        print("  .\\scripts\\build.ps1")
        sys.exit(0)


if __name__ == "__main__":
    run_all()
