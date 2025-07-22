# 📊 Cleemy Analyzer

**Cleemy Analyzer** est une application **Streamlit** permettant d'analyser visuellement, auditer et exporter les associations Profils / Natures, les règles de dépenses, et les plans comptables issus d’une extraction JSON Cleemy (Lucca).

---

## 🚀 Fonctionnalités principales

- 🔍 **Vue d'ensemble** : tableau dynamique avec filtres des associations Profils ↔ Natures.
- 👤 **Analyse détaillée par profil** : exploration des limites, indemnités et règles d’un profil donné.
- 🧮 **Analyse des limites & indemnités** : vue comparative et filtrable multi-profils.
- 🧾 **Analyse du plan comptable** : cartographie des mappings comptes ↔ natures.
- 🧬 **Analyse par nature** : résumé complet des profils concernés et des règles appliquées.

### 📤 Exports disponibles

Toutes les vues peuvent être exportées :

- **CSV** 📥
- **PDF** 📄
- **XLSX (Excel)** 📊

---

## 📦 Installation

### ✅ Prérequis

- Python **3.9+** recommandé
- Packages nécessaires :

```bash
pip install streamlit pandas fpdf2 xlsxwriter
```

---

## 🛠️ Utilisation

### 1. Préparation des données

Depuis Cleemy (Lucca), exportez un rapport complet au format **JSON** (`Full.json`).

### 2. Lancer l'application

```bash
streamlit run app.py
```

### 3. Interface Streamlit

- Uploade ton fichier `.json` depuis la page d’accueil.
- Accède aux différentes sections via la sidebar :
  - Vue d'ensemble
  - Analyse par profil
  - Analyse des limites
  - Analyse plan comptable
  - Analyse par nature
- Applique des filtres, explore, et **exporte** les données.

---

## 🎨 Captures d’écran

*(Ajoutez ici vos captures d'écran illustrant chaque onglet pour une meilleure compréhension visuelle.)*

---

## 💡 Personnalisation

- Les **traductions**, **styles**, **couleurs** et **seuils** sont modifiables dans le code.
- Tu peux facilement ajouter de nouvelles analyses ou formats d’export en t’inspirant des fonctions existantes.

---

## ❓ Dépannage

- **Problème d’affichage** : vérifier que tu utilises bien la dernière version du script.
- **Encodage PDF** : la police `Arial` doit être installée, sinon remplace-la par une autre compatible.
- **Expandeurs Streamlit** : utilisés pour éviter les bugs de container dynamique.

---

## 🤝 Contribution

Les contributions sont **les bienvenues** !

- Fork du repo
- Pull requests
- Suggestions, corrections de bugs, nouvelles vues…

---

## 📝 Licence

Ce projet est sous licence **MIT** (modifiable selon ton contexte).

---

## 📧 Contact

Pour toute question, suggestion ou demande d'amélioration :

**Simon Grossi**  
📧 [simon.grossi@gmail.com](mailto:simon.grossi@gmail.com)  
🔗 [github.com/simongrossi](https://github.com/simongrossi)

---

> Application développée pour l’audit et la cartographie rapide des politiques de dépenses Notes de Frais Cleemy / Lucca, notamment dans des contextes multi-profils et multi-plans comptables.
