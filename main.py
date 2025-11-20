#!/usr/bin/env python3
"""
DeepSeek Coding Agent - Fixed for GitHub API issues
"""

import os
import json
import requests
import base64
from typing import Dict, List, Any

GITHUB_API_URL = "https://api.github.com"
DEFAULT_INSTRUCTION = "write a hello world program"

class GitHubCodingAgent:
    def __init__(self):
        self.load_environment_variables()
        
    def load_environment_variables(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.github_token, self.github_username, self.github_repo]):
            raise ValueError("Missing GitHub environment variables")
    
    def get_headers(self):
        return {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def is_repo_empty(self):
        """Check if repository is empty using contents API"""
        headers = self.get_headers()
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            return True  # No contents endpoint = empty repo
        elif response.status_code == 200:
            contents = response.json()
            return len(contents) == 0  # Empty array = empty repo
        else:
            # If we can't determine, assume it's empty to be safe
            return True
    
    def create_file_via_contents_api(self, filename: str, content: str, message: str = None):
        """Create a file using GitHub Contents API (simpler approach)"""
        headers = self.get_headers()
        
        if message is None:
            message = f"Add {filename}"
        
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
        
        payload = {
            'message': message,
            'content': base64.b64encode(content.encode('utf-8')).decode('utf-8')
        }
        
        response = requests.put(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            return True, f"✅ Created {filename}"
        else:
            return False, f"❌ Failed to create {filename}: {response.status_code} - {response.text}"
    
    def create_hello_world_files(self):
        """Create hello world files using the simpler Contents API"""
        files = {
            'hello.py': "#!/usr/bin/env python3\nprint('Hello, World!')",
            'README.md': "# Hello World\n\nThis project was created automatically by a coding agent."
        }
        
        results = []
        for filename, content in files.items():
            success, message = self.create_file_via_contents_api(filename, content)
            results.append(message)
            if not success:
                # Stop if one file fails
                break
                
        return results
    
    def run(self, instruction: str = None):
        """Main execution method"""
        try:
            print("🚀 Starting GitHub Coding Agent...")
            print("=" * 50)
            
            # Check if repo is empty
            print("📁 Checking repository status...")
            if self.is_repo_empty():
                print("📭 Repository is empty - creating initial files...")
                results = self.create_hello_world_files()
            else:
                print("📂 Repository has existing files - creating hello.py...")
                results = self.create_hello_world_files()
            
            print("📊 Results:")
            for result in results:
                print(f"  {result}")
            
            print("🎉 Operation completed!")
            
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    import sys
    
    try:
        agent = GitHubCodingAgent()
        
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
