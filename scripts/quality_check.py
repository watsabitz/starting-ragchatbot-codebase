#!/usr/bin/env python3
"""
Development script for running code quality checks.
"""
import subprocess
import sys
from pathlib import Path


def run_command(command_list, description):
    """Run a command and handle its output."""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(
            command_list, capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            print(f"✅ {description} passed")
            if result.stdout.strip():
                print(result.stdout)
        else:
            print(f"❌ {description} failed")
            if result.stdout.strip():
                print(result.stdout)
            if result.stderr.strip():
                print(result.stderr)
            return False
    except FileNotFoundError:
        print(f"❌ Tool not found for {description}")
        return False
    except Exception as error:
        print(f"❌ Error running {description}: {error}")
        return False
    return True


def main():
    """Run all quality checks."""
    print("🚀 Running code quality checks...")
    
    project_root = Path(__file__).parent.parent
    backend_path = project_root / "backend"
    
    checks_passed = 0
    total_checks = 0
    
    # Black formatting check
    total_checks += 1
    if run_command(
        [sys.executable, "-m", "black", str(backend_path), "*.py", "--check"],
        "Black formatting check"
    ):
        checks_passed += 1
    
    # Isort import sorting check
    total_checks += 1
    if run_command(
        [sys.executable, "-m", "isort", str(backend_path), "*.py", "--check-only", "--profile", "black"],
        "Import sorting check"
    ):
        checks_passed += 1
    
    # Summary
    print(f"\n📊 Quality checks summary: {checks_passed}/{total_checks} passed")
    
    if checks_passed == total_checks:
        print("🎉 All quality checks passed!")
        sys.exit(0)
    else:
        print("💡 Run 'python scripts/format_code.py' to fix formatting issues")
        sys.exit(1)


if __name__ == "__main__":
    main()