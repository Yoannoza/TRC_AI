#!/usr/bin/env python3
"""
Debug script pour voir la structure exacte de l'API Freepik
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def debug_freepik_api():
    api_key = os.getenv("FREEPIK_API_KEY")
    base_url = "https://api.freepik.com/v1/ai/text-to-image/seedream"
    
    # 1. Créer une tâche simple
    payload = {
        "prompt": "A simple plastic bottle on white background",
        "aspect_ratio": "square_1_1"
    }
    
    headers = {
        "x-freepik-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    print("📝 Creating task...")
    response = requests.post(base_url, json=payload, headers=headers, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Task creation failed: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    print(f"✅ Task creation response: {json.dumps(data, indent=2)}")
    
    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        print("❌ No task_id in response")
        return
    
    print(f"📋 Task ID: {task_id}")
    
    # 2. Suivre le statut jusqu'à completion
    check_url = f"{base_url}/{task_id}"
    headers = {"x-freepik-api-key": api_key}
    
    for i in range(20):  # Max 20 checks
        print(f"🔄 Check {i+1}/20...")
        
        response = requests.get(check_url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"❌ Status check failed: {response.status_code}")
            continue
        
        data = response.json()
        print(f"📊 Status response: {json.dumps(data, indent=2)}")
        
        status = data.get("data", {}).get("status")
        print(f"📈 Status: {status}")
        
        if status == "COMPLETED":
            print("🎉 Task completed!")
            print("📄 Full completion data:")
            print(json.dumps(data, indent=2))
            
            # Analyser la structure pour trouver l'URL
            task_data = data.get("data", {})
            
            # Possibilités multiples
            possible_urls = []
            
            # Option 1: result.images
            result = task_data.get("result", {})
            if "images" in result:
                possible_urls.extend(result["images"])
            
            # Option 2: generated
            if "generated" in task_data:
                possible_urls.extend(task_data["generated"])
            
            # Option 3: urls
            if "urls" in task_data:
                possible_urls.extend(task_data["urls"])
            
            print(f"🔗 Possible URLs found: {possible_urls}")
            
            return possible_urls
            
        elif status in ["FAILED", "CANCELLED"]:
            print(f"❌ Task failed: {status}")
            return None
        
        print("⏳ Waiting 5 seconds...")
        time.sleep(5)
    
    print("⏰ Timeout waiting for completion")
    return None

if __name__ == "__main__":
    urls = debug_freepik_api()
    if urls:
        print(f"\n🎯 URLs to use: {urls}")
    else:
        print("\n❌ No URLs found")
