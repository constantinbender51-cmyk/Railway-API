#!/usr/bin/env python3
"""
DeepSeek Coding Agent Script
Handles empty repositories and applies changes directly to GitHub
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
        self.is_empty_repo = False
        
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
        """Get the current repository structure and content - handles empty repos"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get repository info first
            repo_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}"
            repo_response = requests.get(repo_url, headers=headers)
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            
            default_branch = repo_data.get('default_branch', 'main')
            is_empty = repo_data.get('size', 0) == 0
            
            if is_empty:
                print("📭 Repository is empty (no commits yet)")
                self.is_empty_repo = True
                self.repo_content = "Empty repository - no files yet"
                self.current_files = {}
                return self.repo_content
            
            # Try to get repository contents using the contents API (works for non-empty repos)
            contents_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/"
            contents_response = requests.get(contents_url, headers=headers)
            
            files = {}
            
            if contents_response.status_code == 200:
                contents_data = contents_response.json()
                for item in contents_data:
                    if item['type'] == 'file':
                        file_path = item['path']
                        file_response = requests.get(item['url'], headers=headers)
                        if file_response.status_code == 200:
                            file_data = file_response.json()
                            if file_data.get('encoding') == 'base64':
                                content = base64.b64decode(file_data['content']).decode('utf-8')
                                files[file_path] = content
            
            self.current_files = files
            self.is_empty_repo = False
            
            structure_info = f"Files: {', '.join(files.keys()) if files else 'Repository exists but no accessible files'}"
            self.repo_content = structure_info
            return self.repo_content
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Could not fetch repository structure: {e}")
            self.repo_content = "Unable to fetch repository structure"
            self.current_files = {}
            return self.repo_content
    
    def call_deepseek_api(self, instruction: str) -> str:
        """Call DeepSeek API with the instruction"""
        try:
            headers = {
                'Authorization': f'Bearer {self.deepseek_api_key}',
                'Content-Type': 'application/json'
            }
            
            repo_context = "Empty repository - creating initial files" if self.is_empty_repo else self.repo_content
            
            prompt = f"""
            Current repository status: {repo_context}
            
            Instruction: {instruction}
            
            Respond with JSON instructions for file operations. Use the following format:
            
            For creating new files:
            {{"operation": "create", "file": "filename.ext", "content": "full file content"}}
            
            For updating existing files (complete replacement):
            {{"operation": "update", "file": "filename.ext", "content": "new full file content"}}
            
            For deleting files:
            {{"operation": "delete", "file": "filename.ext"}}
            
            Return a JSON array of operations. Example for empty repository:
            [
                {{"operation": "create", "file": "hello.py", "content": "print('Hello World!')"}},
                {{"operation": "create", "file": "README.md", "content": "# Hello World Project"}}
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
    
    def create_initial_commit(self, instructions: List[Dict[str, Any]]):
        """Create initial commit for empty repository"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Create blobs for each file
            blobs = {}
            for instruction in instructions:
                if instruction['operation'] in ['create', 'update']:
                    filename = instruction['file']
                    content = instruction['content']
                    
                    # Create blob
                    blob_payload = {
                        'content': content,
                        'encoding': 'utf-8'
                    }
                    blob_response = requests.post(
                        f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/blobs",
                        headers=headers,
                        json=blob_payload
                    )
                    blob_response.raise_for_status()
                    blobs[filename] = blob_response.json()['sha']
            
            # Create tree
            tree_entries = []
            for filename, blob_sha in blobs.items():
                tree_entries.append({
                    'path': filename,
                    'mode': '100644',
                    'type': 'blob',
                    'sha': blob_sha
                })
            
            tree_payload = {
                'tree': tree_entries
            }
            tree_response = requests.post(
                f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/trees",
                headers=headers,
                json=tree_payload
            )
            tree_response.raise_for_status()
            tree_sha = tree_response.json()['sha']
            
            # Get the default branch reference (might not exist for empty repo)
            default_branch = 'main'
            ref_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/refs/heads/{default_branch}"
            ref_response = requests.get(ref_url, headers=headers)
            
            parent_sha = None
            if ref_response.status_code == 200:
                # Branch exists, get the commit SHA
                parent_sha = ref_response.json()['object']['sha']
            
            # Create commit
            commit_payload = {
                'message': 'Initial commit: Hello World program by DeepSeek Coding Agent',
                'tree': tree_sha
            }
            if parent_sha:
                commit_payload['parents'] = [parent_sha]
            
            commit_response = requests.post(
                f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/commits",
                headers=headers,
                json=commit_payload
            )
            commit_response.raise_for_status()
            commit_sha = commit_response.json()['sha']
            
            # Create or update branch reference
            ref_payload = {
                'sha': commit_sha
            }
            
            if ref_response.status_code == 404:
                # Create new reference
                ref_response = requests.post(
                    f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/refs",
                    headers=headers,
                    json={'ref': f'refs/heads/{default_branch}', 'sha': commit_sha}
                )
            else:
                # Update existing reference
                ref_response = requests.patch(ref_url, headers=headers, json=ref_payload)
            
            ref_response.raise_for_status()
            
            applied_operations = [f"Created file: {filename}" for filename in blobs.keys()]
            applied_operations.append("✅ Successfully created initial commit on GitHub")
            return applied_operations
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to create initial commit: {e}")
    
    def apply_operations_to_github(self, instructions: List[Dict[str, Any]]):
        """Apply file operations directly to GitHub"""
        if self.is_empty_repo:
            print("🆕 Creating initial commit for empty repository...")
            return self.create_initial_commit(instructions)
        
        # Existing logic for non-empty repositories
        applied_operations = []
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        repo_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}"
        repo_response = requests.get(repo_url, headers=headers)
        repo_response.raise_for_status()
        default_branch = repo_response.json().get('default_branch', 'main')
        
        branch_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/branches/{default_branch}"
        branch_response = requests.get(branch_url, headers=headers)
        branch_response.raise_for_status()
        latest_commit_sha = branch_response.json()['commit']['sha']
        
        commit_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/commits/{latest_commit_sha}"
        commit_response = requests.get(commit_url, headers=headers)
        commit_response.raise_for_status()
        base_tree_sha = commit_response.json()['tree']['sha']
        
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
                    file_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
                    file_response = requests.get(file_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        tree_entries.append({
                            'path': filename,
                            'mode': '100644',
                            'type': 'blob',
                            'content': content,
                            'sha': file_data['sha']
                        })
                        applied_operations.append(f"Updated file: {filename}")
                    else:
                        tree_entries.append({
                            'path': filename,
                            'mode': '100644',
                            'type': 'blob',
                            'content': content
                        })
                        applied_operations.append(f"Created file (was missing): {filename}")
                        
                elif op_type == 'delete':
                    file_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
                    file_response = requests.get(file_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        tree_entries.append({
                            'path': filename,
                            'mode': '100644',
                            'type': 'blob',
                            'sha': None
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
        
        tree_url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/trees"
        tree_payload = {
            'base_tree': base_tree_sha,
            'tree': tree_entries
        }
        tree_response = requests.post(tree_url, headers=headers, json=tree_payload)
        tree_response.raise_for_status()
        new_tree_sha = tree_response.json()['sha']
        
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
        
        ref_payload = {
            'sha': new_commit_sha
        }
        ref_response = requests.patch(
            f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/git/refs/heads/{default_branch}",
