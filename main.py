#!/usr/bin/env python3
"""
DeepSeek Coding Agent Script
Applies changes directly to GitHub via API
"""

import os
import json
import requests
import base64
import socket
from typing import Dict, List, Any

# Configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GITHUB_API_URL = "https://api.github.com"
DEFAULT_INSTRUCTION = "write a hello world program"

class DeepSeekCodingAgent:
    def __init__(self):
        self.load_environment_variables()
        self.repo_content = ""
        self.current_files = {}
        
    def load_environment_variables(self):
        """Load required environment variables"""
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.deepseek_api_key, self.github_token, self.github_username, self.github_repo]):
            raise ValueError(
                "Missing required environment variables. Please set:\n"
                "- DEEPSEEK_API_KEY: Your DeepSeek API key\n"
                "- GITHUB_TOKEN: Your GitHub token\n"
                "- GITHUB_USERNAME: Your GitHub username\n"
                "- GITHUB_REPO: Target repository name\n"
            )
    
    def check_network_connectivity(self):
        """Check network connectivity to required services"""
        print("🔍 Checking network connectivity...")
        
        try:
            github_ip = socket.gethostbyname('api.github.com')
            deepseek_ip = socket.gethostbyname('api.deepseek.com')
            print(f"✅ DNS Resolution: api.github.com -> {github_ip}")
            print(f"✅ DNS Resolution: api.deepseek.com -> {deepseek_ip}")
        except socket.gaierror as e:
            raise Exception(f"DNS resolution failed: {e}")
        
        test_urls = {
            'GitHub API': GITHUB_API_URL,
            'DeepSeek API': DEEPSEEK_API_URL
        }
        
        for service, url in test_urls.items():
            try:
                response = requests.get(url, timeout=10)
                print(f"✅ {service} reachable (Status: {response.status_code})")
            except requests.exceptions.Timeout:
                raise Exception(f"❌ {service} timeout")
            except requests.exceptions.ConnectionError:
                raise Exception(f"❌ {service} connection failed")
            except Exception as e:
                print(f"⚠️  {service} check: {e}")
    
    def validate_github_token(self):
        """Validate the GitHub token"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(f"{GITHUB_API_URL}/user", headers=headers, timeout=10)
            response.raise_for_status()
            
            user_data = response.json()
            print(f"✅ GitHub token validated for user: {user_data.get('login', 'Unknown')}")
            
            repo_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}"
            repo_response = requests.get(repo_url, headers=headers, timeout=10)
            
            if repo_response.status_code == 404:
                raise Exception(f"Repository not found: {self.github_username}/{self.github_repo}")
            elif repo_response.status_code == 403:
                raise Exception("Token lacks permissions to access this repository")
            elif repo_response.status_code == 200:
                print(f"✅ Repository access confirmed: {self.github_username}/{self.github_repo}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"GitHub API validation failed: {e}")
    
    def get_repo_structure(self):
        """Get the current repository structure and content"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get default branch first
            repo_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}"
            repo_response = requests.get(repo_url, headers=headers)
            repo_response.raise_for_status()
            default_branch = repo_response.json().get('default_branch', 'main')
            
            # Get repository contents recursively
            contents_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/trees/{default_branch}?recursive=1"
            contents_response = requests.get(contents_url, headers=headers)
            contents_response.raise_for_status()
            
            tree_data = contents_response.json()
            files = {}
            
            for item in tree_data.get('tree', []):
                if item['type'] == 'blob':  # Only files
                    file_path = item['path']
                    
                    # Get file content
                    file_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{file_path}"
                    file_response = requests.get(file_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        if file_data.get('encoding') == 'base64':
                            content = base64.b64decode(file_data['content']).decode('utf-8')
                            files[file_path] = content
            
            self.current_files = files
            
            structure_info = f"Files: {', '.join(files.keys()) if files else 'Empty repository'}"
            self.repo_content = structure_info
            return self.repo_content
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch repository structure: {e}")
    
    def call_deepseek_api(self, instruction: str) -> str:
        """Call DeepSeek API with the instruction"""
        try:
            headers = {
                'Authorization': f'Bearer {self.deepseek_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""
            Current repository files: {list(self.current_files.keys())}
            
            Instruction: {instruction}
            
            Respond with JSON instructions for file operations. Use the following format:
            
            For creating new files:
            {{"operation": "create", "file": "filename.ext", "content": "full file content"}}
            
            For updating existing files (complete replacement):
            {{"operation": "update", "file": "filename.ext", "content": "new full file content"}}
            
            For deleting files:
            {{"operation": "delete", "file": "filename.ext"}}
            
            Return a JSON array of operations. Example:
            [
                {{"operation": "create", "file": "hello.py", "content": "print('Hello World!')"}},
                {{"operation": "update", "file": "README.md", "content": "# Updated Readme"}}
            ]
            
            Important: 
            - Only respond with valid JSON array, no additional text
            - For updates, provide the complete new file content
            - You can create, update, or delete multiple files
            """
            
            payload = {
                'model': 'deepseek-coder',
                'messages': [
                    {'role': 'system', 'content': 'You are a coding assistant that responds ONLY with valid JSON instructions for file operations. No additional text.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 4000
            }
            
            print("📡 Sending request to DeepSeek API...")
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            print("✅ DeepSeek API response received")
            return response.json()['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API call failed: {e}")
    
    def parse_instructions(self, response: str) -> List[Dict[str, Any]]:
        """Parse the JSON instructions from DeepSeek response"""
        try:
            cleaned_response = response.strip()
            if '```json' in cleaned_response:
                cleaned_response = cleaned_response.split('```json')[1].split('```')[0]
            elif '```' in cleaned_response:
                cleaned_response = cleaned_response.split('```')[1].split('```')[0]
            
            cleaned_response = cleaned_response.strip()
            
            instructions = json.loads(cleaned_response)
            
            if not isinstance(instructions, list):
                raise ValueError("Instructions should be a JSON array")
                
            for i, instruction in enumerate(instructions):
                if 'operation' not in instruction:
                    raise ValueError(f"Instruction {i} missing 'operation' field")
                if 'file' not in instruction:
                    raise ValueError(f"Instruction {i} missing 'file' field")
                if instruction['operation'] in ['create', 'update'] and 'content' not in instruction:
                    raise ValueError(f"Instruction {i} missing 'content' field for {instruction['operation']} operation")
                    
            return instructions
            
        except json.JSONDecodeError as e:
            print(f"Raw response that failed to parse: {response}")
            raise Exception(f"Failed to parse JSON instructions: {e}")
    
    def apply_operations_to_github(self, instructions: List[Dict[str, Any]]):
        """Apply file operations directly to GitHub"""
        applied_operations = []
        
        # Get the latest commit SHA and default branch
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        repo_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}"
        repo_response = requests.get(repo_url, headers=headers)
        repo_response.raise_for_status()
        default_branch = repo_response.json().get('default_branch', 'main')
        
        # Get the latest commit SHA
        branch_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/branches/{default_branch}"
        branch_response = requests.get(branch_url, headers=headers)
        branch_response.raise_for_status()
        latest_commit_sha = branch_response.json()['commit']['sha']
        
        # Get the current tree SHA
        commit_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/commits/{latest_commit_sha}"
        commit_response = requests.get(commit_url, headers=headers)
        commit_response.raise_for_status()
        base_tree_sha = commit_response.json()['tree']['sha']
        
        # Process each operation
        tree_entries = []
        
        for instruction in instructions:
            try:
                op_type = instruction['operation']
                filename = instruction['file']
                
                print(f"  Processing: {op_type} on {filename}")
                
                if op_type == 'create':
                    content = instruction['content']
                    tree_entries.append({
                        'path': filename,
                        'mode': '100644',
                        'type': 'blob',
                        'content': content
                    })
                    applied_operations.append(f"Created file: {filename}")
                    
                elif op_type == 'update':
                    content = instruction['content']
                    # First, get the current file SHA to update it
                    file_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
                    file_response = requests.get(file_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        tree_entries.append({
                            'path': filename,
                            'mode': '100644',
                            'type': 'blob',
                            'content': content,
                            'sha': file_data['sha']  # Include SHA for updates
                        })
                        applied_operations.append(f"Updated file: {filename}")
                    else:
                        # File doesn't exist, create it instead
                        tree_entries.append({
                            'path': filename,
                            'mode': '100644',
                            'type': 'blob',
                            'content': content
                        })
                        applied_operations.append(f"Created file (was missing): {filename}")
                        
                elif op_type == 'delete':
                    # For deletion, we need to get the file SHA first
                    file_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
                    file_response = requests.get(file_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        tree_entries.append({
                            'path': filename,
                            'mode': '100644',
                            'type': 'blob',
                            'sha': None  # Setting SHA to None deletes the file
                        })
                        applied_operations.append(f"Deleted file: {filename}")
                    else:
                        print(f"⚠️  File not found for deletion: {filename}")
                        
                else:
                    raise ValueError(f"Unknown operation: {op_type}")
                    
            except Exception as e:
                raise Exception(f"Failed to process operation {json.dumps(instruction)}: {e}")
        
        if not tree_entries:
            print("ℹ️  No changes to apply")
            return applied_operations
        
        # Create new tree
        tree_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/trees"
        tree_payload = {
            'base_tree': base_tree_sha,
            'tree': tree_entries
        }
        tree_response = requests.post(tree_url, headers=headers, json=tree_payload)
        tree_response.raise_for_status()
        new_tree_sha = tree_response.json()['sha']
        
        # Create new commit
        commit_payload = {
            'message': 'Auto-commit: Changes applied by DeepSeek Coding Agent',
            'tree': new_tree_sha,
            'parents': [latest_commit_sha]
        }
        commit_response = requests.post(
            f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/commits",
            headers=headers,
            json=commit_payload
        )
        commit_response.raise_for_status()
        new_commit_sha = commit_response.json()['sha']
        
        # Update branch reference
        ref_payload = {
            'sha': new_commit_sha
        }
        ref_response = requests.patch(
            f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/refs/heads/{default_branch}",
            headers=headers,
            json=ref_payload
        )
        ref_response.raise_for_status()
        
        applied_operations.append(f"✅ Successfully pushed {len([x for x in tree_entries if x.get('sha') is not None])} changes to GitHub")
        return applied_operations
    
    def run(self, instruction: str = None):
        """Main execution method"""
        try:
            print("🚀 Starting DeepSeek Coding Agent...")
            print("=" * 50)
            
            # Check network first
            self.check_network_connectivity()
            print("✅ Network connectivity confirmed")
            
            # Validate GitHub token
            self.validate_github_token()
            
            # Use default instruction if none provided
            if instruction is None:
                instruction = DEFAULT_INSTRUCTION
                print(f"📝 Using default instruction: '{instruction}'")
            else:
                print(f"📝 Using instruction: '{instruction}'")
            
            # Get repository structure
            print("📁 Fetching repository structure...")
            repo_structure = self.get_repo_structure()
            print(f"📊 Repository: {repo_structure}")
            
            # Call DeepSeek API
            print("🤖 Calling DeepSeek API...")
            deepseek_response = self.call_deepseek_api(instruction)
            
            print("📝 Parsing instructions...")
            instructions = self.parse_instructions(deepseek_response)
            print(f"📋 Parsed {len(instructions)} operation(s)")
            
            # Apply operations directly to GitHub
            print("⚡ Applying operations directly to GitHub...")
            applied_ops = self.apply_operations_to_github(instructions)
            
            print("📊 Operation Results:")
            for op in applied_ops:
                print(f"  {op}")
            
            print("🎉 All operations completed successfully!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

def main():
    """Main function"""
    import sys
    
    try:
        agent = DeepSeekCodingAgent()
        
        if len(sys.argv) > 1:
            instruction = ' '.join(sys.argv[1:])
            agent.run(instruction)
        else:
            agent.run()
            
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
