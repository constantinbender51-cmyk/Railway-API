#!/usr/bin/env python3
"""
Script to retrieve and display deployment IDs for a Railway project.
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
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {}

    def get_all_deployments(self, project_id: str, limit: int = 20) -> list:
        """Get all deployments for a project"""
        query = """
        query GetDeployments($projectId: String!, $limit: Int!) {
            deployments(input: {projectId: $projectId}, first: $limit) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        environment {
                            name
                        }
                    }
                }
            }
        }
        """
        variables = {
            "projectId": project_id,
            "limit": limit
        }
        result = self.make_graphql_request(query, variables)
        if not result:
            return []
        
        deployments = result.get("data", {}).get("deployments", {}).get("edges", [])
        return [{
            "id": d["node"]["id"], 
            "status": d["node"]["status"], 
            "createdAt": d["node"]["createdAt"],
            "environment": d["node"]["environment"]["name"] if d["node"]["environment"] else "Unknown"
        } for d in deployments]

def main():
    monitor = RailwayDeploymentMonitor(RAILWAY_TOKEN)
    
    print(f"Fetching deployments for project: {PROJECT_ID}")
    
    deployments = monitor.get_all_deployments(PROJECT_ID)
    
    if not deployments:
        print("No deployments found for this project")
        return
    
    print(f"\nFound {len(deployments)} deployments:")
    print("=" * 80)
    
    for i, deployment in enumerate(deployments):
        print(f"{i + 1}. Deployment ID: {deployment['id']}")
        print(f"   Status: {deployment['status']}")
        print(f"   Environment: {deployment['environment']}")
        print(f"   Created: {deployment['createdAt']}")
        print()

if __name__ == "__main__":
    main()
