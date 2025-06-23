#!/usr/bin/env python3
"""
Demonstration of ASSET_PATTERNS parameter usage for Istio 1.26.2 release filtering

This script shows how to use the ASSET_PATTERNS parameter to filter Istio release
artifacts to only download specific assets based on platform and component needs.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_downloader import GitHubDownloader


def demo_istio_asset_patterns():
    """Demonstrate various ASSET_PATTERNS configurations for Istio releases"""
    
    # Sample Istio 1.26.2 release data (mimics real GitHub API response)
    istio_release = {
        'id': 127456789,
        'tag_name': '1.26.2',
        'name': 'Istio 1.26.2',
        'assets': [
            {'name': 'istio-1.26.2-linux-amd64.tar.gz', 'size': 23456789},
            {'name': 'istio-1.26.2-linux-arm64.tar.gz', 'size': 22345678},
            {'name': 'istio-1.26.2-osx-amd64.tar.gz', 'size': 23567890},
            {'name': 'istio-1.26.2-osx-arm64.tar.gz', 'size': 23678901},
            {'name': 'istio-1.26.2-win.zip', 'size': 24567890},
            {'name': 'istioctl-1.26.2-linux-amd64.tar.gz', 'size': 12345678},
            {'name': 'istioctl-1.26.2-linux-arm64.tar.gz', 'size': 12234567},
            {'name': 'istioctl-1.26.2-osx-amd64.tar.gz', 'size': 12456789},
            {'name': 'istioctl-1.26.2-osx-arm64.tar.gz', 'size': 12567890},
            {'name': 'istioctl-1.26.2-win.exe', 'size': 13456789}
        ]
    }
    
    # Initialize downloader (we'll use its pattern matching without actually downloading)
    downloader = GitHubDownloader(token="fake-token", download_dir="/tmp")
    
    print("🚀 ASSET_PATTERNS Demonstration - Istio 1.26.2 Release")
    print("=" * 70)
    print(f"📦 Original release contains {len(istio_release['assets'])} assets:")
    for asset in istio_release['assets']:
        size_mb = asset['size'] / (1024 * 1024)
        print(f"   • {asset['name']} ({size_mb:.1f} MB)")
    
    # Test different ASSET_PATTERNS configurations
    scenarios = [
        {
            'title': '🎯 Filter for AMD64 tarballs only',
            'patterns': ['*-amd64.tar.gz'],
            'description': 'Keep only AMD64 architecture tarballs (both Linux and macOS)',
            'use_case': 'Development environments supporting multiple OS but only AMD64'
        },
        {
            'title': '🐧 Filter for Linux AMD64 only', 
            'patterns': ['*-linux-amd64.tar.gz'],
            'description': 'Keep only Linux AMD64 packages',
            'use_case': 'Production Linux deployments'
        },
        {
            'title': '🏢 Main Istio package only (no istioctl)',
            'patterns': ['istio-*.tar.gz', '!istioctl-*'],
            'description': 'Keep main Istio packages but exclude istioctl binaries',
            'use_case': 'Server deployments where istioctl is not needed'
        },
        {
            'title': '📌 Single specific file',
            'patterns': ['istio-1.26.2-linux-amd64.tar.gz'],
            'description': 'Download only one specific file',
            'use_case': 'Targeted deployment for specific environment'
        },
        {
            'title': '🚫 Exclude Windows builds',
            'patterns': ['*.tar.gz', '!*win*'],
            'description': 'All tarballs except Windows builds',
            'use_case': 'Unix-only infrastructure'
        },
        {
            'title': '⚙️ Development setup (Linux tools only)',
            'patterns': ['*-linux-*.tar.gz', '*-linux-*.exe'],
            'description': 'All Linux variants for development',
            'use_case': 'Developer workstation setup'
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'-' * 70}")
        print(f"{scenario['title']}")
        print(f"Patterns: {scenario['patterns']}")
        print(f"Use case: {scenario['use_case']}")
        print(f"Description: {scenario['description']}")
        
        # Apply pattern filtering
        matching_assets = []
        for asset in istio_release['assets']:
            if downloader._matches_patterns(asset['name'], scenario['patterns']):
                matching_assets.append(asset)
        
        total_size = sum(asset['size'] for asset in matching_assets)
        total_size_mb = total_size / (1024 * 1024)
        
        print(f"\n📊 Results: {len(matching_assets)} assets matched ({total_size_mb:.1f} MB total)")
        
        if matching_assets:
            print("✅ Downloaded assets:")
            for asset in matching_assets:
                size_mb = asset['size'] / (1024 * 1024)
                print(f"   ✓ {asset['name']} ({size_mb:.1f} MB)")
        else:
            print("❌ No assets matched the patterns")
        
        # Show what was filtered out
        excluded_assets = [
            asset for asset in istio_release['assets'] 
            if not downloader._matches_patterns(asset['name'], scenario['patterns'])
        ]
        
        if excluded_assets:
            print(f"\n🗑️  Filtered out {len(excluded_assets)} assets:")
            for asset in excluded_assets[:3]:  # Show first 3
                size_mb = asset['size'] / (1024 * 1024)
                print(f"   ✗ {asset['name']} ({size_mb:.1f} MB)")
            if len(excluded_assets) > 3:
                print(f"   ... and {len(excluded_assets) - 3} more")
    
    print(f"\n{'=' * 70}")
    print("🎉 ASSET_PATTERNS Demo Complete!")
    print("\n💡 How to use in Concourse pipeline:")
    print("   Set the ASSET_PATTERNS parameter in your pipeline config:")
    print('   ASSET_PATTERNS: \'["*-linux-amd64.tar.gz"]\'')
    print("\n💡 How to use in download script:")
    print("   python download_releases.py --asset-patterns '*-linux-amd64.tar.gz'")
    print("=" * 70)


def show_concourse_config_example():
    """Show example Concourse pipeline configuration"""
    
    print("\n📋 Example Concourse Pipeline Configuration")
    print("=" * 50)
    
    example_configs = [
        {
            'scenario': 'Linux AMD64 only',
            'config': '\'["*-linux-amd64.tar.gz"]\''
        },
        {
            'scenario': 'All AMD64 (Linux + macOS)',
            'config': '\'["*-amd64.tar.gz"]\''
        },
        {
            'scenario': 'Main Istio only (no istioctl)',
            'config': '\'["istio-*.tar.gz", "!istioctl-*"]\''
        },
        {
            'scenario': 'Single specific file',
            'config': '\'["istio-1.26.2-linux-amd64.tar.gz"]\''
        }
    ]
    
    for config in example_configs:
        print(f"\n# {config['scenario']}")
        print(f"download_asset_patterns: {config['config']}")
    
    print("\n📋 Example Repository Override Configuration")
    print("=" * 50)
    print("""
# In your pipeline params file:
download_repository_overrides: |
  {
    "istio/istio": {
      "asset_patterns": ["*-linux-amd64.tar.gz"],
      "include_prereleases": false
    },
    "kubernetes/kubernetes": {
      "asset_patterns": ["kubernetes-client-*.tar.gz", "kubernetes-server-*.tar.gz"],
      "include_prereleases": false
    }
  }
""")


if __name__ == '__main__':
    demo_istio_asset_patterns()
    show_concourse_config_example()