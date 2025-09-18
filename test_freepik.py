#!/usr/bin/env python3
"""
Testeur de clés API Freepik
===========================

Script pour tester individuellement les 3 clés API Freepik
et vérifier leur capacité à générer des images.

Utilisation:
python test_freepik_keys.py

Le script va:
1. Charger toutes les clés API disponibles
2. Tester chaque clé avec 3 prompts simples
3. Mesurer les temps de réponse
4. Sauvegarder les images générées
5. Fournir un rapport détaillé

Auteur: Assistant IA
Date: Septembre 2025
"""

import os
import time
import requests
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO
from PIL import Image

# Variables d'environnement
from dotenv import load_dotenv
load_dotenv()

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('freepik_key_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FreepikKeyTester:
    """Testeur pour les clés API Freepik"""
    
    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.api_base_url = "https://api.freepik.com/v1/ai/text-to-image/seedream"
        self.output_dir = Path("freepik_test_results")
        self.output_dir.mkdir(exist_ok=True)
        
        # Prompts de test simples
        self.test_prompts = [
            "red plastic bottle waste",
            "metal can garbage", 
            "cardboard box trash"
        ]
        
        logger.info(f"Loaded {len(self.api_keys)} API keys for testing")
        
    def _load_api_keys(self) -> List[str]:
        """Charge toutes les clés API disponibles"""
        keys = []
        
        # Clé principale
        main_key = os.getenv("FREEPIK_API_KEY")
        if main_key:
            keys.append(main_key)
        
        # Clés additionnelles
        for i in range(1, 10):
            key = os.getenv(f"FREEPIK_API_KEY_{i}")
            if key:
                keys.append(key)
        
        if not keys:
            raise ValueError("Aucune clé API trouvée dans les variables d'environnement")
            
        return keys
    
    def test_single_key(self, key: str, key_index: int) -> Dict:
        """Teste une clé API avec tous les prompts"""
        results = {
            "key_index": key_index,
            "key_preview": f"{key[:8]}...",
            "tests": [],
            "total_success": 0,
            "total_failed": 0,
            "average_time": 0,
            "status": "unknown"
        }
        
        logger.info(f"Testing Key {key_index + 1} ({key[:8]}...)")
        
        total_time = 0
        
        for prompt_index, prompt in enumerate(self.test_prompts):
            test_result = self._test_single_generation(key, key_index, prompt, prompt_index)
            results["tests"].append(test_result)
            
            if test_result["success"]:
                results["total_success"] += 1
                total_time += test_result["generation_time"]
            else:
                results["total_failed"] += 1
        
        # Calculs finaux
        if results["total_success"] > 0:
            results["average_time"] = total_time / results["total_success"]
            
        if results["total_success"] == len(self.test_prompts):
            results["status"] = "perfect"
        elif results["total_success"] > 0:
            results["status"] = "partial"
        else:
            results["status"] = "failed"
            
        logger.info(f"Key {key_index + 1} result: {results['total_success']}/{len(self.test_prompts)} success ({results['status']})")
        
        return results
    
    def _test_single_generation(self, api_key: str, key_index: int, prompt: str, prompt_index: int) -> Dict:
        """Teste la génération d'une image avec une clé"""
        start_time = time.time()
        
        test_result = {
            "prompt": prompt,
            "prompt_index": prompt_index,
            "success": False,
            "generation_time": 0,
            "error_message": None,
            "image_saved": False,
            "image_path": None
        }
        
        try:
            logger.info(f"  [{key_index + 1}] Testing prompt {prompt_index + 1}: '{prompt}'")
            
            # Créer la tâche
            task_id = self._create_task(api_key, prompt)
            if not task_id:
                test_result["error_message"] = "Failed to create generation task"
                return test_result
            
            # Attendre completion
            image_url = self._wait_for_completion(task_id, api_key)
            if not image_url:
                test_result["error_message"] = "Generation timeout or failed"
                return test_result
            
            # Télécharger l'image
            image_data = self._download_image(image_url)
            if not image_data:
                test_result["error_message"] = "Failed to download generated image"
                return test_result
            
            # Sauvegarder l'image
            image_path = self._save_test_image(image_data, key_index, prompt_index)
            
            # Succès
            test_result["success"] = True
            test_result["generation_time"] = time.time() - start_time
            test_result["image_saved"] = image_path is not None
            test_result["image_path"] = str(image_path) if image_path else None
            
            logger.info(f"  [{key_index + 1}] ✓ Generated in {test_result['generation_time']:.1f}s")
            
        except Exception as e:
            test_result["error_message"] = str(e)
            test_result["generation_time"] = time.time() - start_time
            logger.error(f"  [{key_index + 1}] ✗ Error: {e}")
        
        return test_result
    
    def _create_task(self, api_key: str, prompt: str) -> Optional[str]:
        """Crée une tâche de génération"""
        try:
            headers = {
                "x-freepik-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "prompt": prompt,
                "aspect_ratio": "square_1_1",
                "guidance_scale": 3.0,
            }
            
            response = requests.post(
                self.api_base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("task_id")
            else:
                logger.error(f"Task creation failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception creating task: {e}")
            return None
    
    def _wait_for_completion(self, task_id: str, api_key: str, max_wait: int = 60) -> Optional[str]:
        """Attend la completion de la tâche"""
        try:
            headers = {"x-freepik-api-key": api_key}
            check_url = f"{self.api_base_url}/{task_id}"
            
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                response = requests.get(check_url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    task_data = data.get("data", {})
                    status = task_data.get("status")
                    
                    if status == "COMPLETED":
                        generated_urls = task_data.get("generated", [])
                        if len(generated_urls) >= 2 and str(generated_urls[1]).startswith("http"):
                            return generated_urls[1]
                    elif status in ["FAILED", "CANCELLED"]:
                        logger.error(f"Task failed with status: {status}")
                        return None
                    
                    time.sleep(3)
                else:
                    logger.error(f"Status check failed: {response.status_code}")
                    time.sleep(5)
            
            logger.error(f"Timeout waiting for task {task_id}")
            return None
            
        except Exception as e:
            logger.error(f"Exception waiting for completion: {e}")
            return None
    
    def _download_image(self, image_url: str) -> Optional[bytes]:
        """Télécharge l'image générée"""
        try:
            response = requests.get(image_url, timeout=60)
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Image download failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Exception downloading image: {e}")
            return None
    
    def _save_test_image(self, image_data: bytes, key_index: int, prompt_index: int) -> Optional[Path]:
        """Sauvegarde l'image de test"""
        try:
            # Vérifier que c'est une image valide
            img = Image.open(BytesIO(image_data))
            
            # Nom de fichier descriptif
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"key{key_index + 1}_prompt{prompt_index + 1}_{timestamp}.jpg"
            image_path = self.output_dir / filename
            
            # Sauvegarder
            img.save(image_path, "JPEG", quality=95)
            logger.debug(f"Saved test image: {image_path}")
            
            return image_path
            
        except Exception as e:
            logger.error(f"Failed to save test image: {e}")
            return None
    
    def run_comprehensive_test(self) -> Dict:
        """Lance un test complet de toutes les clés"""
        logger.info("=" * 60)
        logger.info("FREEPIK API KEYS COMPREHENSIVE TEST")
        logger.info("=" * 60)
        logger.info(f"Testing {len(self.api_keys)} API keys")
        logger.info(f"Each key will be tested with {len(self.test_prompts)} prompts")
        logger.info(f"Results will be saved in: {self.output_dir}")
        logger.info("-" * 60)
        
        start_time = time.time()
        all_results = []
        
        # Tester chaque clé séquentiellement pour éviter les conflits
        for key_index, api_key in enumerate(self.api_keys):
            key_result = self.test_single_key(api_key, key_index)
            all_results.append(key_result)
            
            # Petit délai entre les clés pour éviter les rate limits
            if key_index < len(self.api_keys) - 1:
                time.sleep(2)
        
        # Statistiques globales
        total_tests = len(self.api_keys) * len(self.test_prompts)
        total_success = sum(r["total_success"] for r in all_results)
        total_time = time.time() - start_time
        
        summary = {
            "test_date": datetime.now().isoformat(),
            "total_keys_tested": len(self.api_keys),
            "total_prompts_per_key": len(self.test_prompts),
            "total_tests": total_tests,
            "total_success": total_success,
            "total_failed": total_tests - total_success,
            "global_success_rate": (total_success / total_tests * 100) if total_tests > 0 else 0,
            "total_test_time": total_time,
            "key_results": all_results
        }
        
        # Générer le rapport
        self._generate_report(summary)
        
        return summary
    
    def _generate_report(self, summary: Dict):
        """Génère un rapport détaillé"""
        logger.info("=" * 60)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        
        # Résultats globaux
        logger.info(f"Total tests: {summary['total_tests']}")
        logger.info(f"Total success: {summary['total_success']}")
        logger.info(f"Total failed: {summary['total_failed']}")
        logger.info(f"Global success rate: {summary['global_success_rate']:.1f}%")
        logger.info(f"Total test time: {summary['total_test_time']:.1f}s")
        logger.info("")
        
        # Détails par clé
        logger.info("DETAILED RESULTS BY API KEY:")
        logger.info("-" * 40)
        
        for result in summary["key_results"]:
            status_emoji = {
                "perfect": "🟢",
                "partial": "🟡", 
                "failed": "🔴"
            }.get(result["status"], "❓")
            
            logger.info(f"{status_emoji} Key {result['key_index'] + 1} ({result['key_preview']}):")
            logger.info(f"   Success: {result['total_success']}/{len(self.test_prompts)}")
            logger.info(f"   Status: {result['status']}")
            
            if result['average_time'] > 0:
                logger.info(f"   Avg time: {result['average_time']:.1f}s")
            
            # Détail des tests individuels
            for test in result["tests"]:
                status = "✓" if test["success"] else "✗"
                time_info = f" ({test['generation_time']:.1f}s)" if test["success"] else ""
                error_info = f" - {test['error_message']}" if test["error_message"] else ""
                logger.info(f"     {status} Prompt {test['prompt_index'] + 1}: {test['prompt'][:30]}...{time_info}{error_info}")
            
            logger.info("")
        
        # Recommandations
        logger.info("RECOMMENDATIONS:")
        logger.info("-" * 20)
        
        perfect_keys = [r for r in summary["key_results"] if r["status"] == "perfect"]
        partial_keys = [r for r in summary["key_results"] if r["status"] == "partial"]
        failed_keys = [r for r in summary["key_results"] if r["status"] == "failed"]
        
        if perfect_keys:
            logger.info(f"✅ {len(perfect_keys)} key(s) working perfectly - ready for production")
        if partial_keys:
            logger.info(f"⚠️  {len(partial_keys)} key(s) working partially - may have rate limits")
        if failed_keys:
            logger.info(f"❌ {len(failed_keys)} key(s) failed completely - check validity")
        
        if summary['global_success_rate'] >= 80:
            logger.info("🎉 Overall system ready for simultaneous generation!")
        elif summary['global_success_rate'] >= 50:
            logger.info("⚠️  System partially ready - expect some failures")
        else:
            logger.info("❌ System not ready - resolve API key issues first")
        
        logger.info("=" * 60)

def main():
    """Fonction principale"""
    try:
        tester = FreepikKeyTester()
        results = tester.run_comprehensive_test()
        
        print("\n" + "=" * 60)
        print("FREEPIK API KEYS TEST COMPLETED")
        print("=" * 60)
        print(f"📊 Global Success Rate: {results['global_success_rate']:.1f}%")
        print(f"✅ Working Keys: {len([r for r in results['key_results'] if r['status'] != 'failed'])}/{results['total_keys_tested']}")
        print(f"📁 Test images saved in: {Path('freepik_test_results').absolute()}")
        print(f"📄 Detailed logs in: freepik_key_test.log")
        
        if results['global_success_rate'] >= 80:
            print("\n🎉 Your API keys are ready for the waste generator!")
        else:
            print(f"\n⚠️  Only {results['global_success_rate']:.1f}% success rate - check your API key configuration")
        
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    main()