#!/usr/bin/env python3
"""
Test rapide pour vérifier la configuration de l'API Freepik
"""

import os
import logging
from dotenv import load_dotenv
from competition_waste_generator import FreepikImageGenerator, CompetitionWasteItem

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_freepik_api():
    """Test simple de l'API Freepik"""
    
    print("🔍 Testing Freepik API Configuration...")
    
    # 1. Vérifier les variables d'environnement
    api_key = os.getenv("FREEPIK_API_KEY")
    if not api_key:
        print("❌ FREEPIK_API_KEY not found in environment")
        print("💡 Create a .env file with your Freepik API key")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...")
    
    # 2. Initialiser le générateur
    try:
        generator = FreepikImageGenerator()
        print("✅ Generator initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize generator: {e}")
        return False
    
    # 3. Test de connectivité
    print("🌐 Testing API connectivity...")
    if generator._test_api_connectivity():
        print("✅ API is accessible")
    else:
        print("⚠️  API connectivity test failed")
    
    # 4. Test de génération simple
    print("🎨 Testing image generation...")
    test_item = CompetitionWasteItem(
        name="test_bottle",
        category="menagers", 
        zone="residentielle",
        description="Test plastic bottle",
        colors=["blue"],
        materials=["plastic"],
        typical_forms=["bottle"]
    )
    
    try:
        # Test juste la création de tâche (sans attendre la completion)
        prompt = generator._build_prompt(test_item)
        print(f"✅ Prompt generated: {prompt[:50]}...")
        
        task_id = generator._create_generation_task(prompt)
        if task_id:
            print(f"✅ Task created successfully: {task_id}")
            print("🎉 Freepik API is working correctly!")
            return True
        else:
            print("❌ Failed to create generation task")
            print("💡 Check your API key permissions or subscription")
            return False
            
    except Exception as e:
        print(f"❌ Error testing generation: {e}")
        return False

if __name__ == "__main__":
    success = test_freepik_api()
    
    if success:
        print("\n" + "="*50)
        print("🚀 Ready to run the full generator!")
        print("Run: python competition_waste_generator.py")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("🔧 Please fix the issues above before running the generator")
        print("="*50)
