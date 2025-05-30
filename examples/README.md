# Release Monitor Examples

This directory contains example configurations and use cases for the GitHub Release Monitor.

## Basic Examples

### 1. Monitor a Single Repository

```yaml
# single-repo.yaml
repositories:
  - owner: kubernetes
    repo: kubernetes
    description: "Kubernetes releases"

settings:
  rate_limit_delay: 1.0
  max_releases_per_repo: 5
  include_prereleases: false
```

### 2. Monitor Multiple Projects

```yaml
# multi-project.yaml
repositories:
  # Container Orchestration
  - owner: kubernetes
    repo: kubernetes
    description: "Kubernetes"
  
  - owner: docker
    repo: compose
    description: "Docker Compose"
  
  # CI/CD Tools
  - owner: concourse
    repo: concourse
    description: "Concourse CI"
  
  - owner: argoproj
    repo: argo-cd
    description: "Argo CD"

settings:
  rate_limit_delay: 1.5
  max_releases_per_repo: 3
  include_prereleases: false
```

## Advanced Examples

### 3. Include Pre-releases

```yaml
# with-prereleases.yaml
repositories:
  - owner: nodejs
    repo: node
    description: "Node.js with pre-releases"

settings:
  include_prereleases: true
  max_releases_per_repo: 10
```

### 4. Cron Job Setup

```bash
#!/bin/bash
# monitor-releases.sh - Run this via cron

source /path/to/venv/bin/activate
export GITHUB_TOKEN="your_token_here"

python3 /path/to/github_monitor.py \
  --config /path/to/config.yaml \
  --output /var/log/releases/releases-$(date +%Y%m%d).json

# Send notification if new releases found
if [ -s /var/log/releases/releases-$(date +%Y%m%d).json ]; then
  mail -s "New GitHub Releases Found" admin@example.com < /var/log/releases/releases-$(date +%Y%m%d).json
fi
```

Add to crontab:

```bash
# Check for new releases every 6 hours
0 */6 * * * /path/to/monitor-releases.sh
```

### 5. Slack Notification Integration

```python
# notify-slack.py
import json
import requests
import subprocess

# Run the monitor
result = subprocess.run([
    'python3', 'github_monitor.py',
    '--config', 'config.yaml',
    '--format', 'json'
], capture_output=True, text=True)

data = json.loads(result.stdout)

if data['new_releases_found'] > 0:
    webhook_url = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    
    for release in data['releases']:
        message = {
            'text': f"New release: {release['repository']} {release['tag_name']}",
            'attachments': [{
                'color': 'good',
                'fields': [
                    {'title': 'Repository', 'value': release['repository'], 'short': True},
                    {'title': 'Version', 'value': release['tag_name'], 'short': True},
                    {'title': 'Published', 'value': release['published_at'], 'short': True},
                    {'title': 'URL', 'value': release['html_url'], 'short': False}
                ]
            }]
        }
        requests.post(webhook_url, json=message)
```

### 6. Microsoft Teams Notification Integration

```python
# notify-teams.py
import json
import requests
import subprocess

# Run the monitor
result = subprocess.run([
    'python3', 'github_monitor.py',
    '--config', 'config.yaml',
    '--format', 'json'
], capture_output=True, text=True)

data = json.loads(result.stdout)

if data['new_releases_found'] > 0:
    # Microsoft Teams webhook URL (create via Workflows app)
    webhook_url = 'https://your-tenant.webhook.office.com/webhookb2/...'
    
    # Create adaptive card for Teams
    for release in data['releases']:
        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": f"New Release: {release['repository']}",
                                "size": "Large",
                                "weight": "Bolder",
                                "color": "Accent"
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {
                                        "title": "Version:",
                                        "value": release['tag_name']
                                    },
                                    {
                                        "title": "Repository:",
                                        "value": release['repository']
                                    },
                                    {
                                        "title": "Published:",
                                        "value": release['published_at']
                                    }
                                ]
                            }
                        ],
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "View Release",
                                "url": release['html_url']
                            }
                        ]
                    }
                }
            ]
        }
        
        response = requests.post(webhook_url, json=card)
        if response.status_code != 200:
            print(f"Failed to send Teams notification: {response.status_code}")
```

**Setting up Teams Webhook:**

1. In Microsoft Teams, go to your channel
2. Click "..." → "Workflows" (or "Connectors" for legacy)
3. Search for "When a Teams webhook request is received"
4. Configure the workflow and copy the webhook URL
5. Use the URL in your script

**Note:** Microsoft is transitioning from Connectors to Power Automate Workflows. Use Workflows for new integrations.

## Concourse Pipeline Examples

### 7. Basic Concourse Resource

```yaml
resource_types:
- name: github-release-monitor
  type: docker-image
  source:
    repository: your-registry/github-release-monitor

resources:
- name: release-monitor
  type: github-release-monitor
  source:
    github_token: ((github_token))
    config: |
      repositories:
        - owner: kubernetes
          repo: kubernetes
          description: "K8s releases"
      settings:
        max_releases_per_repo: 1

jobs:
- name: check-releases
  plan:
  - get: release-monitor
    trigger: true
  - task: process-releases
    config:
      platform: linux
      image_resource:
        type: docker-image
        source: {repository: busybox}
      inputs:
      - name: release-monitor
      run:
        path: sh
        args:
        - -exc
        - |
          cat release-monitor/releases.json
          # Process new releases here
```

### 8. Multi-Stage Pipeline

```yaml
jobs:
- name: monitor-releases
  plan:
  - task: check-github-releases
    config:
      platform: linux
      image_resource:
        type: docker-image
        source: 
          repository: python
          tag: 3.9-slim
      params:
        GITHUB_TOKEN: ((github_token))
      run:
        path: bash
        args:
        - -c
        - |
          pip install requests pyyaml
          python3 github_monitor.py --config config.yaml --output releases.json
          
  - task: parse-releases
    config:
      platform: linux
      image_resource:
        type: docker-image
        source: {repository: busybox}
      run:
        path: sh
        args:
        - -c
        - |
          # Parse and process releases
          if [ -s releases.json ]; then
            echo "New releases found!"
            # Trigger downstream jobs
          fi
```

## Integration Patterns

### 9. Dependency Update Automation

```yaml
# Monitor your dependencies and create PRs automatically
repositories:
  - owner: golang
    repo: go
    description: "Go programming language"
  
  - owner: nodejs
    repo: node
    description: "Node.js runtime"
  
  - owner: python
    repo: cpython
    description: "Python interpreter"

settings:
  max_releases_per_repo: 1  # Only latest
  include_prereleases: false
```

Use with a script to automatically create PRs when new versions are available.

### 10. Security Monitoring

```yaml
# Monitor security tools for updates
repositories:
  - owner: aquasecurity
    repo: trivy
    description: "Security scanner"
  
  - owner: anchore
    repo: grype
    description: "Vulnerability scanner"
  
  - owner: goodwithtech
    repo: dockle
    description: "Container linter"
```

## Tips

1. **Start Small**: Begin with a few critical repositories
2. **Adjust Rate Limits**: Increase delay for large repository lists
3. **Use State Tracking**: Let the monitor track what it's already seen
4. **Automate Responses**: Build automation around the JSON/YAML output
5. **Monitor Your Dependencies**: Track the tools your project depends on
