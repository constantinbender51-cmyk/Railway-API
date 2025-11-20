#!/usr/bin/env python3
"""
DeepSeek Coding Agent with Approval Loop
"""

import os
import json
import requests
import base64
import time

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GITHUB_API_URL = "https://api.github.com"

class DeepSeekCodingAgent:
    def __init__(self):
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.github_repo = os.getenv('GITHUB_REPO')
        
        if not all([self.deepseek_api_key, self.github_token, self.github_username, self.github_repo]):
            raise ValueError("Missing required environment variables")

    def get_entire_codebase(self) -> str:
        """Get all files and their contents from the repository"""
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f"{GITHUB_API_URL}/repos/{self.github_username}/{self.github_repo}/contents/"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return "Empty repository or cannot access files"
        
        codebase = []
        items = response.json()
        
        for item in items:
            if item['type'] == 'file':
                file_url = item['url']
                file_response = requests.get(file_url, headers=headers)
                
                if file_response.status_code == 200:
                    file_data = file_response.json()
                    if file_data.get('encoding') == 'base64':
                        content = base64.b64decode(file_data['content']).decode('utf-8')
                        codebase.append(f"--- {item['path']} ---\n{content}\n")
        
        return "\n".join(codebase) if codebase else "Empty repository"

    def call_deepseek(self, prompt: str) -> str:
        """Call DeepSeek API with given prompt"""
        headers = {
            'Authorization': f'Bearer {self.deepseek_api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'deepseek-coder',
            'messages': [
                {'role': 'system', 'content': 'You are a coding assistant. Respond with clear actions.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.1,
            'max_tokens': 4000
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
        
        try:
            instructions = json.loads(cleaned.strip())
            return instructions
        except json.JSONDecodeError:
            return []

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
        return None, None

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
            return response.status_code in [200, 201]

        elif op == 'delete':
            current_content, sha = self.get_file_content(file)
            if not sha:
                return False
            
            payload = {
                'message': f'Delete {file}',
                'sha': sha
            }
            response = requests.delete(url, headers=headers, json=payload)
            return response.status_code in [200, 204]

        elif op == 'insert':
            line = instruction['line']
            content_to_insert = instruction['content']
            
            current_content, sha = self.get_file_content(file)
            if current_content is None:
                payload = {
                    'message': f'Create {file} with insert at line {line}',
                    'content': base64.b64encode(content_to_insert.encode('utf-8')).decode('utf-8')
                }
                response = requests.put(url, headers=headers, json=payload)
                return response.status_code in [200, 201]
            
            lines = current_content.split('\n')
            if line < 1 or line > len(lines) + 1:
                return False
            
            lines.insert(line - 1, content_to_insert)
            new_content = '\n'.join(lines)
            
            payload = {
                'message': f'Insert at line {line} in {file}',
                'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                'sha': sha
            }
            response = requests.put(url, headers=headers, json=payload)
            return response.status_code in [200, 201]

        elif op == 'delete_from':
            line = instruction['line']
            content_to_delete = instruction['content']
            
            current_content, sha = self.get_file_content(file)
            if not current_content:
                return False
            
            lines = current_content.split('\n')
            if line < 1 or line > len(lines):
                return False
            
            target_line_content = lines[line - 1] if line - 1 < len(lines) else ""
            if content_to_delete in target_line_content:
                del lines[line - 1]
                new_content = '\n'.join(lines)
                
                payload = {
                    'message': f'Delete content from line {line} in {file}',
                    'content': base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
                    'sha': sha
                }
                response = requests.put(url, headers=headers, json=payload)
                return response.status_code in [200, 201]
            else:
                return False

        return False

    def apply_instructions(self, instructions: list):
        """Apply all instructions to GitHub"""
        results = []
        for instruction in instructions:
            success = self.apply_instruction(instruction)
            op = instruction['operation']
            file = instruction['file']
            if success:
                results.append(f"✅ {op} {file}")
            else:
                results.append(f"❌ {op} {file}")
        return results

    def check_approval(self, instruction: str, codebase: str) -> tuple:
        """Check if DeepSeek approves the code or provides revisions"""
        prompt = f"""
        ORIGINAL INSTRUCTION: {instruction}
        
        CURRENT CODEBASE AFTER IMPLEMENTATION:
        {codebase}
        
        Please review the code and respond with one of two options:
        
        OPTION 1 - APPROVE: If the code correctly implements the instruction and has no issues, respond with:
        {{"status": "approved"}}
        
        OPTION 2 - REVISE: If you find issues or improvements needed, respond with file operations:
        {{
            "status": "revise",
            "instructions": [
                {{"operation": "write", "file": "filename", "content": "content"}},
                {{"operation": "insert", "file": "filename", "line": 5, "content": "code"}}
            ]
        }}
        
        Only respond with valid JSON, no other text.
        """
        
        response = self.call_deepseek(prompt)
        
        try:
            result = json.loads(response.strip())
            status = result.get('status')
            
            if status == 'approved':
                return True, []
            elif status == 'revise':
                instructions = result.get('instructions', [])
                return False, instructions
            else:
                return False, []
                
        except json.JSONDecodeError:
            return False, []

    def run(self, instruction: str = "write a hello world program"):
        """Main execution flow with approval loop"""
        print(f"📝 Instruction: {instruction}")
        iteration = 1
        
        while True:
            print(f"\n🔄 Iteration {iteration}")
            print("=" * 40)
            
            # Get current codebase
            print("📁 Fetching codebase...")
            codebase = self.get_entire_codebase()
            
            if iteration == 1:
                # First iteration: implement the instruction
                prompt = f"""
                CURRENT CODEBASE:
                {codebase}
                
                INSTRUCTION: {instruction}
                
                Implement this instruction by providing file operations in JSON format:
                
                Available operations:
                - write: Create or overwrite file
                - delete: Delete file  
                - insert: Insert at line
                - delete_from: Delete content from line
                
                Return JSON array of operations. Example:
                [
                    {{"operation": "write", "file": "hello.py", "content": "print('Hello World!')"}}
                ]
                
                Only respond with valid JSON array.
                """
            else:
                # Subsequent iterations: apply revisions
                prompt = f"""
                CURRENT CODEBASE:
                {codebase}
                
                REVISION REQUEST: Apply the following improvements to the code
                
                Return JSON array of file operations:
                [
                    {{"operation": "write", "file": "filename", "content": "content"}}
                ]
                
                Only respond with valid JSON array.
                """
            
            # Call DeepSeek for implementation
            print("🤖 Getting implementation from DeepSeek...")
            response = self.call_deepseek(prompt)
            
            # Parse and apply instructions
            instructions = self.parse_instructions(response)
            if instructions:
                print(f"📦 Applying {len(instructions)} operations...")
                results = self.apply_instructions(instructions)
                for result in results:
                    print(f"  {result}")
            else:
                print("⚠️  No operations to apply")
            
            # Wait a moment for GitHub to update
            print("⏳ Waiting for GitHub sync...")
            time.sleep(2)
            
            # Get updated codebase for review
            updated_codebase = self.get_entire_codebase()
            
            # Check for approval
            print("🔍 Requesting code review...")
            approved, revision_instructions = self.check_approval(instruction, updated_codebase)
            
            if approved:
                print("\n🎉 CODE APPROVED!")
                print("✅ Implementation completed successfully")
                break
            elif revision_instructions:
                print(f"📋 Revision needed: {len(revision_instructions)} changes")
                iteration += 1
            else:
                print("⚠️  Could not determine approval status, continuing...")
                iteration += 1
            
            if iteration > 5:  # Safety limit
                print("\n🛑 Maximum iterations reached")
                break

if __name__ == "__main__":
    import sys
    
    agent = DeepSeekCodingAgent()
    instruction = sys.argv[1] if len(sys.argv) > 1 else "write a hello world program"
    agent.run(instruction)
