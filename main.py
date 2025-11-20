#!/usr/bin/env python3
"""
DeepSeek Coding Agent - Complete with DeepSeek API integration
"""

import os
import json
import requests
import base64
from typing import Dict, List, Any

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GITHUB_API_URL = "https://api.github.com"
DEFAULT_INSTRUCTION = "write a hello world program"

class DeepSeekCodingAgent:
    def __init__(self):
        self.load_environment_variables()
        
    def load_environment_variables(self):
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.github_token, self.github_username, self.github_repo]):
            raise ValueError("Missing GitHub environment variables")
        if not self.deepseek_api_key:
            print("⚠️  DEEPSEEK_API_KEY not set - will use default hello world")
    
    def get_github_headers(self):
        return {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def get_repo_files(self):
        """Get current files in the repository"""
        headers = self.get_github_headers()
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return [item['name'] for item in response.json() if item['type'] == 'file']
        return []
    
    def get_file_content(self, filename: str):
        """Get content of a specific file"""
        headers = self.get_github_headers()
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            file_data = response.json()
            if file_data.get('encoding') == 'base64':
                return base64.b64decode(file_data['content']).decode('utf-8')
        return None
    
    def call_deepseek_api(self, instruction: str) -> str:
        """Call DeepSeek API with the instruction"""
        if not self.deepseek_api_key:
            raise Exception("DeepSeek API key not available")
            
        try:
            headers = {
                'Authorization': f'Bearer {self.deepseek_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Get current repo state for context
            current_files = self.get_repo_files()
            repo_context = f"Current files: {', '.join(current_files) if current_files else 'Empty repository'}"
            
            prompt = f"""
            Repository Context: {repo_context}
            
            Instruction: {instruction}
            
            Respond with JSON instructions for file operations. Use the following format:
            
            For creating new files:
            {{"operation": "create", "file": "filename.ext", "content": "full file content"}}
            
            For updating existing files:
            {{"operation": "update", "file": "filename.ext", "content": "new full file content"}}
            
            For deleting files:
            {{"operation": "delete", "file": "filename.ext"}}
            
            Return a JSON array of operations. Example:
            [
                {{"operation": "create", "file": "hello.py", "content": "print('Hello World!')"}},
                {{"operation": "create", "file": "README.md", "content": "# My Project"}}
            ]
            
            Important: 
            - Only respond with valid JSON array, no additional text
            - For updates, provide the complete new file content
            - You can create, update, or delete multiple files
            - Use proper file extensions and meaningful filenames
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
            
            print("📡 Calling DeepSeek API...")
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            print("✅ DeepSeek API response received")
            return response.json()['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API call failed: {e}")
    
    def parse_instructions(self, response: str) -> List[Dict[str, Any]]:
        """Parse the JSON instructions from DeepSeek response"""
        try:
            # Clean the response
            cleaned_response = response.strip()
            
            # Extract JSON from code blocks if present
            if '```json' in cleaned_response:
                cleaned_response = cleaned_response.split('```json')[1].split('```')[0]
            elif '```' in cleaned_response:
                cleaned_response = cleaned_response.split('```')[1].split('```')[0]
            
            cleaned_response = cleaned_response.strip()
            
            instructions = json.loads(cleaned_response)
            
            if not isinstance(instructions, list):
                raise ValueError("Instructions should be a JSON array")
                
            # Validate each instruction
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
    
    def apply_file_operation(self, instruction: Dict[str, Any]):
        """Apply a single file operation to GitHub"""
        headers = self.get_github_headers()
        operation = instruction['operation']
        filename = instruction['file']
        
        if operation == 'create':
            content = instruction['content']
            url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
            
            payload = {
                'message': f'Create {filename}',
                'content': base64.b64encode(content.encode('utf-8')).decode('utf-8')
            }
            
            response = requests.put(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                return f"✅ Created {filename}"
            else:
                return f"❌ Failed to create {filename}: {response.status_code}"
                
        elif operation == 'update':
            content = instruction['content']
            url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
            
            # First get the current file to get its SHA
            current_response = requests.get(url, headers=headers)
            if current_response.status_code != 200:
                return f"❌ Cannot update {filename}: file not found"
            
            current_data = current_response.json()
            sha = current_data['sha']
            
            payload = {
                'message': f'Update {filename}',
                'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
                'sha': sha
            }
            
            response = requests.put(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                return f"✅ Updated {filename}"
            else:
                return f"❌ Failed to update {filename}: {response.status_code}"
                
        elif operation == 'delete':
            url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
            
            # First get the current file to get its SHA
            current_response = requests.get(url, headers=headers)
            if current_response.status_code != 200:
                return f"❌ Cannot delete {filename}: file not found"
            
            current_data = current_response.json()
            sha = current_data['sha']
            
            payload = {
                'message': f'Delete {filename}',
                'sha': sha
            }
            
            response = requests.delete(url, headers=headers, json=payload)
            
            if response.status_code in [200, 204]:
                return f"✅ Deleted {filename}"
            else:
                return f"❌ Failed to delete {filename}: {response.status_code}"
        
        else:
            return f"❌ Unknown operation: {operation}"
    
    def apply_deepseek_instructions(self, instructions: List[Dict[str, Any]]):
        """Apply all instructions from DeepSeek response"""
        results = []
        
        for instruction in instructions:
            print(f"  Processing: {instruction['operation']} on {instruction['file']}")
            result = self.apply_file_operation(instruction)
            results.append(result)
            
        return results
    
    def create_default_hello_world(self):
        """Create default hello world files if DeepSeek fails"""
        default_instructions = [
            {
                "operation": "create",
                "file": "hello.py",
                "content": "#!/usr/bin/env python3\nprint('Hello, World!')"
            },
            {
                "operation": "create",
                "file": "README.md",
                "content": "# Hello World\n\nThis project was created automatically by DeepSeek Coding Agent."
            }
        ]
        
        print("🔄 Using default hello world instructions")
        return self.apply_deepseek_instructions(default_instructions)
    
    def run(self, instruction: str = None):
        """Main execution method"""
        try:
            print("🚀 Starting DeepSeek Coding Agent...")
            print("=" * 50)
            
            if instruction is None:
                instruction = DEFAULT_INSTRUCTION
            print(f"📝 Instruction: '{instruction}'")
            
            # Get current repo state
            current_files = self.get_repo_files()
            print(f"📁 Current files: {', '.join(current_files) if current_files else 'Empty repository'}")
            
            # Try to get instructions from DeepSeek
            instructions = None
            if self.deepseek_api_key:
                try:
                    deepseek_response = self.call_deepseek_api(instruction)
                    instructions = self.parse_instructions(deepseek_response)
                    print(f"📋 Parsed {len(instructions)} operation(s) from DeepSeek")
                except Exception as e:
                    print(f"⚠️  DeepSeek API failed: {e}")
                    print("🔄 Falling back to default hello world")
            
            # Apply instructions
            if instructions:
                print("⚡ Applying DeepSeek instructions...")
                results = self.apply_deepseek_instructions(instructions)
            else:
                results = self.create_default_hello_world()
            
            # Display results
            print("📊 Operation Results:")
            for result in results:
                print(f"  {result}")
            
            print("🎉 All operations completed!")
            
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
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
