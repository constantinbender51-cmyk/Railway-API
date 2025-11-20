#!/usr/bin/env python3
"""
DeepSeek Coding Agent Script
Interacts with DeepSeek API to perform file operations and applies changes to GitHub repo
"""

import os
import json
import requests
import base64
from typing import Dict, List, Any

# Configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_INSTRUCTION = "write a hello world program"

class DeepSeekCodingAgent:
    def __init__(self):
        self.load_environment_variables()
        self.repo_content = ""
        
    def load_environment_variables(self):
        """Load required environment variables"""
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.github_api_key = os.getenv('GITHUB_API_KEY')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.deepseek_api_key, self.github_api_key, self.github_username, self.github_repo]):
            raise ValueError("Missing required environment variables. Please set: DEEPSEEK_API_KEY, GITHUB_API_KEY, GITHUB_USERNAME, GITHUB_REPO")
    
    def get_repo_structure(self):
        """Get the current repository structure and content"""
        try:
            headers = {
                'Authorization': f'token {self.github_api_key}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get repo contents
            url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/contents/"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            files = []
            for item in response.json():
                if item['type'] == 'file':
                    files.append(item['name'])
            
            self.repo_content = f"Repository structure: {', '.join(files) if files else 'Empty repository'}"
            return self.repo_content
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch repository structure: {str(e)}")
    
    def call_deepseek_api(self, instruction: str) -> str:
        """Call DeepSeek API with the instruction"""
        try:
            headers = {
                'Authorization': f'Bearer {self.deepseek_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""
            Current repository status: {self.repo_content}
            
            Instruction: {instruction}
            
            Respond with JSON instructions for file operations. Use the following format for operations:
            
            For creating files:
            {{"operation": "create", "file": "filename.ext", "content": "file content"}}
            
            For deleting files:
            {{"operation": "delete", "file": "filename.ext"}}
            
            For inserting code at specific line:
            {{"operation": "insert", "file": "filename.ext", "line": 5, "content": "code to insert"}}
            
            For deleting lines from specific line:
            {{"operation": "delete_lines", "file": "filename.ext", "line": 10, "content": "number_of_lines_to_delete"}}
            
            Return a JSON array of operations. Example:
            [
                {{"operation": "create", "file": "hello.py", "content": "print('Hello World!')"}}
            ]
            """
            
            payload = {
                'model': 'deepseek-coder',
                'messages': [
                    {'role': 'system', 'content': 'You are a coding assistant that responds with JSON instructions for file operations.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1
            }
            
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            return response.json()['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API call failed: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected response format from DeepSeek API: {str(e)}")
    
    def parse_instructions(self, response: str) -> List[Dict[str, Any]]:
        """Parse the JSON instructions from DeepSeek response"""
        try:
            # Extract JSON from response (handling cases where response might have extra text)
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found in response")
            
            json_str = response[start_idx:end_idx]
            instructions = json.loads(json_str)
            
            if not isinstance(instructions, list):
                raise ValueError("Instructions should be a JSON array")
                
            return instructions
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON instructions: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to parse instructions: {str(e)}")
    
    def apply_file_operations(self, instructions: List[Dict[str, Any]]):
        """Apply file operations locally"""
        applied_operations = []
        
        for instruction in instructions:
            try:
                op_type = instruction.get('operation')
                filename = instruction.get('file')
                
                if not op_type or not filename:
                    raise ValueError("Missing 'operation' or 'file' in instruction")
                
                if op_type == 'create':
                    content = instruction.get('content', '')
                    with open(filename, 'w') as f:
                        f.write(content)
                    applied_operations.append(f"Created file: {filename}")
                    
                elif op_type == 'delete':
                    if os.path.exists(filename):
                        os.remove(filename)
                        applied_operations.append(f"Deleted file: {filename}")
                    else:
                        raise ValueError(f"File not found: {filename}")
                        
                elif op_type == 'insert':
                    line_num = instruction.get('line')
                    content = instruction.get('content', '')
                    
                    if line_num is None:
                        raise ValueError("Missing 'line' for insert operation")
                    
                    if not os.path.exists(filename):
                        raise ValueError(f"File not found: {filename}")
                    
                    with open(filename, 'r') as f:
                        lines = f.readlines()
                    
                    # Insert at specific line (1-indexed)
                    if line_num < 1 or line_num > len(lines) + 1:
                        raise ValueError(f"Line number {line_num} out of range for file {filename}")
                    
                    lines.insert(line_num - 1, content + '\n')
                    
                    with open(filename, 'w') as f:
                        f.writelines(lines)
                    
                    applied_operations.append(f"Inserted content at line {line_num} in: {filename}")
                    
                elif op_type == 'delete_lines':
                    line_num = instruction.get('line')
                    lines_to_delete = instruction.get('content', 1)
                    
                    if line_num is None:
                        raise ValueError("Missing 'line' for delete_lines operation")
                    
                    if not os.path.exists(filename):
                        raise ValueError(f"File not found: {filename}")
                    
                    with open(filename, 'r') as f:
                        lines = f.readlines()
                    
                    if line_num < 1 or line_num > len(lines):
                        raise ValueError(f"Line number {line_num} out of range for file {filename}")
                    
                    # Delete lines starting from line_num
                    del lines[line_num - 1:line_num - 1 + int(lines_to_delete)]
                    
                    with open(filename, 'w') as f:
                        f.writelines(lines)
                    
                    applied_operations.append(f"Deleted {lines_to_delete} lines starting from line {line_num} in: {filename}")
                    
                else:
                    raise ValueError(f"Unknown operation: {op_type}")
                    
            except Exception as e:
                raise Exception(f"Failed to apply operation {instruction}: {str(e)}")
        
        return applied_operations
    
    def commit_and_push_to_github(self):
        """Commit and push changes to GitHub"""
        try:
            headers = {
                'Authorization': f'token {self.github_api_key}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get the latest commit SHA
            commits_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/commits"
            commits_response = requests.get(commits_url, headers=headers)
            commits_response.raise_for_status()
            latest_commit_sha = commits_response.json()[0]['sha']
            
            # Get the tree SHA
            commit_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/commits/{latest_commit_sha}"
            commit_response = requests.get(commit_url, headers=headers)
            commit_response.raise_for_status()
            tree_sha = commit_response.json()['tree']['sha']
            
            # Create new tree with all files
            tree_data = []
            for root, dirs, files in os.walk('.'):
                for file in files:
                    if file.startswith('.') or file == os.path.basename(__file__):
                        continue
                    
                    filepath = os.path.join(root, file)
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    
                    tree_data.append({
                        'path': filepath[2:],  # Remove './' prefix
                        'mode': '100644',
                        'type': 'blob',
                        'content': content.decode('utf-8')
                    })
            
            create_tree_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/trees"
            tree_payload = {
                'base_tree': tree_sha,
                'tree': tree_data
            }
            tree_response = requests.post(create_tree_url, headers=headers, json=tree_payload)
            tree_response.raise_for_status()
            new_tree_sha = tree_response.json()['sha']
            
            # Create commit
            commit_payload = {
                'message': 'Auto-commit: Changes by DeepSeek Coding Agent',
                'tree': new_tree_sha,
                'parents': [latest_commit_sha]
            }
            commit_response = requests.post(
                f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/commits",
                headers=headers,
                json=commit_payload
            )
            commit_response.raise_for_status()
            new_commit_sha = commit_response.json()['sha']
            
            # Update reference
            ref_payload = {
                'sha': new_commit_sha
            }
            ref_response = requests.patch(
                f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/refs/heads/main",
                headers=headers,
                json=ref_payload
            )
            ref_response.raise_for_status()
            
            return "Successfully committed and pushed changes to GitHub"
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"GitHub API operation failed: {str(e)}")
    
    def run(self, instruction: str = None):
        """Main execution method"""
        try:
            print("🚀 Starting DeepSeek Coding Agent...")
            
            # Use default instruction if none provided
            if instruction is None:
                instruction = DEFAULT_INSTRUCTION
                print(f"Using default instruction: {instruction}")
            
            # Get current repo structure
            print("📁 Fetching repository structure...")
            repo_structure = self.get_repo_structure()
            print(f"Repository structure: {repo_structure}")
            
            # Call DeepSeek API
            print("🤖 Calling DeepSeek API...")
            deepseek_response = self.call_deepseek_api(instruction)
            print("DeepSeek response received")
            
            # Parse instructions
            print("📝 Parsing instructions...")
            instructions = self.parse_instructions(deepseek_response)
            print(f"Parsed {len(instructions)} operation(s)")
            
            # Apply file operations
            print("⚡ Applying file operations...")
            applied_ops = self.apply_file_operations(instructions)
            for op in applied_ops:
                print(f"  ✅ {op}")
            
            # Commit and push to GitHub
            print("📤 Pushing changes to GitHub...")
            push_result = self.commit_and_push_to_github()
            print(f"  ✅ {push_result}")
            
            print("🎉 All operations completed successfully!")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise

def main():
    """Main function with optional custom instruction"""
    import sys
    
    agent = DeepSeekCodingAgent()
    
    # Use command line argument as instruction if provided
    if len(sys.argv) > 1:
        instruction = ' '.join(sys.argv[1:])
        print(f"Using custom instruction: {instruction}")
        agent.run(instruction)
    else:
        agent.run()

if __name__ == "__main__":
    main()
