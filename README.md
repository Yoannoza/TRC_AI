# Générateur de Dataset pour Compétition de Robotique

Script spécialisé pour générer des images de déchets pour une compétition de robotique.

## 🎯 Objectif

Générer **126 images de déchets** organisées en:
- **3 catégories**: Ménagers, Dangereux, Recyclables  
- **3 zones**: Résidentielle, Commerciale, Industrielle
- **14 types par zone** × 3 zones × 3 catégories = 126 images

## 📋 Format de sortie

- **Images individuelles**: Générées via API Freepik
- **PDFs organisés**: 3x3 cm par image, 10 répétitions par ligne
- **Format d'impression**: Prêt pour découpage et collage sur cubes

## 🚀 Installation

1. **Installer les dépendances**:
```bash
pip install -r requirements_competition.txt
```

2. **Configurer l'API Freepik**:
```bash
cp .env.example .env
# Éditer .env et ajouter votre clé API Freepik
```

3. **Lancer la génération**:
```bash
python competition_waste_generator.py
```

## 📁 Structure de sortie

```
competition_waste_dataset/
├── images/              # Images individuelles générées
├── pdfs/               # PDFs prêts à imprimer
│   ├── competition_waste_menagers.pdf
│   ├── competition_waste_recyclables.pdf
│   └── competition_waste_dangereux.pdf
├── cache/              # Cache des images (reprise possible)
└── logs/               # Logs de génération
```

## 🎨 Fonctionnalités

✅ **Génération en parallèle** - Utilise l'API Freepik efficacement  
✅ **Cache intelligent** - Reprend là où ça s'est arrêté  
✅ **PDFs optimisés** - Format 3x3 cm, 10 images par ligne  
✅ **Gestion d'erreurs** - Retry automatique, logs détaillés  
✅ **Progress tracking** - Suivi visuel de la progression  
✅ **Organisation claire** - Tri par catégorie et zone  

## 📊 Types de déchets générés

### Ménagers (42 types)
- **Résidentielle**: bouteilles, sacs, canettes, cartons, restes alimentaires
- **Commerciale**: papier bureau, gobelets, emballages, verre, métal
- **Industrielle**: films, cartons ondulés, palettes, bidons

### Recyclables (42 types) 
- **Résidentielle**: journaux, conserves, bouteilles propres, verre, textile
- **Commerciale**: papier blanc, carton propre, aluminium, plastique rigide
- **Industrielle**: métaux ferreux/non-ferreux, plastiques triés, papier-carton

### Dangereux (42 types)
- **Résidentielle**: piles, ampoules, médicaments, produits nettoyage, peintures
- **Commerciale**: cartouches, chimiques bureau, électronique, batteries, huiles
- **Industrielle**: chimiques, médicaux, amiante, radioactifs

## ⚙️ Configuration

Le script est pré-configuré avec 14 types de déchets par zone, optimisés pour une compétition de robotique avec des descriptions réalistes et des prompts de qualité.

## 🖨️ Impression

Les PDFs générés sont optimisés pour:
- **Format A4 standard**
- **Images 3x3 cm précises** (300 DPI)
- **10 répétitions par ligne** pour faciliter le découpage
- **Espacement optimal** pour la découpe

## 🔧 Résolution de problèmes

- **Erreur API**: Vérifiez votre clé Freepik dans `.env`
- **Interruption**: Le cache permet de reprendre automatiquement
- **Qualité images**: Le script optimise automatiquement pour l'impression

## 📞 Support

Le script inclut des logs détaillés dans `competition_waste_generator.log` pour diagnostiquer tout problème.
