#!/usr/bin/env python3
"""
Demonstration script showing how to filter Istio 1.26.2 release artifacts
to only keep istio-1.26.2-linux-amd64.tar.gz
"""

def demo_istio_filtering():
    """Demonstrate filtering Istio release assets"""
    
    # Sample Istio 1.26.2 release data with all assets
    istio_release = {
        'repository': 'istio/istio',
        'tag_name': '1.26.2',
        'name': 'Istio 1.26.2',
        'published_at': '2024-11-14T20:35:04Z',
        'html_url': 'https://github.com/istio/istio/releases/tag/1.26.2',
        'author': {'login': 'istio-release-robot'},
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
    
    print("Original Istio 1.26.2 release assets:")
    print(f"Total assets: {len(istio_release['assets'])}")
    for asset in istio_release['assets']:
        size_mb = asset['size'] / (1024 * 1024)
        print(f"  - {asset['name']} ({size_mb:.1f} MB)")
    
    print("\n" + "="*50)
    
    # Filter to only keep the target asset
    target_asset = 'istio-1.26.2-linux-amd64.tar.gz'
    filtered_assets = [
        asset for asset in istio_release['assets']
        if asset['name'] == target_asset
    ]
    
    print(f"\nFiltered to only keep: {target_asset}")
    print(f"Remaining assets: {len(filtered_assets)}")
    for asset in filtered_assets:
        size_mb = asset['size'] / (1024 * 1024)
        print(f"  ✓ {asset['name']} ({size_mb:.1f} MB)")
    
    # Show what was filtered out
    removed_assets = [
        asset for asset in istio_release['assets']
        if asset['name'] != target_asset
    ]
    
    print(f"\nFiltered out assets: {len(removed_assets)}")
    for asset in removed_assets:
        size_mb = asset['size'] / (1024 * 1024)
        print(f"  ✗ {asset['name']} ({size_mb:.1f} MB)")
    
    print(f"\n✅ Successfully filtered {len(removed_assets)} assets, keeping only {target_asset}")
    
    return {
        'original_count': len(istio_release['assets']),
        'filtered_count': len(filtered_assets),
        'removed_count': len(removed_assets),
        'target_asset': target_asset
    }


if __name__ == '__main__':
    result = demo_istio_filtering()
    print(f"\nSUMMARY:")
    print(f"Original assets: {result['original_count']}")
    print(f"Filtered assets: {result['filtered_count']}")
    print(f"Removed assets: {result['removed_count']}")
    print(f"Target asset: {result['target_asset']}")