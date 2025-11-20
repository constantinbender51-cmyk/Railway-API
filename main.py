#!/usr/bin/env python3
"""
DeepSeek Coding Agent Script
Interacts with DeepSeek API to perform file operations and applies changes to GitHub repo
Uses fine-grained GitHub tokens for enhanced security
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
        self.github_token = os.getenv('GITHUB_TOKEN')  # Fine-grained token
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.deepseek_api_key, self.github_token, self.github_username, self.github_repo]):
            raise ValueError(
                "Missing required environment variables. Please set:\n"
                "- DEEPSEEK_API_KEY: Your DeepSeek API key\n"
                "- GITHUB_TOKEN: Your fine-grained GitHub token\n"
                "- GITHUB_USERNAME: Your GitHub username\n"
                "- GITHUB_REPO: Target repository name\n"
            )
    
    def validate_github_token(self):
        """Validate the fine-grained GitHub token has required permissions"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Test token access to the repository
            url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Check token permissions (for fine-grained tokens)
            user_url = "https://api.github.com/user"
            user_response = requests.get(user_url, headers=headers)
            
            print("✅ GitHub token validated successfully")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise Exception(
                    "GitHub token lacks required permissions. "
                    "Please ensure your fine-grained token has:\n"
                    "- Repository permissions: Contents (Read and Write)\n"
                    "- Repository permissions: Metadata (Read)\n"
                    "- Access to the specific repository\n"
                    f"- Repository: {self.github_username}/{self.github_repo}"
                )
            elif e.response.status_code == 404:
                raise Exception(f"Repository not found: {self.github_username}/{self.github_repo}")
            else:
                raise Exception(f"GitHub API error: {str(e)}")
    
    def get_repo_structure(self):
        """Get the current repository structure and content"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get repo contents recursively
            url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/trees/main?recursive=1"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 404:
                # Try master branch if main doesn't exist
                url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/trees/master?recursive=1"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
            
            response.raise_for_status()
            
            tree_data = response.json()
            files = []
            for item in tree_data.get('tree', []):
                if item['type'] == 'blob':  # Only files, not directories
                    files.append(item['path'])
            
            # Get file contents for key files
            file_contents = {}
            for file_path in files[:10]:  # Limit to first 10 files to avoid too many API calls
                if any(file_path.endswith(ext) for ext in ['.py', '.js', '.java', '.cpp', '.c', '.html', '.css', '.md', '.txt']):
                    content_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/contents/{file_path}"
                    content_response = requests.get(content_url, headers=headers)
                    if content_response.status_code == 200:
                        content_data = content_response.json()
                        if content_data.get('encoding') == 'base64':
                            file_content = base64.b64decode(content_data['content']).decode('utf-8')
                            file_contents[file_path] = file_content[:500]  # First 500 chars
            
            structure_info = f"Files: {', '.join(files) if files else 'Empty repository'}"
            if file_contents:
                structure_info += f"\nFile contents preview: {json.dumps(file_contents, indent=2)}"
            
            self.repo_content = structure_info
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
            {{"operation": "delete_lines", "file": "filename.ext", "line": 10, "count": 3}}
            
            Return a JSON array of operations. Example:
            [
                {{"operation": "create", "file": "hello.py", "content": "print('Hello World!')"}}
            ]
            
            Important: Only respond with valid JSON array, no additional text.
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
            
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            return response.json()['choices'][0]['message']['content']
            
        except requests.exceptions.Timeout:
            raise Exception("DeepSeek API request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API call failed: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected response format from DeepSeek API: {str(e)}")
    
    def parse_instructions(self, response: str) -> List[Dict[str, Any]]:
        """Parse the JSON instructions from DeepSeek response"""
        try:
            # Clean the response - remove any markdown code blocks
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            instructions = json.loads(cleaned_response)
            
            if not isinstance(instructions, list):
                raise ValueError("Instructions should be a JSON array")
                
            # Validate each instruction has required fields
            for i, instruction in enumerate(instructions):
                if 'operation' not in instruction:
                    raise ValueError(f"Instruction {i} missing 'operation' field")
                if 'file' not in instruction:
                    raise ValueError(f"Instruction {i} missing 'file' field")
                    
            return instructions
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON instructions: {str(e)}\nResponse was: {response}")
        except Exception as e:
            raise Exception(f"Failed to parse instructions: {str(e)}")
    
    def apply_file_operations(self, instructions: List[Dict[str, Any]]):
        """Apply file operations locally"""
        applied_operations = []
        
        for instruction in instructions:
            try:
                op_type = instruction['operation']
                filename = instruction['file']
                
                if op_type == 'create':
                    content = instruction.get('content', '')
                    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(content)
                    applied_operations.append(f"Created file: {filename}")
                    
                elif op_type == 'delete':
                    if os.path.exists(filename):
                        os.remove(filename)
                        applied_operations.append(f"Deleted file: {filename}")
                    else:
                        print(f"⚠️  File not found for deletion: {filename}")
                        
                elif op_type == 'insert':
                    line_num = instruction.get('line')
                    content = instruction.get('content', '')
                    
                    if line_num is None:
                        raise ValueError("Missing 'line' for insert operation")
                    
                    if not os.path.exists(filename):
                        # Create file if it doesn't exist
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(content + '\n')
                        applied_operations.append(f"Created file with content: {filename}")
                    else:
                        with open(filename, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        # Insert at specific line (1-indexed)
                        if line_num < 1 or line_num > len(lines) + 1:
                            raise ValueError(f"Line number {line_num} out of range for file {filename}")
                        
                        lines.insert(line_num - 1, content + '\n')
                        
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.writelines(lines)
                        
                        applied_operations.append(f"Inserted content at line {line_num} in: {filename}")
                    
                elif op_type == 'delete_lines':
                    line_num = instruction.get('line')
                    lines_to_delete = instruction.get('count', 1)
                    
                    if line_num is None:
                        raise ValueError("Missing 'line' for delete_lines operation")
                    
                    if not os.path.exists(filename):
                        raise ValueError(f"File not found: {filename}")
                    
                    with open(filename, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    if line_num < 1 or line_num > len(lines):
                        raise ValueError(f"Line number {line_num} out of range for file {filename}")
                    
                    # Delete lines starting from line_num
                    start_idx = line_num - 1
                    end_idx = start_idx + int(lines_to_delete)
                    del lines[start_idx:end_idx]
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                    
                    applied_operations.append(f"Deleted {lines_to_delete} lines starting from line {line_num} in: {filename}")
                    
                else:
                    raise ValueError(f"Unknown operation: {op_type}")
                    
            except Exception as e:
                raise Exception(f"Failed to apply operation {json.dumps(instruction)}: {str(e)}")
        
        return applied_operations
    
    def commit_and_push_to_github(self):
        """Commit and push changes to GitHub using fine-grained token"""
        try:
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get the default branch first
            repo_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}"
            repo_response = requests.get(repo_url, headers=headers)
            repo_response.raise_for_status()
            default_branch = repo_response.json().get('default_branch', 'main')
            
            # Get the latest commit SHA from the default branch
            branch_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/branches/{default_branch}"
            branch_response = requests.get(branch_url, headers=headers)
            branch_response.raise_for_status()
            latest_commit_sha = branch_response.json()['commit']['sha']
            
            # Get the tree SHA from the latest commit
            commit_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/commits/{latest_commit_sha}"
            commit_response = requests.get(commit_url, headers=headers)
            commit_response.raise_for_status()
            base_tree_sha = commit_response.json()['tree']['sha']
            
            # Create new tree with current files
            tree_entries = []
            for root, dirs, files in os.walk('.'):
                for file in files:
                    # Skip hidden files and the script itself
                    if file.startswith('.') or file == os.path.basename(__file__):
                        continue
                    
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath)
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree_entries.append({
                        'path': relative_path,
                        'mode': '100644',
                        'type': 'blob',
                        'content': content
                    })
            
            if not tree_entries:
                print("📝 No changes to commit")
                return "No changes to commit"
            
            # Create new tree
            tree_url = f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/trees"
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
                f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/commits",
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
                f"https://api.github.com/repos/{self.github_username}/{self.github_repo}/git/refs/heads/{default_branch}",
                headers=headers,
                json=ref_payload
            )
            ref_response.raise_for_status()
            
            return f"Successfully committed and pushed {len(tree_entries)} files to {default_branch} branch"
            
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get('message', error_detail)
                except:
                    pass
            raise Exception(f"GitHub API operation failed: {error_detail}")
    
    def run(self, instruction: str = None):
        """Main execution method"""
        try:
            print("🚀 Starting DeepSeek Coding Agent...")
            print("🔐 Validating GitHub token...")
            self.validate_github_token()
            
            # Use default instruction if none provided
            if instruction is None:
                instruction = DEFAULT_INSTRUCTION
                print(f"📝 Using default instruction: '{instruction}'")
            else:
                print(f"📝 Using instruction: '{instruction}'")
            
            # Get current repo structure
            print("📁 Fetching repository structure...")
            repo_structure = self.get_repo_structure()
            print(f"📊 Repository status: {repo_structure.splitlines()[0]}")
            
            # Call DeepSeek API
            print("🤖 Calling DeepSeek API...")
            deepseek_response = self.call_deepseek_api(instruction)
            print("✅ DeepSeek response received")
            
            # Parse instructions
            print("📝 Parsing instructions...")
            instructions = self.parse_instructions(deepseek_response)
            print(f"📋 Parsed {len(instructions)} operation(s)")
            
            # Apply file operations
            print("⚡ Applying file operations locally...")
            applied_ops = self.apply_file_operations(instructions)
            for op in applied_ops:
                print(f"  ✅ {op}")
            
            if not applied_ops:
                print("ℹ️  No file operations were applied")
                return
            
            # Commit and push to GitHub
            print("📤 Pushing changes to GitHub...")
            push_result = self.commit_and_push_to_github()
            print(f"✅ {push_result}")
            
            print("🎉 All operations completed successfully!")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise

def main():
    """Main function with optional custom instruction"""
    import sys
    
    try:
        agent = DeepSeekCodingAgent()
        
        # Use command line argument as instruction if provided
        if len(sys.argv) > 1:
            instruction = ' '.join(sys.argv[1:])
            agent.run(instruction)
        else:
            agent.run()
            
    except Exception as e:
        print(f"💥 Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
