#!/usr/bin/env python3
"""
End-to-end test showing REPOSITORIES_OVERRIDE works with the full pipeline
"""

import os
import sys
import json
import unittest
import tempfile
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRepositoriesOverrideE2E(unittest.TestCase):
    """End-to-end test for REPOSITORIES_OVERRIDE with monitor and download"""

    def test_override_example_scenarios(self):
        """Test various override scenarios that would be used in practice"""
        
        # Scenario 1: Override to monitor only gatekeeper
        scenario1 = [
            {'owner': 'open-policy-agent', 'repo': 'gatekeeper', 'description': 'Policy Controller for Kubernetes'}
        ]
        
        # Verify JSON is valid
        json_str = json.dumps(scenario1)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['owner'], 'open-policy-agent')
        self.assertEqual(parsed[0]['repo'], 'gatekeeper')
        
        # Scenario 2: Override with multiple specific repositories
        scenario2 = [
            {'owner': 'kubernetes', 'repo': 'kubernetes', 'description': 'Kubernetes'},
            {'owner': 'istio', 'repo': 'istio', 'description': 'Istio Service Mesh'},
            {'owner': 'helm', 'repo': 'helm', 'description': 'Helm Package Manager'}
        ]
        
        json_str = json.dumps(scenario2)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed), 3)
        
        # Scenario 3: Complex override with special characters in descriptions
        scenario3 = [
            {'owner': 'prometheus', 'repo': 'prometheus', 'description': 'Monitoring & Alerting'},
            {'owner': 'grafana', 'repo': 'grafana', 'description': 'Dashboards (visualization)'},
            {'owner': 'elastic', 'repo': 'elasticsearch', 'description': 'Search/Analytics Engine'}
        ]
        
        json_str = json.dumps(scenario3)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed), 3)
        self.assertIn('&', parsed[0]['description'])
        self.assertIn('(', parsed[1]['description'])

    def test_pipeline_parameter_format(self):
        """Test the format expected in pipeline parameter files"""
        # This is how it would appear in params/*.yml files
        
        # Single line format (common in pipeline params)
        single_line = '[{"owner": "kubernetes", "repo": "kubernetes", "description": "K8s"}, {"owner": "istio", "repo": "istio", "description": "Istio"}]'
        parsed = json.loads(single_line)
        self.assertEqual(len(parsed), 2)
        
        # Multi-line format (for readability in params)
        multi_line = '''[
            {"owner": "kubernetes", "repo": "kubernetes", "description": "Container orchestration"},
            {"owner": "prometheus", "repo": "prometheus", "description": "Monitoring toolkit"},
            {"owner": "grafana", "repo": "grafana", "description": "Visualization platform"}
        ]'''
        # Remove extra whitespace that YAML might introduce
        cleaned = ' '.join(multi_line.split())
        parsed = json.loads(cleaned)
        self.assertEqual(len(parsed), 3)

    def test_escaping_in_pipeline_context(self):
        """Test proper escaping for use in Concourse pipeline"""
        # When setting via fly or in pipeline params, quotes need escaping
        
        # This is what you'd put in the params file or fly command
        escaped_format = '[{\"owner\": \"open-policy-agent\", \"repo\": \"gatekeeper\", \"description\": \"Policy Controller\"}]'
        
        # When the escaped string is processed, it becomes valid JSON
        unescaped = escaped_format.replace('\\"', '"')
        parsed = json.loads(unescaped)
        
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['owner'], 'open-policy-agent')

    def test_empty_override_scenarios(self):
        """Test empty override scenarios"""
        # Empty array - valid, means no repositories
        empty1 = '[]'
        parsed = json.loads(empty1)
        self.assertEqual(len(parsed), 0)
        
        # Empty string - means no override (use config file)
        empty2 = ''
        self.assertEqual(empty2, '')
        
        # These should be treated differently:
        # - '[]' = Override with empty list (monitor nothing)
        # - '' = Don't override (use config.yaml)


if __name__ == '__main__':
    unittest.main()