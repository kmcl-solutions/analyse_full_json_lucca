# 📊 Analyse Full Json Notes de Frais - Lucca

**Analyse Full Json Notes de Frais** est une application **Streamlit** permettant d'analyser visuellement, auditer et exporter les associations Profils / Natures, les règles de dépenses, et les plans comptables issus d’une extraction JSON Cleemy (Lucca).

---

## 🚀 Fonctionnalités principales

- 📖 **Vue d'ensemble** : Tableau dynamique avec filtres des associations Profils ↔ Natures.
- 👤 **Analyse par Profil** : Exploration des limites, indemnités et règles d’un profil donné.
- 🔬 **Analyse par Nature** : Résumé complet des profils concernés et des règles appliquées à une nature.
- 📏 **Analyse des Limites** : Vue comparative et filtrable de toutes les règles (limites et indemnités).
- 🧾 **Analyse du Plan Comptable** : Cartographie des mappings comptes ↔ natures.

### 📤 Exports disponibles

Toutes les vues principales peuvent être exportées aux formats :

- **CSV** 📥
- **PDF** 📄
- **XLSX (Excel)** 📊

---

## 📦 Installation

### ✅ Prérequis

- Python **3.9+** est recommandé.
- Installation des paquets nécessaires via pip :

```bash
pip install streamlit pandas fpdf2 openpyxl
```

---

## 🛠️ Utilisation

### 1. Préparation des données

Depuis l'application Cleemy (Lucca), exportez un rapport complet au format JSON (généralement nommé `Full.json`).

### 2. Lancer l'application

Placez-vous dans le dossier du projet et exécutez la commande suivante dans votre terminal :

```bash
streamlit run app.py
```

### 3. Interface Streamlit

- Chargez votre fichier `.json` depuis la page d’accueil.
- Naviguez entre les différentes sections via les onglets :
  - Vue d'Ensemble
  - Analyse par Profil
  - Analyse par Nature
  - Analyse des Limites
  - Analyse Plan Comptable
- Appliquez des filtres, explorez les données et exportez les vues de votre choix.

---

## 🎨 Captures d’écran

*(Ajoutez ici vos captures d'écran illustrant chaque onglet pour une meilleure compréhension visuelle.)*

---

## 💡 Personnalisation

Le code est conçu pour être simple à adapter. Vous pouvez facilement modifier :

- Les traductions des périodes dans la constante `PERIOD_TRANSLATION`.
- Les icônes et messages d'alerte dans les fonctions d'affichage (`build_*_ui`).
- Ajouter de nouvelles analyses ou formats d’export en vous inspirant des fonctions existantes.

---

## ❓ Dépannage

- **Problème d’affichage ou erreur** : Assurez-vous d'utiliser la dernière version du script et que toutes les dépendances sont installées.
- **Encodage PDF** : L'export utilise la police standard **Helvetica**. Les caractères très spécifiques non supportés par l'encodage latin-1 (comme certains emojis) seront automatiquement remplacés par un `?` pour garantir la génération du fichier sans erreur.
- **Section de débogage** : En cas d'erreur lors du chargement, une section "Inspecter les données et les erreurs" apparaît en haut de la page pour vous aider à diagnostiquer le problème.

---

## 🤝 Contribution

Les contributions sont les bienvenues !

- Fork du dépôt
- Pull requests pour corrections ou améliorations
- Suggestions de nouvelles fonctionnalités

---

## 📝 Licence

Ce projet est sous licence **MIT**, vous pouvez donc l'utiliser et le modifier librement.

---

## 📧 Contact

Pour toute question, suggestion ou demande d'amélioration, n'hésitez pas à ouvrir une *Issue* sur le dépôt GitHub.

> Application développée pour l’audit et la cartographie rapide des politiques de dépenses Notes de Frais Cleemy / Lucca, notamment dans des contextes multi-profils et multi-plans comptables.
