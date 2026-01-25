"""Test Groq API key validity"""
import requests
import json

import os

# Groq API key - load from environment variable
API_KEY = os.getenv("GROQ_API_KEY", "your-api-key-here")

# Groq API endpoint
url = "https://api.groq.com/openai/v1/chat/completions"

# Headers
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Simple test request
data = {
    "model": "llama-3.3-70b-versatile",
    "messages": [
        {
            "role": "user",
            "content": "Say 'API key is valid' if you can read this."
        }
    ],
    "max_tokens": 50
}

print("Testing Groq API key...")
print(f"API Key: {API_KEY[:20]}...")
print("-" * 50)

try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        message = result['choices'][0]['message']['content']
        print("✅ SUCCESS: API key is valid and working!")
        print(f"Response: {message}")
    elif response.status_code == 401:
        print("❌ FAILED: Invalid API key (401 Unauthorized)")
        print(f"Error: {response.text}")
    elif response.status_code == 429:
        print("⚠️  WARNING: Rate limit exceeded (429)")
        print(f"Error: {response.text}")
    else:
        print(f"❌ FAILED: Unexpected status code {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.exceptions.Timeout:
    print("❌ FAILED: Request timed out")
except requests.exceptions.RequestException as e:
    print(f"❌ FAILED: Request error - {str(e)}")
except Exception as e:
    print(f"❌ FAILED: Unexpected error - {str(e)}")

print("-" * 50)
