#!/usr/bin/env python3
"""
Test script to verify all upload scripts support YAML files.
"""

import os
from pathlib import Path

def check_script_supports_yaml(script_path):
    """Check if an upload script supports YAML file extensions."""
    if not script_path.exists():
        return False, "Script not found"
    
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Check for YAML extensions
    has_yaml = '.yaml' in content and '.yml' in content
    
    # Check if it still has the old hardcoded filter
    has_old_filter = '.gz.*\\.zip' in content.replace(' ', '').replace('\n', '')
    
    if has_yaml and not has_old_filter:
        return True, "✅ Supports YAML files"
    elif has_yaml and has_old_filter:
        return False, "⚠️ Mixed: Has YAML support but also old hardcoded filter"
    else:
        return False, "❌ No YAML support found"

def main():
    """Test all upload scripts."""
    scripts_dir = Path('/Users/markalston/git/release-monitor/scripts')
    
    upload_scripts = [
        'upload-to-s3.py',
        'upload-to-s3-mc.py', 
        'upload-to-s3-no-proxy.py'
    ]
    
    print("Testing upload scripts for YAML support...")
    print("=" * 60)
    
    all_good = True
    
    for script_name in upload_scripts:
        script_path = scripts_dir / script_name
        supports_yaml, message = check_script_supports_yaml(script_path)
        
        print(f"{script_name:25} {message}")
        
        if not supports_yaml:
            all_good = False
    
    print("=" * 60)
    
    if all_good:
        print("🎉 ALL UPLOAD SCRIPTS SUPPORT YAML FILES!")
        print("\nwavefront-operator.yaml will now be uploaded by any of these scripts.")
    else:
        print("❌ Some scripts still need fixes.")
        print("\nPlease check the scripts marked with warnings or errors above.")
    
    return all_good

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)