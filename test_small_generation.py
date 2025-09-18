#!/usr/bin/env python3
"""
Version simplifiée pour tester avec quelques images seulement
"""

import os
import time
from pathlib import Path
from competition_waste_generator import CompetitionDatasetGenerator, CompetitionWasteItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_small_generation():
    """Génère seulement quelques images de test"""
    
    print("🧪 Testing with small dataset (6 images)...")
    
    # Créer un générateur personnalisé
    output_dir = Path("test_competition_dataset")
    
    class TestGenerator(CompetitionDatasetGenerator):
        def _load_waste_configuration(self):
            """Configuration réduite pour les tests"""
            return [
                # 2 images par catégorie
                CompetitionWasteItem("bouteille_plastique", "menagers", "residentielle",
                                   "Bouteille en plastique domestique", 
                                   ["transparent", "bleu"], ["PET"], ["bouteille"]),
                CompetitionWasteItem("sac_plastique", "menagers", "residentielle",
                                   "Sac plastique de courses",
                                   ["blanc", "noir"], ["polyéthylène"], ["sac"]),
                
                CompetitionWasteItem("papier_blanc", "recyclables", "commerciale",
                                   "Papier blanc de bureau",
                                   ["blanc"], ["papier"], ["feuille"]),
                CompetitionWasteItem("carton_propre", "recyclables", "commerciale",
                                   "Carton d'emballage propre",
                                   ["brun"], ["carton"], ["boîte"]),
                
                CompetitionWasteItem("pile_batterie", "dangereux", "residentielle",
                                   "Piles et petites batteries",
                                   ["noir", "argenté"], ["lithium"], ["cylindrique"]),
                CompetitionWasteItem("produit_nettoyage", "dangereux", "residentielle",
                                   "Produits de nettoyage ménagers",
                                   ["coloré"], ["plastique"], ["flacon"])
            ]
    
    # Lancer la génération de test
    generator = TestGenerator(str(output_dir))
    result = generator.run_full_generation()
    
    if result["success"]:
        print(f"\n🎉 Test successful!")
        print(f"📊 Generated: {result['generated_images']}/{result['total_items']} images")
        print(f"📄 PDFs: {result['generated_pdfs']}")
        print(f"⏱️  Time: {result['elapsed_time']:.1f}s")
        print(f"📁 Check: {output_dir}/")
        
        # Lister les fichiers générés
        if output_dir.exists():
            print("\n📋 Generated files:")
            for pdf_file in (output_dir / "pdfs").glob("*.pdf"):
                print(f"  📄 {pdf_file.name}")
            
            image_count = len(list((output_dir / "images").glob("*")))
            print(f"  🖼️  {image_count} images in cache/")
        
        return True
    else:
        print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
        return False

if __name__ == "__main__":
    success = test_small_generation()
    
    if success:
        print("\n" + "="*60)
        print("✅ Small test successful! Ready for full generation:")
        print("python3 competition_waste_generator.py")
        print("="*60)
    else:
        print("\n❌ Test failed. Check the logs for details.")
