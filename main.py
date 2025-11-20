#!/usr/bin/env python3
"""
Script to retrieve and display logs of the most recent Railway deployment.
"""

import os
import requests
import sys

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
            response = requests.post(
                RAILWAY_API_BASE,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}: {response.text}")
                return {}
                
            result = response.json()
            
            if "errors" in result:
                print("GraphQL Errors:")
                for error in result["errors"]:
                    print(f"  - {error.get('message', 'Unknown error')}")
                return {}
                
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {}

    def get_latest_deployment(self, project_id: str) -> dict:
        """Get the latest deployment for a project"""
        # Try multiple query variations
        queries = [
            # Try the most common Railway GraphQL schema
            """
            query GetDeployments($projectId: String!) {
                deployments(input: {projectId: $projectId}, first: 1) {
                    edges {
                        node {
                            id
                            status
                            createdAt
                        }
                    }
                }
            }
            """,
            # Alternative query
            """
            query GetDeployments($projectId: String!) {
                project(id: $projectId) {
                    deployments(first: 1) {
                        edges {
                            node {
                                id
                                status
                                createdAt
                            }
                        }
                    }
                }
            }
            """
        ]
        
        for i, query in enumerate(queries):
            print(f"Trying query variation {i + 1}...")
            variables = {"projectId": project_id}
            result = self.make_graphql_request(query, variables)
            
            if result:
                # Parse first query format
                if "deployments" in result.get("data", {}):
                    deployments = result["data"]["deployments"]["edges"]
                    if deployments:
                        deployment = deployments[0]["node"]
                        return {
                            "id": deployment["id"], 
                            "status": deployment["status"], 
                            "createdAt": deployment["createdAt"]
                        }
                
                # Parse second query format  
                if "project" in result.get("data", {}):
                    deployments = result["data"]["project"]["deployments"]["edges"]
                    if deployments:
                        deployment = deployments[0]["node"]
                        return {
                            "id": deployment["id"], 
                            "status": deployment["status"], 
                            "createdAt": deployment["createdAt"]
                        }
        
        return None

    def get_deployment_logs(self, deployment_id: str) -> list:
        """Get logs for a deployment"""
        # Try multiple query variations for logs
        queries = [
            """
            query GetDeploymentLogs($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    deploymentsLogs {
                        timestamp
                        message
                        level
                    }
                }
            }
            """,
            """
            query GetDeploymentLogs($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    logs {
                        timestamp
                        message
                        level
                    }
                }
            }
            """
        ]
        
        for i, query in enumerate(queries):
            print(f"Trying logs query variation {i + 1}...")
            variables = {"deploymentId": deployment_id}
            result = self.make_graphql_request(query, variables)
            
            if result:
                deployment = result.get("data", {}).get("deployment", {})
                if deployment:
                    # Try different log field names
                    for field_name in ["deploymentsLogs", "logs"]:
                        logs = deployment.get(field_name, [])
                        if logs:
                            print(f"Retrieved {len(logs)} log entries using field '{field_name}'")
                            return sorted(logs, key=lambda x: x["timestamp"])
        
        return []

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
