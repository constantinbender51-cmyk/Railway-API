#!/usr/bin/env python3
"""
Simple script to fetch both deployment logs and build logs.
"""

import os
import requests

RAILWAY_API = "https://backboard.railway.app/graphql/v2"
TOKEN = os.environ["RAILWAY_API_TOKEN"]
PROJECT_ID = os.environ["PROJECT_ID"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# Get latest deployment
deployments_query = """
{
  deployments(input: {projectId: "%s"}, first: 1) {
    edges {
      node {
        id
        status
      }
    }
  }
}
""" % PROJECT_ID

response = requests.post(RAILWAY_API, json={"query": deployments_query}, headers=headers)
deployment_id = response.json()["data"]["deployments"]["edges"][0]["node"]["id"]
status = response.json()["data"]["deployments"]["edges"][0]["node"]["status"]

print(f"Deployment: {deployment_id} ({status})")

# Get deployment logs
deployment_logs_query = """
{
  deploymentLogs(deploymentId: "%s", limit: 500) {
    message
    severity
    timestamp
  }
}
""" % deployment_id

response = requests.post(RAILWAY_API, json={"query": deployment_logs_query}, headers=headers)
deployment_logs = response.json()["data"]["deploymentLogs"]

print(f"\n=== DEPLOYMENT LOGS ({len(deployment_logs)} entries) ===")
for log in sorted(deployment_logs, key=lambda x: x["timestamp"]):
    print(f"{log['timestamp']} [{log['severity']}] {log['message']}")

# Get build logs
build_logs_query = """
{
  buildLogs(deploymentId: "%s", limit: 500) {
    message
    severity
    timestamp
  }
}
""" % deployment_id

response = requests.post(RAILWAY_API, json={"query": build_logs_query}, headers=headers)
build_logs = response.json()["data"]["buildLogs"]

print(f"\n=== BUILD LOGS ({len(build_logs)} entries) ===")
for log in sorted(build_logs, key=lambda x: x["timestamp"]):
    print(f"{log['timestamp']} [{log['severity']}] {log['message']}")
