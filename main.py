#!/usr/bin/env python3
"""
Script to retrieve and display logs of the most recent Railway deployment.
"""

import os
import requests
import sys
import json

# Configuration
RAILWAY_API_BASE = "https://backboard.railway.app/graphql/v2"
RAILWAY_TOKEN = os.environ.get("RAILWAY_API_TOKEN")
PROJECT_ID = os.environ.get("PROJECT_ID")

if not RAILWAY_TOKEN:
    print("Error: RAILWAY_API_TOKEN environment variable is not set")
    sys.exit(1)

if not PROJECT_ID:
    print("Error: PROJECT_ID environment variable is not set")
    sys.exit(1)

class RailwayDeploymentMonitor:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def make_graphql_request(self, query: str, variables: dict = None) -> dict:
        """Make a GraphQL request to Railway API"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            print(f"Making GraphQL request to: {RAILWAY_API_BASE}")
            response = requests.post(
                RAILWAY_API_BASE,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error response: {response.text}")
                return {}
                
            result = response.json()
            
            # Check for GraphQL errors
            if "errors" in result:
                print("GraphQL errors found:")
                for error in result["errors"]:
                    print(f"  - {error}")
                return {}
                
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {}

    def get_latest_deployment(self, project_id: str) -> dict:
        """Get the latest deployment for a project"""
        query = """
        query GetDeployments($projectId: ID!) {
            deployments(projectId: $projectId, limit: 1) {
                nodes {
                    id
                    status
                    createdAt
                    environment {
                        name
                    }
                }
            }
        }
        """
        variables = {"projectId": project_id}
        result = self.make_graphql_request(query, variables)
        if not result:
            return None
        
        deployments = result.get("data", {}).get("deployments", {}).get("nodes", [])
        if not deployments:
            print("No deployments found in response")
            return None
            
        deployment = deployments[0]
        return {
            "id": deployment["id"], 
            "status": deployment["status"], 
            "createdAt": deployment["createdAt"],
            "environment": deployment["environment"]["name"] if deployment["environment"] else "Unknown"
        }

    def get_deployment_logs(self, deployment_id: str) -> list:
        """Get logs for a deployment"""
        query = """
        query GetDeploymentLogs($deploymentId: ID!) {
            deployment(id: $deploymentId) {
                logs {
                    timestamp
                    message
                    level
                }
            }
        }
        """
        variables = {"deploymentId": deployment_id}
        result = self.make_graphql_request(query, variables)
        if not result:
            return []
            
        deployment = result.get("data", {}).get("deployment", {})
        if not deployment:
            print("No deployment data found in response")
            return []
            
        logs = deployment.get("logs", [])
        print(f"Retrieved {len(logs)} log entries")
        return sorted(logs, key=lambda x: x["timestamp"])

def main():
    monitor = RailwayDeploymentMonitor(RAILWAY_TOKEN)
    
    print(f"Fetching latest deployment for project: {PROJECT_ID}")
    
    # Get the latest deployment
    deployment = monitor.get_latest_deployment(PROJECT_ID)
    
    if not deployment:
        print("No deployments found for this project")
        return
    
    print(f"\nLatest Deployment:")
    print(f"ID: {deployment['id']}")
    print(f"Status: {deployment['status']}")
    print(f"Environment: {deployment['environment']}")
    print(f"Created: {deployment['createdAt']}")
    
    print(f"\nFetching logs for deployment: {deployment['id']}")
    
    # Get and display the logs
    logs = monitor.get_deployment_logs(deployment['id'])
    
    if not logs:
        print("No logs available for this deployment")
        return
    
    print(f"\nFound {len(logs)} log entries:")
    print("=" * 80)
    
    for log in logs:
        timestamp = log["timestamp"]
        level = log.get("level", "INFO")
        message = log["message"]
        print(f"[{timestamp}] [{level}] {message}")

if __name__ == "__main__":
    main()
