# HealthGuard IA  Guide des Interfaces (Lo-Fi)

Ce document décrit chaque écran du prototype, son rôle, ses composants clés,  
et indique les fichiers + numéros de lignes à capturer pour la documentation.

---

## Vue d'ensemble du flux de navigation

```
E1 (Connexion)
    │
    ▼
E2 (Tableau de bord)  ◄──────────────────────┐
    │                                         │
    ├──► E3 (Nouvelle consultation)           │
    │         │                               │
    │         ▼                               │
    │    E4 (Arbre décisionnel)               │
    │         │                               │
    │         ▼                               │
    │    E5 (Résultat diagnostic) ────────────┘
    │
    ├──► E6 (Dossiers patients)
    │
    └──► E7 (Paramètres & Sync)
```

---

## E1  Écran de Connexion

**Fichier :** `prototype/screens/e1_login.html`  
**Rôle :** Authentification multi-comptes avec PIN. Premier écran affiché au démarrage.

### Composants principaux

| Composant | Description | Lignes HTML |
|-----------|-------------|-------------|
| Logo + titre | "🏥 HealthGuard IA" centré | 17–24 |
| Liste agents | Cartes cliquables avec avatar initiale, nom, rôle, badge PIN | 36–44 |
| Badge PIN démo | Fond bleu clair, "PIN : 246810" pour les comptes par défaut | JS l. 204–213 |
| Clavier PIN | Grille 3×4 de touches numériques + points indicateurs | 76–100 |
| Bouton urgence | Rouge, accès sans identification | 104–108 |
| Modal ajout compte | Formulaire nom / rôle / PIN 6 chiffres | 112–148 |
| Modal urgence | Popup de confirmation (hgConfirm) | JS l. 315–327 |

### Logique JavaScript clé

| Fonction | Lignes JS | Description |
|----------|-----------|-------------|
| `getAgents()` | 188–197 | Charge agents depuis localStorage, initialise par défaut |
| `renderAgents()` | 200–216 | Affiche les cartes avec badge PIN pour comptes démo |
| `loadAgents()` | 218–241 | Enrichit depuis l'API PostgreSQL si disponible |
| `selectAgent()` | 243–253 | Passe à l'étape saisie PIN |
| `validatePin()` | 281–295 | Vérifie le PIN et ouvre la session |
| `saveNewAgent()` | 330–356 | Crée un nouveau compte (local + PostgreSQL) |

### Captures recommandées
- **Zoomer sur la carte agent** (les 2 cartes avec badge PIN bleu "PIN : 246810")
- **Cliquer sur une carte** → affiche le clavier PIN avec le nom de l'agent en sous-titre
- **Cliquer sur "Accès Urgence"** → affiche le modal de confirmation Material Design

---

## E2  Tableau de Bord

**Fichier :** `prototype/screens/e2_dashboard.html`  
**Rôle :** Écran d'accueil après connexion. Vue synthétique de l'activité du jour.

### Composants principaux

| Composant | Description | Lignes HTML |
|-----------|-------------|-------------|
| Barre de statut | Heure + badge réseau EN LIGNE/HORS LIGNE | 10–14 |
| En-tête | Nom app + nom agent connecté + bouton paramètres | 16–23 |
| Alerte sync | Bandeau orange si retard > 48h | 25–28 |
| Grille stats | 3 chiffres : Consultations / Urgences / En attente | 30–44 |
| Grille actions | 4 boutons : Consultation / Patient / Sync / Paramètres | 47–66 |
| Liste consultations | Dots colorés + diagnostic + patient + date | 68–86 |
| Source indicator | "(base centrale)" ou "(local)" selon source des données | JS l. 59 |

### Logique de chargement (`loadDashboard`)

```
loadDashboard()
  │
  ├── Stats : localStorage (toujours)
  │
  ├── Nom agent : localStorage.hg_agent_nom
  │
  └── Liste consultations :
        ├── Tentative fetch GET /api/v1/consultations/recent (timeout 2.5s)
        │     └── Si réussi → affiche "(base centrale)"
        └── Fallback → localStorage → affiche "(local)"
```

**Lignes JavaScript :** `e2_dashboard.html` lignes 98–211

### Comportement responsive
- **Mobile** : layout 1 colonne, stats en grille 3 col
- **Desktop (≥768px)** : sidebar injectée par `nav.js`, contenu décalé de 230px
- **Tablette étroite (768–900px)** : sidebar réduite en icônes

---

## E3  Nouvelle Consultation

**Fichier :** `prototype/screens/e3_consultation.html`  
**Rôle :** Saisie du patient et de ses symptômes. Étape 1 du diagnostic.

### Composants principaux

| Composant | Description | Lignes HTML |
|-----------|-------------|-------------|
| Steppeur | 3 étapes : Patient → Symptômes → Résultat | 17–35 |
| Formulaire patient | Nom, sexe, sélecteur d'âge (bébé/enfant/adulte/senior), poids | 39–110 |
| Grille symptômes | Boutons toggle 2×4 col avec icônes | 116–150 |
| Vitaux | Température (slider + champ), SpO2, fréq. resp., MUAC | 153–220 |
| Alerte SpO2 | Bandeau rouge si valeur < 90% | ~l.220 |
| Jauge MUAC | Barre colorée rouge/orange/vert selon valeur | ~l.200 |
| Bouton soumettre | "🔬 Analyser les Symptômes" | ~l.230 |

### Alertes remplacées par modals

| Ancienne fonction | Nouveau comportement | Lignes JS |
|-------------------|---------------------|-----------|
| `alert('Nom manquant')` | `hgAlert('...', 'Champ manquant', '⚠️')` | 335 |
| `alert('Âge manquant')` | `hgAlert('...', 'Champ manquant', '⚠️')` | 336 |

---

## E4  Arbre Décisionnel

**Fichier :** `prototype/screens/e4_decision_tree.html`  
**Rôle :** Questions guidées basées sur PCIME. Étape 2 du diagnostic.

### Composants principaux

| Composant | Description | Lignes HTML |
|-----------|-------------|-------------|
| En-tête | "Arbre Décisionnel" + bouton retour | 10–20 |
| Compteur progression | "Étape X / N" en haut à droite | ~l.22 |
| Question principale | Texte grand, lisible (22px) | ~l.30 |
| Aide contextuelle | Texte italique gris sous la question | ~l.35 |
| Boutons OUI/NON | Grande grille 1×2, 64px hauteur, vert/rouge | ~l.40 |
| Pré-remplissage | Si symptôme déjà saisi en E3, la réponse est pré-cochée | JS l.200+ |

### Logique de questions
Définie dans `src/decision_engine/tree_navigator.py`.  
Le prototype simule les questions localement en JS (l.80–250 de e4).

---

## E5  Résultat du Diagnostic

**Fichier :** `prototype/screens/e5_result.html`  
**Rôle :** Affichage du résultat, recommandations, et sauvegarde. Étape 3.

### Composants principaux

| Composant | Description | Lignes HTML |
|-----------|-------------|-------------|
| Bandeau alerte | Couleur dynamique (ROUGE/ORANGE/VERT) + icône + diagnostic | ~l.15 |
| Bloc diagnostic principal | Maladie + probabilité % + gravité | ~l.40 |
| Diagnostic différentiel | 2e diagnostic possible si probabilité > 20% | ~l.55 |
| Recommandations | 3 points d'action, médicaments, transfert | ~l.70 |
| Score gravité | Numérique 0–10 + couleur | ~l.90 |
| Boutons action | "💾 Enregistrer le Dossier" + "🩺 Nouvelle Consultation" | ~l.100 |

### Logique de simulation clinique

La fonction `runDiagnostic(data)` dans e5 (JS l.200–400) :
1. Calcule un score de gravité basé sur les symptômes
2. Applique les règles cliniques PCIME (convulsions → paludisme grave, MUAC < 115mm → malnutrition sévère…)
3. Retourne : `{ diagnostic, code, gravite, couleur, proba, source, points, traitement }`

### Modal remplacée

| Ancienne fonction | Nouveau comportement | Lignes JS |
|------------------|---------------------|-----------|
| `alert('Dossier sauvegardé...')` + redirect | `hgAlert(...)` puis `setTimeout(redirect, 1800)` | ~l.487–492 |

---

## E6  Dossiers Patients

**Fichier :** `prototype/screens/e6_patient_record.html`  
**Rôle :** Recherche et consultation des dossiers patients.

### Composants principaux

| Composant | Description | Lignes HTML |
|-----------|-------------|-------------|
| Barre de recherche | Filtre en temps réel par nom | ~l.20 |
| Liste patients | Cartes avec avatar coloré + nom + date dernière consultation | ~l.35 |
| Onglets fiche | "Informations" / "Consultations" | ~l.70 |
| Historique | Liste chronologique des consultations avec dot coloré | ~l.90 |

### Source de données
Chargé depuis `localStorage.hg_consultations` en JS.  
Groupé par `patient_nom` pour créer les fiches.

---

## E7  Paramètres & Synchronisation

**Fichier :** `prototype/screens/e7_settings.html`  
**Rôle :** Gestion de la sync, sécurité, et informations système.

### Sections et composants

| Section | Composant | Lignes HTML |
|---------|-----------|-------------|
| Sync | Statut PostgreSQL + bouton "Synchroniser maintenant" + barre progression | ~l.20–60 |
| Sync | Compteur "X consultations en attente" | ~l.50 |
| Sécurité | Changer PIN (ouvre modal PIN) | ~l.80 |
| Sécurité | Journal d'audit (ouvre modal liste) | ~l.85 |
| Sécurité | Exporter données JSON | ~l.90 |
| IA | Informations modèle (ouvre modal tableau) | ~l.95 |
| Danger | Réinitialiser les données (double confirmation) | ~l.100 |

### Modals remplacées

| Ancienne fonction | Nouveau modal | Lignes JS |
|------------------|---------------|-----------|
| `alert('PIN modifié')` | `hgAlert('...', 'PIN modifié', '✅')` | ~l.408 |
| `alert(journal)` | `hgAlert(lignes, 'Journal d\'audit', '📋')` | ~l.413–419 |
| `alert(infos modèle)` | `hgAlert('<table>...</table>', '...', '🤖', true)` | ~l.421–438 |
| `confirm()+confirm()` | `hgConfirm()` imbriqués avec bouton rouge "Supprimer" | ~l.439–449 |

---

## Système de Navigation (nav.js)

**Fichier :** `prototype/js/nav.js`  
**Inclus dans :** Tous les écrans E1–E7

### Responsabilités

**1. Système modal (`hgAlert` / `hgConfirm`)**
- Remplace `window.alert()` et `window.confirm()` partout dans l'app
- Style Material Design 3 (animation slide-up, overlay sombre)
- Lignes nav.js : 14–100

**2. Sidebar desktop (≥768px)**
- `_initDesktopLayout()` : wraps le contenu dans `.hg-main`, injecte la sidebar fixe
- Lignes nav.js : 165–182

**3. Sidebar mobile (<768px)**
- `_initMobileNav()` : injecte sidebar off-canvas + backdrop + bouton hamburger ☰
- La sidebar glisse depuis la gauche en 260ms
- Fermeture : clic backdrop, clic lien nav, touche Échap
- Lignes nav.js : 184–224

**4. Indicateur de connectivité**
- Surveille `navigator.onLine` et les événements online/offline
- Affiche "● En ligne" (vert) ou "● Hors ligne" (orange) dans la sidebar
- Lignes nav.js : 153–162

---

## Design System CSS

**Fichier :** `prototype/css/healthguard.css`

### Variables principales (lignes 7–42)
```css
--color-rouge: #D32F2F    /* urgence critique */
--color-orange: #F57C00   /* attention modérée */
--color-vert: #388E3C     /* cas bénin */
--color-primary: #1565C0  /* bleu médical */
--sidebar-width: 230px    /* largeur sidebar desktop */
```

### Composants CSS documentés

| Composant | Lignes CSS | Description |
|-----------|-----------|-------------|
| Variables | 7–42 | Palette couleurs + typographie |
| Boutons `.btn` | 164–218 | Variants primary/danger/warning/success |
| Clavier PIN | 288–330 | Grille 3×4 + dots indicateurs |
| Grille symptômes | 253–286 | Boutons toggle avec état actif |
| Badges gravité | 397–410 | Rouge/orange/vert chips |
| Liste consultations | 412–438 | Dots colorés + info |
| Sidebar base | ~l.690 | Styles partagés mobile+desktop |
| Modal système | ~l.684 | Overlay + sheet + animations |
| Desktop ≥768px | ~l.750 | Sidebar fixe + `.hg-main` |
| Tablette 768–900px | ~l.790 | Mode icônes seules |
| Tablette 901–1023px | ~l.805 | Sidebar 190px |

---

## Endpoints API documentés

**Fichier :** `src/api/app.py`

| Méthode | Route | Lignes | Rôle |
|---------|-------|--------|------|
| GET | `/` | 611–614 | Redirige vers E1 |
| GET | `/api/v1/health` | 124–147 | Santé du système |
| POST | `/api/v1/diagnostic/new` | 150–242 | Nouveau diagnostic |
| POST | `/api/v1/patients/new` | 262–282 | Créer patient |
| GET | `/api/v1/patients/{id}` | 285–324 | Fiche patient |
| GET | `/api/v1/consultations/recent` | 468–508 | 10 dernières (PostgreSQL) |
| GET | `/api/v1/agents` | 511–544 | Liste agents |
| POST | `/api/v1/agents/new` | 547–581 | Créer agent |
| GET | `/api/v1/sync/status` | 327–348 | Statut sync |
| POST | `/api/v1/sync/from-browser` | 351–465 | Sync localStorage → PostgreSQL |
| POST | `/api/v1/sync/trigger` | 584–608 | Sync SQLite → PostgreSQL |
