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
        
        Respond with JSON array of file operations. Available operations:
        
        - write: Create or overwrite file
          {{"operation": "write", "file": "filename", "content": "full content"}}
        
        - delete: Delete file  
          {{"operation": "delete", "file": "filename"}}
        
        - insert: Insert content at specific line
          {{"operation": "insert", "file": "filename", "line": 5, "content": "code to insert"}}
        
        - delete_from: Delete content starting from line
          {{"operation": "delete_from", "file": "filename", "line": 10, "content": "content to delete"}}
        
        Return ONLY JSON array. Example:
        [
            {{"operation": "write", "file": "hello.py", "content": "print('Hello World!')"}}
        ]
        """
        
        payload = {
            'model': 'deepseek-coder',
            'messages': [
                {'role': 'system', 'content': 'Respond ONLY with JSON array of file operations. No other text.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.1
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    def parse_instructions(self, response: str) -> list:
        """Parse JSON instructions from DeepSeek response"""
        cleaned = response.strip()
        if '```json' in cleaned:
            cleaned = cleaned.split('```json')[1].split('```')[0]
        elif '```' in cleaned:
            cleaned = cleaned.split('```')[1].split('```')[0]
        
        instructions = json.loads(cleaned.strip())
        return instructions

    def get_file_content(self, filename: str) -> tuple:
        """Get current file content and SHA from GitHub"""
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{filename}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            file_data = response.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return content, file_data['sha']
        return "", None

    def apply_instruction(self, instruction: dict):
        """Apply a single file operation to GitHub"""
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        op = instruction['operation']
        file = instruction['file']
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/{file}"

        if op == 'write':
            payload = {
                'message': f'Write {file}',
                'content': base64.b64encode(instruction['content'].encode('utf-8')).decode('utf-8')
            }
            response = requests.put(url, headers=headers, json=payload)
            return f"Written {file}" if response.status_code in [200, 201] else f"Failed to write {file}"

        elif op == 'delete':
            # Get current file to obtain SHA
            current_content, sha = self.get_file_content(file)
            if not sha:
                return f"Cannot delete {file}: file not found"
            
            payload = {
                'message': f'Delete {file}',
                'sha': sha
            }
            response = requests.delete(url, headers=headers, json=payload)
            return f"Deleted {file}" if response.status_code in [200, 204] else f"Failed to delete {file}"

        elif op == 'insert':
            line = instruction['line']
            content_to_insert = instruction['content']
            
            # Get current file content
            current_content, sha = self.get_file_content(file)
            if current_content is None:
                # File doesn't exist, create it with the content
                payload = {
                    'message': f'Create {file} with insert at line {line}',
                    'content': base64.b64encode(content_to_insert.encode('utf-8')).decode('utf-8')
                }
                response = requests.put(url, headers=headers, json=payload)
                return f"Created {file} with insert" if response.status_code in [200, 201] else f"Failed to create {file}"
            
            # Insert at specified line
            lines = current_content.split('\n')
            if line < 1 or line > len(lines) + 1:
                return f"Line {line} out of range for {file}"
            
            lines.insert(line - 1, content_to_insert)
            new_content = '\n'.join(lines)
            
            payload = {
                'message': f'Insert at line {line} in {file}',
                'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                'sha': sha
            }
            response = requests.put(url, headers=headers, json=payload)
            return f"Inserted at line {line} in {file}" if response.status_code in [200, 201] else f"Failed to insert in {file}"

        elif op == 'delete_from':
            line = instruction['line']
            content_to_delete = instruction['content']
            
            # Get current file content
            current_content, sha = self.get_file_content(file)
            if not current_content:
                return f"Cannot delete from {file}: file not found"
            
            # Find and delete the content starting from line
            lines = current_content.split('\n')
            if line < 1 or line > len(lines):
                return f"Line {line} out of range for {file}"
            
            # Delete the specified content starting from the line
            target_line_content = lines[line - 1] if line - 1 < len(lines) else ""
            if content_to_delete in target_line_content:
                # Remove the line containing the content
                del lines[line - 1]
                new_content = '\n'.join(lines)
                
                payload = {
                    'message': f'Delete content from line {line} in {file}',
                    'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                    'sha': sha
                }
                response = requests.put(url, headers=headers, json=payload)
                return f"Deleted content from line {line} in {file}" if response.status_code in [200, 201] else f"Failed to delete from {file}"
            else:
                return f"Content not found at line {line} in {file}"

        else:
            return f"Unknown operation: {op}"

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
