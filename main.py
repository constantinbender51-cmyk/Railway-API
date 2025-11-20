#!/usr/bin/env python3
"""
Script to monitor Railway deployment status and output logs once deployment is running.
"""

import os
import requests
import time
import sys
import json
import argparse
from typing import Optional, Dict, Any

# Configuration
RAILWAY_API_BASE = "https://backboard.railway.app/graphql/v2"
RAILWAY_TOKEN = os.environ.get("RAILWAY_API_TOKEN")

if not RAILWAY_TOKEN:
    print("Error: RAILWAY_API_TOKEN environment variable is not set")
    sys.exit(1)

class RailwayDeploymentMonitor:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def make_graphql_request(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
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

    def get_projects(self) -> list:
        """Get list of projects"""
        query = """
        query {
            projects {
                edges {
                    node {
                        id
                        name
                    }
                }
            }
        }
        """
        result = self.make_graphql_request(query)
        projects = result.get("data", {}).get("projects", {}).get("edges", [])
        return [{"id": p["node"]["id"], "name": p["node"]["name"]} for p in projects]

    def get_deployments(self, project_id: str, limit: int = 5) -> list:
        """Get recent deployments for a project"""
        query = """
        query GetDeployments($projectId: String!, $limit: Int!) {
            deployments(input: {projectId: $projectId}, first: $limit) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        meta
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
        deployments = result.get("data", {}).get("deployments", {}).get("edges", [])
        return [{"id": d["node"]["id"], "status": d["node"]["status"], "createdAt": d["node"]["createdAt"]} for d in deployments]

    def get_latest_deployment(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest deployment for a project"""
        deployments = self.get_deployments(project_id, limit=1)
        return deployments[0] if deployments else None

    def get_deployment_status(self, deployment_id: str) -> Optional[str]:
        """Get current status of a deployment"""
        query = """
        query GetDeploymentStatus($deploymentId: String!) {
            deployment(id: $deploymentId) {
                status
            }
        }
        """
        variables = {"deploymentId": deployment_id}
        result = self.make_graphql_request(query, variables)
        deployment = result.get("data", {}).get("deployment", {})
        return deployment.get("status") if deployment else None

    def get_deployment_logs(self, deployment_id: str) -> list:
        """Get logs for a deployment"""
        query = """
        query GetDeploymentLogs($deploymentId: String!) {
            deployment(id: $deploymentId) {
                deploymentsLogs {
                    timestamp
                    message
                    level
                }
            }
        }
        """
        variables = {"deploymentId": deployment_id}
        result = self.make_graphql_request(query, variables)
        deployment = result.get("data", {}).get("deployment", {})
        logs = deployment.get("deploymentsLogs", []) if deployment else []
        return sorted(logs, key=lambda x: x["timestamp"])

    def monitor_deployment(self, deployment_id: str, poll_interval: int = 5, timeout: int = 1800):
        """Monitor deployment status and output logs once running"""
        print(f"Monitoring deployment {deployment_id}...")
        
        start_time = time.time()
        last_log_timestamp = None
        
        while time.time() - start_time < timeout:
            status = self.get_deployment_status(deployment_id)
            
            if not status:
                print("Failed to get deployment status")
                time.sleep(poll_interval)
                continue
            
            print(f"Deployment status: {status}")
            
            if status in ["SUCCESS", "FAILED", "CANCELLED"]:
                print(f"Deployment completed with status: {status}")
                self.print_all_logs(deployment_id)
                return status
            
            elif status == "RUNNING":
                print("Deployment is running! Fetching logs...")
                self.stream_logs(deployment_id, last_log_timestamp)
                # Update last log timestamp to only get new logs next time
                logs = self.get_deployment_logs(deployment_id)
                if logs:
                    last_log_timestamp = logs[-1]["timestamp"]
            
            time.sleep(poll_interval)
        
        print("Monitoring timeout reached")
        return "TIMEOUT"

    def stream_logs(self, deployment_id: str, since_timestamp: str = None):
        """Stream deployment logs"""
        logs = self.get_deployment_logs(deployment_id)
        
        for log in logs:
            if since_timestamp and log["timestamp"] <= since_timestamp:
                continue
            
            timestamp = log["timestamp"]
            level = log.get("level", "INFO")
            message = log["message"]
            
            print(f"[{timestamp}] [{level}] {message}")

    def print_all_logs(self, deployment_id: str):
        """Print all deployment logs"""
        print("\n" + "="*50)
        print("FULL DEPLOYMENT LOGS")
        print("="*50)
        logs = self.get_deployment_logs(deployment_id)
        
        for log in logs:
            timestamp = log["timestamp"]
            level = log.get("level", "INFO")
            message = log["message"]
            print(f"[{timestamp}] [{level}] {message}")

def main():
    parser = argparse.ArgumentParser(description='Monitor Railway deployments')
    parser.add_argument('--project-id', help='Specific project ID to monitor')
    parser.add_argument('--project-name', help='Specific project name to monitor (partial match)')
    parser.add_argument('--deployment-id', help='Specific deployment ID to monitor')
    parser.add_argument('--poll-interval', type=int, default=5, help='Polling interval in seconds')
    parser.add_argument('--timeout', type=int, default=1800, help='Timeout in seconds')
    parser.add_argument('--auto-select', action='store_true', help='Automatically select the first project')
    parser.add_argument('--list-projects', action='store_true', help='List all projects and exit')
    
    args = parser.parse_args()
    
    monitor = RailwayDeploymentMonitor(RAILWAY_TOKEN)
    
    # List projects and exit if requested
    if args.list_projects:
        projects = monitor.get_projects()
        if not projects:
            print("No projects found or failed to fetch projects")
            return
        
        print("Available projects:")
        for i, project in enumerate(projects):
            print(f"{i + 1}. {project['name']} ({project['id']})")
        return
    
    # If deployment ID is provided, monitor that specific deployment
    if args.deployment_id:
        print(f"Monitoring specific deployment: {args.deployment_id}")
        final_status = monitor.monitor_deployment(
            args.deployment_id, 
            args.poll_interval, 
            args.timeout
        )
        print(f"Deployment monitoring completed. Final status: {final_status}")
        return
    
    # Get projects
    projects = monitor.get_projects()
    if not projects:
        print("No projects found or failed to fetch projects")
        return
    
    # If project ID is provided, monitor its latest deployment
    if args.project_id:
        deployment = monitor.get_latest_deployment(args.project_id)
        if not deployment:
            print("No deployments found for this project")
            return
        
        print(f"Monitoring latest deployment: {deployment['id']}")
        final_status = monitor.monitor_deployment(
            deployment["id"],
            args.poll_interval,
            args.timeout
        )
        print(f"Deployment monitoring completed. Final status: {final_status}")
        return
    
    # If project name is provided, find matching project
    if args.project_name:
        matching_projects = [p for p in projects if args.project_name.lower() in p['name'].lower()]
        if not matching_projects:
            print(f"No projects found matching: {args.project_name}")
            print("Available projects:")
            for i, project in enumerate(projects):
                print(f"{i + 1}. {project['name']} ({project['id']})")
            return
        
        if len(matching_projects) > 1:
            print(f"Multiple projects found matching '{args.project_name}':")
            for i, project in enumerate(matching_projects):
                print(f"{i + 1}. {project['name']} ({project['id']})")
            # Use the first matching project
            project = matching_projects[0]
            print(f"Using first matching project: {project['name']}")
        else:
            project = matching_projects[0]
        
        deployment = monitor.get_latest_deployment(project["id"])
        if not deployment:
            print("No deployments found for this project")
            return
        
        print(f"Monitoring deployment: {deployment['id']}")
        print(f"Current status: {deployment['status']}")
        
        final_status = monitor.monitor_deployment(
            deployment["id"],
            args.poll_interval,
            args.timeout
        )
        print(f"\nDeployment monitoring completed. Final status: {final_status}")
        return
    
    # Auto-select first project if requested
    if args.auto_select:
        project = projects[0]
        print(f"Auto-selected project: {project['name']}")
        
        deployment = monitor.get_latest_deployment(project["id"])
        if not deployment:
            print("No deployments found for this project")
            return
        
        print(f"Monitoring deployment: {deployment['id']}")
        print(f"Current status: {deployment['status']}")
        
        final_status = monitor.monitor_deployment(
            deployment["id"],
            args.poll_interval,
            args.timeout
        )
        print(f"\nDeployment monitoring completed. Final status: {final_status}")
        return
    
    # Default behavior: auto-select first project with a message
    print("No specific project specified. Auto-selecting first project.")
    print("Available projects:")
    for i, project in enumerate(projects):
        print(f"{i + 1}. {project['name']} ({project['id']})")
    
    project = projects[0]
    print(f"\nAuto-selected project: {project['name']}")
    
    deployment = monitor.get_latest_deployment(project["id"])
    if not deployment:
        print("No deployments found for this project")
        return
    
    print(f"Monitoring deployment: {deployment['id']}")
    print(f"Current status: {deployment['status']}")
    
    final_status = monitor.monitor_deployment(
        deployment["id"],
        args.poll_interval,
        args.timeout
    )
    
    print(f"\nDeployment monitoring completed. Final status: {final_status}")

if __name__ == "__main__":
    main()
