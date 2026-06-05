#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║     PROTOCOL & MEDIA TEAM — SETUP SCRIPT v2.0           ║
║     Wellspring of Grace Arena Chapel                     ║
╚══════════════════════════════════════════════════════════╝

Run this script once to set up and launch the system.
Usage:  python setup.py
"""

import subprocess
import sys
import os
import platform

REQUIRED_PACKAGES = ["flask"]
APP_FILE = "app.py"
TEMPLATES_DIR = "templates"
PORT = 5000

# ── COLOURS ──────────────────────────────────────────────
def green(t):  return f"\033[92m{t}\033[0m"
def yellow(t): return f"\033[93m{t}\033[0m"
def red(t):    return f"\033[91m{t}\033[0m"
def bold(t):   return f"\033[1m{t}\033[0m"
def cyan(t):   return f"\033[96m{t}\033[0m"

def banner():
    print()
    print(cyan("╔══════════════════════════════════════════════════════════╗"))
    print(cyan("║") + bold("     PROTOCOL & MEDIA TEAM — SETUP SCRIPT v2.0           ") + cyan("║"))
    print(cyan("║") + "     Wellspring of Grace Arena Chapel                     " + cyan("║"))
    print(cyan("╚══════════════════════════════════════════════════════════╝"))
    print()

def step(n, total, msg):
    print(f"  {cyan(f'[{n}/{total}]')} {msg}")

def ok(msg):   print(f"        {green('✔')}  {msg}")
def warn(msg): print(f"        {yellow('⚠')}  {msg}")
def fail(msg): print(f"        {red('✘')}  {msg}")

# ── CHECKS ────────────────────────────────────────────────
def check_python():
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        fail(f"Python 3.7+ required. You have {version.major}.{version.minor}.")
        sys.exit(1)
    ok(f"Python {version.major}.{version.minor}.{version.micro} — OK")

def check_files():
    missing = []
    if not os.path.isfile(APP_FILE):
        missing.append(APP_FILE)
    if not os.path.isdir(TEMPLATES_DIR):
        missing.append(TEMPLATES_DIR + "/")
    else:
        required_templates = [
            "base.html", "login.html", "dashboard.html",
            "members.html", "profile.html", "attendance.html",
            "duty.html", "welfare.html", "disciplinary.html", "reports.html"
        ]
        for t in required_templates:
            path = os.path.join(TEMPLATES_DIR, t)
            if not os.path.isfile(path):
                missing.append(f"templates/{t}")

    if missing:
        fail("Missing required files:")
        for m in missing:
            print(f"             - {m}")
        print()
        print(f"  {yellow('Make sure all files from the zip are in the same folder as setup.py.')}")
        sys.exit(1)

    ok(f"app.py found")
    ok(f"All {len(required_templates)} templates found")

def install_packages():
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
            ok(f"{pkg} already installed")
        except ImportError:
            warn(f"{pkg} not found — installing...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                ok(f"{pkg} installed successfully")
            else:
                fail(f"Failed to install {pkg}")
                print(f"         {red('Error:')} {result.stderr.strip()}")
                print(f"\n  Try manually:  pip install {pkg}")
                sys.exit(1)

def check_port():
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', PORT))
    sock.close()
    if result == 0:
        warn(f"Port {PORT} is already in use. The server may not start.")
        warn("Close any other running instances and try again.")
    else:
        ok(f"Port {PORT} is available")

def init_database():
    """Run app init_db() to create and seed the database."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", APP_FILE)
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)
    app_module.init_db()
    db_path = app_module.DB
    size_kb = os.path.getsize(db_path) / 1024 if os.path.exists(db_path) else 0
    ok(f"Database initialised — {os.path.basename(db_path)} ({size_kb:.1f} KB)")
    ok("Default users and members seeded")

def print_summary():
    print()
    print(cyan("  ══════════════════════════════════════════════════════"))
    print(bold(f"  ✅  Setup complete! Starting the server on port {PORT}..."))
    print(cyan("  ══════════════════════════════════════════════════════"))
    print()
    print(f"  {bold('Open your browser and go to:')}")
    print(f"  {green(f'  ➜  http://localhost:{PORT}')}")
    print()
    print(f"  {bold('Login Credentials:')}")
    print(f"  {'Username':<12} {'Password':<16} {'Role'}")
    print(f"  {'-'*42}")
    print(f"  {'asare':<12} {'admin123':<16} Admin (Head of Protocol)")
    print(f"  {'richard':<12} {'richard123':<16} Secretary")
    print(f"  {'apostle':<12} {'apostle123':<16} Member")
    print()
    print(f"  {yellow('Press Ctrl+C to stop the server.')}")
    print()

def launch():
    os.environ["FLASK_ENV"] = "production"
    os.execv(sys.executable, [sys.executable, APP_FILE])

# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    banner()

    TOTAL = 5
    step(1, TOTAL, "Checking Python version...")
    check_python()

    step(2, TOTAL, "Verifying project files...")
    check_files()

    step(3, TOTAL, "Installing dependencies...")
    install_packages()

    step(4, TOTAL, "Checking port availability...")
    check_port()

    step(5, TOTAL, "Initialising database...")
    init_database()

    print_summary()
    launch()
