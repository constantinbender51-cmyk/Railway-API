#!/usr/bin/env python3
"""
Script to fetch Railway deployment logs using the deploymentLogs query.
Uses only environment variables - no user input.
"""

import os
import requests
import sys
from datetime import datetime

RAILWAY_API_BASE = "https://backboard.railway.app/graphql/v2"
RAILWAY_TOKEN = os.environ.get("RAILWAY_API_TOKEN")
PROJECT_ID = os.environ.get("PROJECT_ID")
DEPLOYMENT_ID = os.environ.get("DEPLOYMENT_ID")  # Optional: specific deployment ID

if not RAILWAY_TOKEN or not PROJECT_ID:
    print("Error: RAILWAY_API_TOKEN and PROJECT_ID environment variables are required")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {RAILWAY_TOKEN}",
    "Content-Type": "application/json",
}

def get_deployments(limit=10):
    """Get deployments to find the latest deployment ID"""
    query = """
    query GetDeployments($projectId: String!, $limit: Int!) {
        deployments(input: {projectId: $projectId}, first: $limit) {
            edges {
                node {
                    id
                    status
                    createdAt
                }
            }
        }
    }
    """
    
    variables = {
        "projectId": PROJECT_ID,
        "limit": limit
    }
    
    try:
        response = requests.post(
            RAILWAY_API_BASE,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if "errors" not in result:
                deployments = result.get("data", {}).get("deployments", {}).get("edges", [])
                return [deployment["node"] for deployment in deployments]
        
        print(f"Error getting deployments: {response.status_code}")
        return []
        
    except Exception as e:
        print(f"Request failed: {e}")
        return []

def get_deployment_logs(deployment_id, limit=500):
    """Get logs for a specific deployment"""
    query = """
    query deploymentLogs($deploymentId: String!, $limit: Int) {
      deploymentLogs(
        deploymentId: $deploymentId
        limit: $limit
      ) {
        __typename
        message
        severity
        timestamp
      }
    }
    """
    
    variables = {
        "deploymentId": deployment_id,
        "limit": limit
    }
    
    try:
        response = requests.post(
            RAILWAY_API_BASE,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if "errors" in result:
                print(f"GraphQL errors: {result['errors']}")
                return []
            
            logs = result.get("data", {}).get("deploymentLogs", [])
            return logs
        else:
            print(f"Error response: {response.text}")
            return []
            
    except Exception as e:
        print(f"Logs request failed: {e}")
        return []

def format_timestamp(timestamp):
    """Format ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp

def format_severity(severity):
    """Format severity with emoji"""
    if not severity:
        return "⚪ UNKNOWN"
    
    severity = severity.lower()
    if severity in ['error', 'err']:
        return "🔴 ERROR"
    elif severity in ['warning', 'warn']:
        return "🟡 WARN" 
    elif severity == 'info':
        return "🔵 INFO"
    elif severity == 'debug':
        return "⚪ DEBUG"
    else:
        return f"⚪ {severity.upper()}"

def main():
    print("🚄 Railway Deployment Logs")
    print("=" * 60)
    print(f"Project ID: {PROJECT_ID}")
    
    # Use specific deployment ID if provided, otherwise get latest
    if DEPLOYMENT_ID:
        print(f"Using specified deployment: {DEPLOYMENT_ID}")
        deployment_id = DEPLOYMENT_ID
        deployment_status = "SPECIFIED"
    else:
        print("Getting latest deployment...")
        deployments = get_deployments(limit=1)
        
        if not deployments:
            print("❌ No deployments found")
            return
        
        latest_deployment = deployments[0]
        deployment_id = latest_deployment['id']
        deployment_status = latest_deployment.get('status', 'UNKNOWN')
        print(f"Using latest deployment: {deployment_id}")
        print(f"Deployment status: {deployment_status}")
    
    print("=" * 60)
    
    # Get deployment logs
    print(f"\n📜 Fetching deployment logs...")
    logs = get_deployment_logs(deployment_id, limit=500)
    
    if not logs:
        print("❌ No logs found for this deployment")
        return
    
    print(f"✅ Found {len(logs)} log entries")
    print("=" * 80)
    
    # Display logs in chronological order
    sorted_logs = sorted(logs, key=lambda x: x.get('timestamp', ''))
    
    for log in sorted_logs:
        timestamp = format_timestamp(log.get('timestamp', 'Unknown'))
        severity = format_severity(log.get('severity', 'info'))
        message = log.get('message', '').strip()
        
        print(f"{timestamp} [{severity}] {message}")

if __name__ == "__main__":
    main()
