#!/usr/bin/env python3
"""
Simple script to fetch latest Railway deployment logs.
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

# Get deployment logs
logs_query = """
{
  deploymentLogs(deploymentId: "%s", limit: 500) {
    message
    severity
    timestamp
  }
}
""" % deployment_id

response = requests.post(RAILWAY_API, json={"query": logs_query}, headers=headers)
logs = response.json()["data"]["deploymentLogs"]

# Print logs
for log in sorted(logs, key=lambda x: x["timestamp"]):
    print(f"{log['timestamp']} [{log['severity']}] {log['message']}")
