#!/usr/bin/env python3
"""
Script to fetch deployment logs using Railway REST API.
"""

import os
import requests
import sys

# Configuration
RAILWAY_REST_BASE = "https://api.railway.app"
RAILWAY_TOKEN = os.environ.get("RAILWAY_API_TOKEN")
PROJECT_ID = os.environ.get("PROJECT_ID")

if not RAILWAY_TOKEN:
    print("Error: RAILWAY_API_TOKEN environment variable is not set")
    sys.exit(1)

if not PROJECT_ID:
    print("Error: PROJECT_ID environment variable is not set")
    sys.exit(1)

class RailwayRestClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def get_deployments(self):
        """Get deployments for a project using REST API"""
        url = f"{RAILWAY_REST_BASE}/v1/projects/{PROJECT_ID}/deployments"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            print(f"GET {url} - Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

    def get_deployment_logs(self, deployment_id: str):
        """Get logs for a specific deployment using REST API"""
        # Try different REST endpoints for logs
        endpoints = [
            f"/v1/deployments/{deployment_id}/logs",
            f"/v1/deployments/{deployment_id}/build-logs",
            f"/v1/projects/{PROJECT_ID}/deployments/{deployment_id}/logs",
            f"/v1/projects/{PROJECT_ID}/deployments/{deployment_id}/build-logs",
        ]
        
        for endpoint in endpoints:
            url = f"{RAILWAY_REST_BASE}{endpoint}"
            print(f"Trying endpoint: {endpoint}")
            
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                print(f"GET {url} - Status: {response.status_code}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code != 404:
                    print(f"Error {response.status_code}: {response.text}")
                    
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")
                
        return None

    def get_project_info(self):
        """Get project information"""
        url = f"{RAILWAY_REST_BASE}/v1/projects/{PROJECT_ID}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            print(f"GET {url} - Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

def main():
    client = RailwayRestClient(RAILWAY_TOKEN)
    
    print(f"Testing Railway REST API for project: {PROJECT_ID}")
    print("=" * 70)
    
    # First, get project info to verify access
    print("\n1. Getting project information...")
    project_info = client.get_project_info()
    if project_info:
        print(f"Project Name: {project_info.get('name', 'Unknown')}")
        print(f"Project Description: {project_info.get('description', 'None')}")
    else:
        print("Failed to get project info")
        return
    
    # Get deployments
    print("\n2. Getting deployments...")
    deployments = client.get_deployments()
    
    if not deployments:
        print("No deployments found or failed to fetch deployments")
        return
    
    print(f"Found {len(deployments)} deployments")
    
    # Show deployment list
    print("\nDeployments:")
    print("-" * 50)
    for i, deployment in enumerate(deployments[:5]):  # Show first 5
        deployment_id = deployment.get('id', 'Unknown')
        status = deployment.get('status', 'Unknown')
        created_at = deployment.get('createdAt', 'Unknown')
        
        print(f"{i + 1}. ID: {deployment_id}")
        print(f"   Status: {status}")
        print(f"   Created: {created_at}")
    
    # Try to get logs for the latest deployment
    if deployments:
        latest_deployment = deployments[0]
        deployment_id = latest_deployment.get('id')
        
        print(f"\n3. Trying to get logs for latest deployment: {deployment_id}")
        logs = client.get_deployment_logs(deployment_id)
        
        if logs:
            print(f"\nSuccessfully retrieved logs!")
            print("Logs structure:")
            print(f"Type: {type(logs)}")
            if isinstance(logs, dict):
                print("Keys:", list(logs.keys()))
                # Print the actual logs if they're in a readable format
                if 'logs' in logs:
                    print("\nLogs content:")
                    if isinstance(logs['logs'], list):
                        for log_entry in logs['logs'][:10]:  # Show first 10 entries
                            print(f"  {log_entry}")
                    else:
                        print(logs['logs'])
                elif 'buildLogs' in logs:
                    print("\nBuild logs content:")
                    if isinstance(logs['buildLogs'], list):
                        for log_entry in logs['buildLogs'][:10]:
                            print(f"  {log_entry}")
                    else:
                        print(logs['buildLogs'])
            elif isinstance(logs, list):
                print(f"Number of log entries: {len(logs)}")
                for log_entry in logs[:10]:  # Show first 10 entries
                    print(f"  {log_entry}")
            else:
                print(f"Raw logs: {logs}")
        else:
            print("No logs available via REST API")

if __name__ == "__main__":
    main()
