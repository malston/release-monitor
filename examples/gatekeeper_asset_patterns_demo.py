#!/usr/bin/env python3
"""
Demonstration of ASSET_PATTERNS parameter usage for Gatekeeper release filtering

This script shows how to use the ASSET_PATTERNS parameter to filter Gatekeeper release
artifacts using the pattern: ["gator-v*-linux-amd64.tar.gz", "*-linux-amd64.tar.gz"]

Gatekeeper typically releases multiple assets including:
- gator CLI tool for multiple platforms
- manager container images
- helm charts
- various platform-specific binaries
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_downloader import GitHubDownloader


def demo_gatekeeper_asset_patterns():
    """Demonstrate ASSET_PATTERNS configurations for Gatekeeper releases"""
    
    # Sample Gatekeeper release data (based on real open-policy-agent/gatekeeper releases)
    gatekeeper_release = {
        'id': 123456789,
        'tag_name': 'v3.14.0',
        'name': 'Gatekeeper v3.14.0',
        'published_at': '2023-11-15T18:30:00Z',
        'assets': [
            # Gator CLI binaries (the main CLI tool)
            {'name': 'gator-v3.14.0-linux-amd64.tar.gz', 'size': 15234567},
            {'name': 'gator-v3.14.0-linux-arm64.tar.gz', 'size': 14876543},
            {'name': 'gator-v3.14.0-darwin-amd64.tar.gz', 'size': 15456789},
            {'name': 'gator-v3.14.0-darwin-arm64.tar.gz', 'size': 15123456},
            {'name': 'gator-v3.14.0-windows-amd64.tar.gz', 'size': 16234567},
            
            # Manager binaries (the controller component)
            {'name': 'manager-v3.14.0-linux-amd64.tar.gz', 'size': 45234567},
            {'name': 'manager-v3.14.0-linux-arm64.tar.gz', 'size': 44876543},
            {'name': 'manager-v3.14.0-darwin-amd64.tar.gz', 'size': 45456789},
            {'name': 'manager-v3.14.0-darwin-arm64.tar.gz', 'size': 45123456},
            {'name': 'manager-v3.14.0-windows-amd64.tar.gz', 'size': 46234567},
            
            # Additional assets
            {'name': 'gatekeeper-v3.14.0-helm-chart.tgz', 'size': 12345},
            {'name': 'gatekeeper-v3.14.0-manifests.yaml', 'size': 67890},
            {'name': 'checksums.txt', 'size': 1234},
            {'name': 'README.md', 'size': 5678}
        ]
    }
    
    # Initialize downloader
    downloader = GitHubDownloader(token="fake-token", download_dir="/tmp")
    
    print("🔒 ASSET_PATTERNS Demonstration - Gatekeeper v3.14.0 Release")
    print("=" * 75)
    print(f"📦 Original release contains {len(gatekeeper_release['assets'])} assets:")
    total_size = 0
    for asset in gatekeeper_release['assets']:
        size_mb = asset['size'] / (1024 * 1024)
        total_size += asset['size']
        print(f"   • {asset['name']} ({size_mb:.1f} MB)")
    
    total_size_mb = total_size / (1024 * 1024)
    print(f"\n📊 Total size: {total_size_mb:.1f} MB")
    
    # Test different ASSET_PATTERNS configurations
    scenarios = [
        {
            'title': '🎯 Your Specific Pattern: Gator + Linux AMD64',
            'patterns': ['gator-v*-linux-amd64.tar.gz', '*-linux-amd64.tar.gz'],
            'description': 'Gator CLI + all Linux AMD64 binaries (gator + manager)',
            'use_case': 'Linux development/deployment with both CLI and manager components'
        },
        {
            'title': '🛠️  Gator CLI Only (Linux AMD64)',
            'patterns': ['gator-v*-linux-amd64.tar.gz'],
            'description': 'Only the Gator CLI tool for Linux AMD64',
            'use_case': 'Policy development and testing (CLI only)'
        },
        {
            'title': '⚙️  Manager Only (Linux AMD64)',
            'patterns': ['manager-v*-linux-amd64.tar.gz'],
            'description': 'Only the Gatekeeper manager/controller for Linux AMD64',
            'use_case': 'Kubernetes cluster deployment (controller only)'
        },
        {
            'title': '🐧 All Linux AMD64 Components',
            'patterns': ['*-linux-amd64.tar.gz'],
            'description': 'All Linux AMD64 binaries (gator + manager)',
            'use_case': 'Complete Linux AMD64 deployment'
        },
        {
            'title': '🔧 Development Setup (All Gator Platforms)',
            'patterns': ['gator-v*'],
            'description': 'Gator CLI for all platforms (Linux, macOS, Windows)',
            'use_case': 'Multi-platform development team'
        },
        {
            'title': '📋 Configuration Only',
            'patterns': ['*.yaml', '*.yml', '*.tgz'],
            'description': 'Helm charts and manifests only',
            'use_case': 'GitOps deployment with existing binaries'
        },
        {
            'title': '🚫 Exclude Windows Builds',
            'patterns': ['*.tar.gz', '!*windows*'],
            'description': 'All tarballs except Windows builds',
            'use_case': 'Unix-only infrastructure'
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'-' * 75}")
        print(f"{scenario['title']}")
        print(f"Patterns: {scenario['patterns']}")
        print(f"Use case: {scenario['use_case']}")
        print(f"Description: {scenario['description']}")
        
        # Apply pattern filtering
        matching_assets = []
        for asset in gatekeeper_release['assets']:
            if downloader._matches_patterns(asset['name'], scenario['patterns']):
                matching_assets.append(asset)
        
        total_size = sum(asset['size'] for asset in matching_assets)
        total_size_mb = total_size / (1024 * 1024)
        original_size_mb = sum(asset['size'] for asset in gatekeeper_release['assets']) / (1024 * 1024)
        savings_pct = ((original_size_mb - total_size_mb) / original_size_mb) * 100 if original_size_mb > 0 else 0
        
        print(f"\n📊 Results: {len(matching_assets)} assets matched ({total_size_mb:.1f} MB total)")
        print(f"💾 Bandwidth savings: {savings_pct:.1f}% ({original_size_mb - total_size_mb:.1f} MB saved)")
        
        if matching_assets:
            print("✅ Downloaded assets:")
            for asset in matching_assets:
                size_mb = asset['size'] / (1024 * 1024)
                component = "🛠️ CLI" if "gator" in asset['name'] else "⚙️ Manager" if "manager" in asset['name'] else "📋 Config"
                print(f"   ✓ {asset['name']} ({size_mb:.1f} MB) {component}")
        else:
            print("❌ No assets matched the patterns")
        
        # Show what was filtered out for the main pattern
        if i == 1:  # Your specific pattern
            excluded_assets = [
                asset for asset in gatekeeper_release['assets'] 
                if not downloader._matches_patterns(asset['name'], scenario['patterns'])
            ]
            
            if excluded_assets:
                print(f"\n🗑️  Filtered out {len(excluded_assets)} assets:")
                for asset in excluded_assets[:5]:  # Show first 5
                    size_mb = asset['size'] / (1024 * 1024)
                    print(f"   ✗ {asset['name']} ({size_mb:.1f} MB)")
                if len(excluded_assets) > 5:
                    print(f"   ... and {len(excluded_assets) - 5} more")
    
    print(f"\n{'=' * 75}")
    print("🎉 Gatekeeper ASSET_PATTERNS Demo Complete!")
    
    # Highlight the specific pattern requested
    print(f"\n🎯 YOUR SPECIFIC PATTERN ANALYSIS:")
    print(f"   Pattern: [\"gator-v*-linux-amd64.tar.gz\", \"*-linux-amd64.tar.gz\"]")
    
    target_patterns = ['gator-v*-linux-amd64.tar.gz', '*-linux-amd64.tar.gz']
    target_assets = []
    for asset in gatekeeper_release['assets']:
        if downloader._matches_patterns(asset['name'], target_patterns):
            target_assets.append(asset)
    
    target_size_mb = sum(asset['size'] for asset in target_assets) / (1024 * 1024)
    print(f"   Downloads: {len(target_assets)} assets ({target_size_mb:.1f} MB)")
    print(f"   Components: Gator CLI + Manager (both Linux AMD64)")
    print(f"   Perfect for: Linux deployment with both CLI and controller")
    
    print(f"\n💡 How to use in pipeline:")
    print(f'   repositories_override: \'{"open-policy-agent/gatekeeper": {"asset_patterns": ["gator-v*-linux-amd64.tar.gz", "*-linux-amd64.tar.gz"]}}\'')
    print("=" * 75)


def show_gatekeeper_concourse_examples():
    """Show practical Concourse pipeline configuration examples for Gatekeeper"""
    
    print("\n📋 Gatekeeper Concourse Pipeline Examples")
    print("=" * 55)
    
    examples = [
        {
            'name': 'Your Pattern: Gator + Linux AMD64',
            'config': '''
# Complete Linux AMD64 setup (CLI + Manager)
repositories_override: |-
  {
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["gator-v*-linux-amd64.tar.gz", "*-linux-amd64.tar.gz"],
      "include_prereleases": false
    }
  }''',
            'result': 'Downloads: gator CLI + manager (Linux AMD64 only)'
        },
        {
            'name': 'CLI Only for Policy Development',
            'config': '''
# Gator CLI only for policy testing
repositories_override: |-
  {
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["gator-v*-linux-amd64.tar.gz"],
      "include_prereleases": false
    }
  }''',
            'result': 'Downloads: gator CLI only (15.3 MB)'
        },
        {
            'name': 'Production Deployment (Manager Only)',
            'config': '''
# Manager/controller only for Kubernetes deployment
repositories_override: |-
  {
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["manager-v*-linux-amd64.tar.gz"],
      "include_prereleases": false
    }
  }''',
            'result': 'Downloads: manager only (45.2 MB)'
        },
        {
            'name': 'Multi-Platform Development',
            'config': '''
# Gator CLI for all platforms
repositories_override: |-
  {
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["gator-v*", "!*windows*"],
      "include_prereleases": false
    }
  }''',
            'result': 'Downloads: gator for Linux + macOS (excludes Windows)'
        },
        {
            'name': 'GitOps Configuration Only',
            'config': '''
# Helm charts and manifests only
repositories_override: |-
  {
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["*.yaml", "*.yml", "*.tgz"],
      "include_prereleases": false
    }
  }''',
            'result': 'Downloads: Helm chart + manifests only'
        }
    ]
    
    for example in examples:
        print(f"\n📌 {example['name']}")
        print(f"Result: {example['result']}")
        print(example['config'])
    
    print(f"\n📋 Global Pipeline Configuration")
    print("=" * 35)
    print("""
# In your pipeline params file - Let repository overrides handle all downloads
repositories_override: |-
  {
    "open-policy-agent/gatekeeper": {
      "asset_patterns": ["gator-v*-linux-amd64.tar.gz", "*-linux-amd64.tar.gz"],
      "include_prereleases": false
    },
    "istio/istio": {
      "asset_patterns": ["istio-*-linux-amd64.tar.gz"],
      "include_prereleases": false
    }
  }
""")

def analyze_pattern_specificity():
    """Analyze how the specific patterns work"""
    
    print(f"\n🔍 Pattern Analysis: Your Specific Configuration")
    print("=" * 55)
    
    patterns = ['gator-v*-linux-amd64.tar.gz', '*-linux-amd64.tar.gz']
    
    print(f"Patterns: {patterns}")
    print(f"\nPattern Breakdown:")
    print(f"  1. 'gator-v*-linux-amd64.tar.gz'")
    print(f"     → Matches: gator-v3.14.0-linux-amd64.tar.gz")
    print(f"     → Purpose: Specifically get the Gator CLI for Linux AMD64")
    
    print(f"\n  2. '*-linux-amd64.tar.gz'")
    print(f"     → Matches: manager-v3.14.0-linux-amd64.tar.gz, gator-v3.14.0-linux-amd64.tar.gz")
    print(f"     → Purpose: Get ALL Linux AMD64 components")
    
    print(f"\nCombined Effect:")
    print(f"  ✅ gator-v3.14.0-linux-amd64.tar.gz (matched by both patterns)")
    print(f"  ✅ manager-v3.14.0-linux-amd64.tar.gz (matched by second pattern)")
    print(f"  ❌ gator-v3.14.0-darwin-amd64.tar.gz (not Linux)")
    print(f"  ❌ manager-v3.14.0-linux-arm64.tar.gz (not AMD64)")
    print(f"  ❌ gatekeeper-v3.14.0-manifests.yaml (not .tar.gz)")
    
    print(f"\n💡 Why This Pattern Works Well:")
    print(f"  • Gets both CLI tool (gator) and controller (manager)")
    print(f"  • Specific to Linux AMD64 architecture")
    print(f"  • Excludes unnecessary platforms and file types")
    print(f"  • Perfect for Linux-based CI/CD and deployment")


if __name__ == '__main__':
    demo_gatekeeper_asset_patterns()
    show_gatekeeper_concourse_examples()
    analyze_pattern_specificity()