#!/usr/bin/env python3
"""
Development script for automatically formatting code.
"""
import subprocess
import sys
from pathlib import Path


def run_formatter(command_list, description):
    """Run a formatter and handle its output."""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(
            command_list, capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            print(f"✅ {description} completed")
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
    """Format all code files."""
    print("🚀 Formatting code files...")
    
    project_root = Path(__file__).parent.parent
    backend_path = project_root / "backend"
    
    formatters_run = 0
    total_formatters = 0
    
    # Run isort first (import sorting)
    total_formatters += 1
    if run_formatter(
        [sys.executable, "-m", "isort", str(backend_path), "*.py", "--profile", "black"],
        "Sorting imports with isort"
    ):
        formatters_run += 1
    
    # Run black (code formatting)
    total_formatters += 1
    if run_formatter(
        [sys.executable, "-m", "black", str(backend_path), "*.py"],
        "Formatting code with black"
    ):
        formatters_run += 1
    
    # Summary
    print(f"\n📊 Formatting summary: {formatters_run}/{total_formatters} formatters completed")
    
    if formatters_run == total_formatters:
        print("🎉 All code formatting completed successfully!")
        print("💡 Run 'python scripts/quality_check.py' to verify formatting")
        sys.exit(0)
    else:
        print("❌ Some formatters failed")
        sys.exit(1)


if __name__ == "__main__":
    main()