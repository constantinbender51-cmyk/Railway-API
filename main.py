#!/usr/bin/env python3
"""
Simplified DeepSeek Coding Agent
"""

import os
import json
import requests
import base64

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GITHUB_API_URL = "https://api.github.com"

class SimpleCodingAgent:
    def __init__(self):
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.deepseek_api_key, self.github_token, self.github_username, self.github_repo]):
            raise ValueError("Missing required environment variables")

    def call_deepseek(self, instruction: str) -> str:
        """Call DeepSeek API and return response"""
        headers = {
            'Authorization': f'Bearer {self.deepseek_api_key}',
            'Content-Type': 'application/json'
        }
        
        prompt = f"""
        Instruction: {instruction}
        
        Respond with JSON array of file operations:
        [
            {{"operation": "create", "file": "filename", "content": "content"}},
            {{"operation": "update", "file": "filename", "content": "content"}},
            {{"operation": "delete", "file": "filename"}}
        ]
        
        Only respond with valid JSON array.
        """
        
        payload = {
            'model': 'deepseek-coder',
            'messages': [
                {'role': 'system', 'content': 'Respond ONLY with JSON array of file operations.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.1
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    def parse_instructions(self, response: str) -> list:
        """Parse JSON instructions from DeepSeek response"""
        # Extract JSON from response
        cleaned = response.strip()
        if '```json' in cleaned:
            cleaned = cleaned.split('```json')[1].split('```')[0]
        elif '```' in cleaned:
            cleaned = cleaned.split('```')[1].split('```')[0]
        
        instructions = json.loads(cleaned.strip())
        return instructions

    def apply_instruction(self, instruction: dict):
        """Apply a single file operation to GitHub"""
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        op = instruction['operation']
        file = instruction['file']
        
        if op == 'create':
            url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{file}"
            payload = {
                'message': f'Create {file}',
                'content': base64.b64encode(instruction['content'].encode()).decode()
            }
            response = requests.put(url, headers=headers, json=payload)
            return f"Created {file}" if response.status_code in [200, 201] else f"Failed to create {file}"
        
        elif op == 'update':
            url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{file}"
            # Get current file SHA
            current = requests.get(url, headers=headers)
            if current.status_code != 200:
                return f"Cannot update {file}: not found"
            
            sha = current.json()['sha']
            payload = {
                'message': f'Update {file}',
                'content': base64.b64encode(instruction['content'].encode()).decode(),
                'sha': sha
            }
            response = requests.put(url, headers=headers, json=payload)
            return f"Updated {file}" if response.status_code in [200, 201] else f"Failed to update {file}"
        
        elif op == 'delete':
            url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{file}"
            # Get current file SHA
            current = requests.get(url, headers=headers)
            if current.status_code != 200:
                return f"Cannot delete {file}: not found"
            
            sha = current.json()['sha']
            payload = {
                'message': f'Delete {file}',
                'sha': sha
            }
            response = requests.delete(url, headers=headers, json=payload)
            return f"Deleted {file}" if response.status_code in [200, 204] else f"Failed to delete {file}"

    def run(self, instruction: str = "write a hello world program"):
        """Main execution flow"""
        print(f"📝 Instruction: {instruction}")
        
        # Prompt DeepSeek
        print("🤖 Calling DeepSeek...")
        response = self.call_deepseek(instruction)
        
        # Parse response
        print("📋 Parsing instructions...")
        instructions = self.parse_instructions(response)
        print(f"📦 Found {len(instructions)} operations")
        
        # Apply instructions
        print("⚡ Applying to GitHub...")
        for instruction in instructions:
            result = self.apply_instruction(instruction)
            print(f"  {result}")
        
        print("🎉 Done!")

if __name__ == "__main__":
    import sys
    
    agent = SimpleCodingAgent()
    instruction = sys.argv[1] if len(sys.argv) > 1 else "write a hello world program"
    agent.run(instruction)
