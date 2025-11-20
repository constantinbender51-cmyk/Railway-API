#!/usr/bin/env python3
"""
Script to retrieve and display build logs of the most recent Railway deployment.
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
                print(f"HTTP Error {response.status_code}")
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
        query = """
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
        """
        variables = {"projectId": project_id}
        result = self.make_graphql_request(query, variables)
        
        if not result:
            return None
            
        data = result.get("data", {})
        deployments = data.get("deployments", {}).get("edges", [])
        
        if not deployments:
            print("No deployments found")
            return None
            
        deployment = deployments[0]["node"]
        return {
            "id": deployment["id"], 
            "status": deployment["status"], 
            "createdAt": deployment["createdAt"]
        }

    def get_build_logs(self, deployment_id: str) -> list:
        """Get build logs for a deployment"""
        # Try different queries for build logs
        queries = [
            # Query for build logs
            """
            query GetBuildLogs($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    buildLogs {
                        timestamp
                        message
                        level
                    }
                }
            }
            """,
            # Alternative query
            """
            query GetBuildLogs($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    build {
                        logs {
                            timestamp
                            message
                            level
                        }
                    }
                }
            }
            """,
            # Another alternative
            """
            query GetBuildLogs($deploymentId: String!) {
                deployment(id: $deploymentId) {
                    buildLogs {
                        lines {
                            timestamp
                            message
                            level
                        }
                    }
                }
            }
            """
        ]
        
        for i, query in enumerate(queries):
            print(f"Trying build logs query variation {i + 1}...")
            variables = {"deploymentId": deployment_id}
            result = self.make_graphql_request(query, variables)
            
            if result and "errors" not in result:
                data = result.get("data", {})
                deployment = data.get("deployment", {})
                
                # Try direct buildLogs
                build_logs = deployment.get("buildLogs")
                if build_logs:
                    if isinstance(build_logs, list):
                        print(f"Found {len(build_logs)} build log entries")
                        return sorted(build_logs, key=lambda x: x["timestamp"])
                    elif isinstance(build_logs, dict) and "lines" in build_logs:
                        lines = build_logs.get("lines", [])
                        print(f"Found {len(lines)} build log entries")
                        return sorted(lines, key=lambda x: x["timestamp"])
                
                # Try build -> logs
                build = deployment.get("build", {})
                if build:
                    logs = build.get("logs", [])
                    if logs:
                        print(f"Found {len(logs)} build log entries")
                        return sorted(logs, key=lambda x: x["timestamp"])
        
        return []

def main():
    monitor = RailwayDeploymentMonitor(RAILWAY_TOKEN)
    
    print(f"Project ID: {PROJECT_ID}")
    print("Fetching latest deployment...")
    
    # Get the latest deployment
    deployment = monitor.get_latest_deployment(PROJECT_ID)
    
    if not deployment:
        print("Failed to get deployment")
        return
    
    print(f"Deployment ID: {deployment['id']}")
    print(f"Status: {deployment['status']}")
    print(f"Created: {deployment['createdAt']}")
    
    print("\nFetching build logs...")
    
    # Get and display the build logs
    build_logs = monitor.get_build_logs(deployment['id'])
    
    if not build_logs:
        print("No build logs available for this deployment")
        return
    
    print(f"Found {len(build_logs)} build log entries:")
    print("=" * 80)
    
    for log in build_logs:
        timestamp = log["timestamp"]
        level = log.get("level", "INFO")
        message = log["message"]
        print(f"[{timestamp}] [{level}] {message}")

if __name__ == "__main__":
    main()
