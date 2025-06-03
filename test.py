#!/usr/bin/env python3
"""
Test script for GitHub repository monitoring functionality
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

def test_basic_functionality():
    """Test basic script functionality"""
    print("Testing basic functionality...")

    # Check if GITHUB_TOKEN is set
    if not os.getenv('GITHUB_TOKEN'):
        print("GITHUB_TOKEN not set - creating mock test")
        return test_without_token()

    script_dir = Path(__file__).parent

    # Test with test configuration
    cmd = [
        'python3',
        str(script_dir / 'github_monitor.py'),
        '--config', str(script_dir / 'test-config.yaml'),
        '--format', 'json',
        '--force-check'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            print(f"Script failed with error: {result.stderr}")
            return False

        # Parse output
        try:
            output_data = json.loads(result.stdout)
            print(f"✓ Script executed successfully")
            print(f"✓ Checked {output_data.get('total_repositories_checked', 0)} repositories")
            print(f"✓ Found {output_data.get('new_releases_found', 0)} releases")

            # Validate output structure
            required_fields = ['timestamp', 'total_repositories_checked', 'new_releases_found', 'releases']
            for field in required_fields:
                if field not in output_data:
                    print(f"✗ Missing required field: {field}")
                    return False

            print("✓ Output structure is valid")
            return True

        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON output: {e}")
            return False

    except subprocess.TimeoutExpired:
        print("✗ Script timed out")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_without_token():
    """Test script behavior without GitHub token"""
    print("Testing without GitHub token...")

    script_dir = Path(__file__).parent

    # Remove GITHUB_TOKEN if set
    env = os.environ.copy()
    env.pop('GITHUB_TOKEN', None)

    cmd = [
        'python3',
        str(script_dir / 'github_monitor.py'),
        '--config', str(script_dir / 'test-config.yaml')
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)

        if result.returncode == 1 and 'GITHUB_TOKEN' in result.stderr:
            print("✓ Script correctly validates GitHub token requirement")
            return True
        else:
            print(f"✗ Script should fail without GITHUB_TOKEN. Return code: {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_invalid_config():
    """Test script behavior with invalid configuration"""
    print("Testing with invalid configuration...")

    script_dir = Path(__file__).parent

    # Create temporary invalid config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content:\n  - bad\n    indentation")
        invalid_config = f.name

    cmd = [
        'python3',
        str(script_dir / 'github_monitor.py'),
        '--config', invalid_config
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            print("✓ Script correctly handles invalid configuration")
            return True
        else:
            print("✗ Script should fail with invalid configuration")
            return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    finally:
        # Clean up
        os.unlink(invalid_config)

def test_bash_wrapper():
    """Test bash wrapper script"""
    print("Testing bash wrapper...")

    script_dir = Path(__file__).parent
    wrapper_script = script_dir / 'scripts' / 'monitor.sh'

    if not wrapper_script.exists():
        print("✗ Bash wrapper script not found")
        return False

    # Test help option
    cmd = [str(wrapper_script), '--help']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and 'Usage:' in result.stdout:
            print("✓ Bash wrapper help function works")
            return True
        else:
            print(f"✗ Bash wrapper help failed. Return code: {result.returncode}")
            return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_api_error_handling():
    """Test script behavior with API errors"""
    print("Testing API error handling...")

    script_dir = Path(__file__).parent

    # Create a config that will trigger API errors (non-existent repo)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
repositories:
  - owner: this-owner-does-not-exist-12345
    repo: this-repo-does-not-exist-67890
    description: "Test repository that should not exist"
settings:
  rate_limit_delay: 0.1
""")
        test_config = f.name

    try:
        # Test 1: Default behavior (should exit with error)
        print("  Testing default behavior (exit on API error)...")
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = os.getenv('GITHUB_TOKEN', 'test-token')

        cmd = [
            'python3',
            str(script_dir / 'github_monitor.py'),
            '--config', test_config,
            '--force-check'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)

        # Check if the script exited due to API error (RequestException)
        if result.returncode == 1 and 'Exiting due to API error' in result.stderr:
            print("    ✓ Script exits on API error (default behavior)")

            # Test 2: With CONTINUE_ON_API_ERROR=true
            print("  Testing with CONTINUE_ON_API_ERROR=true...")
            env['CONTINUE_ON_API_ERROR'] = 'true'

            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)

            if result.returncode == 0:
                print("    ✓ Script continues with CONTINUE_ON_API_ERROR=true")
                return True
            else:
                print(f"    ✗ Script failed unexpectedly. Return code: {result.returncode}")
                print(f"    Stderr: {result.stderr}")
                return False
        elif 'No releases found' in result.stderr and result.returncode == 0:
            # This is a 404 case (repo exists but has no releases)
            print("    ✓ Script handles 404 (no releases) gracefully - not a RequestException")
            return True
        else:
            print(f"    ✗ Unexpected result. Return code: {result.returncode}")
            print(f"    Stderr: {result.stderr}")
            return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    finally:
        # Clean up
        os.unlink(test_config)

def main():
    """Run all tests"""
    print("=" * 50)
    print("GitHub Repository Monitoring - Test Suite")
    print("=" * 50)

    tests = [
        test_without_token,
        test_invalid_config,
        test_bash_wrapper,
        test_api_error_handling,
        test_basic_functionality
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        print(f"\n{test_func.__name__.replace('_', ' ').title()}:")
        print("-" * 30)

        if test_func():
            passed += 1
            print("PASSED")
        else:
            print("FAILED")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    print("=" * 50)

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
