#!/usr/bin/env python3
"""
Script to sweep all possible Railway deployment GraphQL queries and report success.
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

class RailwayQuerySweeper:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self.results = []

    def test_query(self, name: str, query: str, variables: dict = None) -> dict:
        """Test a single GraphQL query and return results"""
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
            
            result = {
                "name": name,
                "status_code": response.status_code,
                "success": False,
                "data_present": False,
                "errors": [],
                "response_time": None
            }
            
            if response.status_code == 200:
                json_response = response.json()
                result["success"] = True
                
                if "errors" in json_response:
                    result["errors"] = json_response["errors"]
                
                if "data" in json_response and json_response["data"]:
                    result["data_present"] = True
                    # Store a sample of the data (first few items)
                    result["data_sample"] = self._sample_data(json_response["data"])
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {
                "name": name,
                "status_code": None,
                "success": False,
                "data_present": False,
                "errors": [str(e)],
                "response_time": None
            }

    def _sample_data(self, data: dict, max_items: int = 3) -> dict:
        """Create a sample of the data for display"""
        sample = {}
        for key, value in data.items():
            if isinstance(value, list):
                sample[key] = value[:max_items]
            elif isinstance(value, dict):
                sample[key] = self._sample_data(value, max_items)
            else:
                sample[key] = value
        return sample

    def run_sweep(self):
        """Run all deployment-related queries"""
        queries = [
            # Basic deployment queries
            {
                "name": "Get deployments list",
                "query": """
                query GetDeployments($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 5) {
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
                "variables": {"projectId": PROJECT_ID}
            },
            {
                "name": "Get deployments with all fields",
                "query": """
                query GetDeploymentsFull($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 2) {
                        edges {
                            node {
                                id
                                status
                                createdAt
                                updatedAt
                                meta
                                environment {
                                    id
                                    name
                                }
                                project {
                                    id
                                    name
                                }
                                staticUrl
                                url
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Single deployment queries
            {
                "name": "Get single deployment by ID",
                "query": """
                query GetDeployment($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 1) {
                        edges {
                            node {
                                id
                                status
                                createdAt
                                buildLogs {
                                    timestamp
                                    message
                                    level
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Build logs queries
            {
                "name": "Get deployment with buildLogs",
                "query": """
                query GetDeploymentWithBuildLogs($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 1) {
                        edges {
                            node {
                                id
                                buildLogs {
                                    timestamp
                                    message
                                    level
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            {
                "name": "Get deployment build object",
                "query": """
                query GetDeploymentBuild($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 1) {
                        edges {
                            node {
                                id
                                build {
                                    id
                                    status
                                    logs {
                                        timestamp
                                        message
                                        level
                                    }
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Logs queries (various types)
            {
                "name": "Get deployment logs",
                "query": """
                query GetDeploymentLogs($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 1) {
                        edges {
                            node {
                                id
                                deploymentsLogs {
                                    timestamp
                                    message
                                    level
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            {
                "name": "Get deployment with all log types",
                "query": """
                query GetAllLogs($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 1) {
                        edges {
                            node {
                                id
                                buildLogs {
                                    timestamp
                                    message
                                    level
                                }
                                deploymentsLogs {
                                    timestamp
                                    message
                                    level
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Project-based queries
            {
                "name": "Get project with deployments",
                "query": """
                query GetProjectWithDeployments($projectId: ID!) {
                    project(id: $projectId) {
                        id
                        name
                        deployments(first: 3) {
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
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Service-based queries
            {
                "name": "Get services with deployments",
                "query": """
                query GetServices($projectId: String!) {
                    services(projectId: $projectId) {
                        id
                        name
                        deployments(first: 2) {
                            edges {
                                node {
                                    id
                                    status
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Direct deployment by ID (need to get an ID first)
            {
                "name": "Get deployment by direct ID query",
                "query": """
                query GetDeploymentDirect($projectId: String!) {
                    deployments(input: {projectId: $projectId}, first: 1) {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Environment queries
            {
                "name": "Get environments with deployments",
                "query": """
                query GetEnvironments($projectId: String!) {
                    environments(projectId: $projectId) {
                        id
                        name
                        deployments(first: 2) {
                            edges {
                                node {
                                    id
                                    status
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Build-related queries
            {
                "name": "Get builds directly",
                "query": """
                query GetBuilds($projectId: String!) {
                    builds(projectId: $projectId, first: 3) {
                        edges {
                            node {
                                id
                                status
                                deployment {
                                    id
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            },
            # Railway specific queries
            {
                "name": "Get railway deployment status",
                "query": """
                query GetRailwayDeployment($projectId: String!) {
                    railwayDeployment(projectId: $projectId) {
                        id
                        status
                        logs {
                            timestamp
                            message
                        }
                    }
                }
                """,
                "variables": {"projectId": PROJECT_ID}
            }
        ]

        print(f"Running query sweep for project: {PROJECT_ID}")
        print("=" * 80)
        
        successful_queries = 0
        total_queries = len(queries)
        
        for i, query_def in enumerate(queries):
            print(f"Testing {i+1}/{total_queries}: {query_def['name']}...")
            result = self.test_query(query_def['name'], query_def['query'], query_def.get('variables'))
            self.results.append(result)
            
            if result['success'] and result['data_present']:
                print(f"  SUCCESS - Found data")
                successful_queries += 1
            elif result['success']:
                print(f"  SUCCESS - But no data returned")
            else:
                print(f"  FAILED - Status: {result['status_code']}, Errors: {len(result['errors'])}")
        
        print("\n" + "=" * 80)
        print(f"SWEEP COMPLETE: {successful_queries}/{total_queries} queries successful")
        print("=" * 80)

    def print_detailed_results(self):
        """Print detailed results of the sweep"""
        print("\nDETAILED RESULTS:")
        print("=" * 80)
        
        for result in self.results:
            print(f"\nQUERY: {result['name']}")
            print(f"  Status: {'SUCCESS' if result['success'] else 'FAILED'}")
            print(f"  HTTP Status: {result['status_code']}")
            print(f"  Data Present: {'Yes' if result['data_present'] else 'No'}")
            
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
                for error in result['errors'][:2]:  # Show first 2 errors
                    if isinstance(error, dict):
                        print(f"    - {error.get('message', 'Unknown error')}")
                    else:
                        print(f"    - {error}")
            
            if result.get('data_sample'):
                print(f"  Data Sample:")
                sample_str = json.dumps(result['data_sample'], indent=2)
                # Limit sample output
                lines = sample_str.split('\n')
                for line in lines[:10]:  # Show first 10 lines
                    print(f"    {line}")
                if len(lines) > 10:
                    print(f"    ... (truncated)")

    def print_working_queries(self):
        """Print only the successful queries"""
        print("\nWORKING QUERIES:")
        print("=" * 80)
        
        working = [r for r in self.results if r['success'] and r['data_present']]
        
        for result in working:
            print(f"\nQUERY: {result['name']}")
            if result.get('data_sample'):
                # Show what data is available
                data_keys = list(result['data_sample'].keys())
                print(f"  Available data: {', '.join(data_keys)}")

def main():
    sweeper = RailwayQuerySweeper(RAILWAY_TOKEN)
    sweeper.run_sweep()
    sweeper.print_detailed_results()
    sweeper.print_working_queries()

if __name__ == "__main__":
    main()
