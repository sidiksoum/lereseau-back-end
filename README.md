# LeRéseau — Backend API

> Plateforme éducative et professionnelle pour étudiants, mentors et institutions.

## Stack Technique

| Couche | Technologie |
|---|---|
| Framework | FastAPI (Python 3.11+) |
| Base de données | PostgreSQL + SQLAlchemy ORM |
| Migrations | Alembic |
| Auth | JWT (access + refresh token) + OTP Email |
| Temps réel | Socket.IO (python-socketio) |
| Stockage fichiers | AWS S3 |
| Email | SMTP Gmail (FastAPI-Mail) |
| IA Chatbot | OpenRouter API (Google Gemma) |
| Paiement | CinetPay / Stripe |
| Serveur | Uvicorn (ASGI) |

---

## Architecture du Projet

```
app/
├── api/
│   ├── routes/
│   │   ├── auth.py              # Authentification (register, login, OTP, reset)
│   │   ├── v1/                  # Routes utilisateurs
│   │   │   ├── users.py
│   │   │   ├── feed.py
│   │   │   ├── documents.py
│   │   │   ├── opportunities.py
│   │   │   ├── forum.py
│   │   │   ├── network.py
│   │   │   ├── chat.py
│   │   │   ├── notifications.py
│   │   │   ├── chatbot.py
│   │   │   └── publishing.py    # Publication par users Premium
│   │   └── admin/               # Routes admin protégées
│   │       ├── users.py
│   │       ├── forum.py
│   │       ├── publishing.py
│   │       ├── certifications.py
│   │       └── dashboard.py
│   └── dependencies/auth.py     # Guards (get_current_user, require_role)
├── models/                      # Modèles SQLAlchemy
├── schemas/                     # Pydantic schemas
├── services/                    # Logique métier
│   ├── storage.py               # AWS S3
│   ├── email.py                 # SMTP OTP
│   ├── notifications.py         # Push in-app
│   └── chatbot_ia.py            # OpenRouter AI
├── sockets/                     # WebSocket handlers
├── core/
│   ├── config.py                # Settings (.env)
│   └── security.py             # Hash, JWT
└── main.py
```

---

## Modèles de Base de Données

### `users`
| Colonne | Type | Description |
|---|---|---|
| id | String (UUID) | Clé primaire |
| email | String UNIQUE | Email (identifiant) |
| passwordHash | String | Bcrypt hash |
| firstName / lastName | String | Nom complet |
| roleType | Enum | `student` / `professional` / `institution` |
| role | Enum | `USER` / `ADMIN` / `SUPER_ADMIN` |
| isPremium | Boolean | Compte premium actif |
| isEmailVerified | Boolean | Email vérifié via OTP |
| nineaUploaded | Boolean | Certification approuvée |
| kycDocumentUrl | String | Statut demande certification (`PENDING_REQUEST` / `APPROVED`) |
| premiumPaymentMethod | String | Statut premium (`PENDING_REQUEST` / `APPROVED`) |
| avatarUrl / coverUrl | String | Photos profil/couverture |
| skills | JSON | Compétences |
| settings | JSON | Préférences utilisateur |

### `feed_posts`
| Colonne | Type | Description |
|---|---|---|
| id | UUID | PK |
| authorId | FK users | Auteur |
| type | Enum | `TEXT/IMAGE/VIDEO/PDF` |
| status | Enum | `PENDING/APPROVED/REJECTED` |
| attachments | JSON | `[{url, type}]` (images, vidéos ext.) |
| likesCount / commentsCount | Int | Compteurs d'engagement |

### `documents`
| Colonne | Type | Description |
|---|---|---|
| category | String | Catégorie (NOT NULL) |
| tags | JSON | `["IA", "Finance"]` |
| fileUrl | String | URL PDF ou document |
| previewUrl | String | Image de couverture |
| isPremium / price | Bool/Float | Accès payant |
| status | Enum | `PENDING/APPROVED/REJECTED` |

### `forum_channels`, `forum_topics`, `forum_replies`
- Topics créés par users → status `PENDING` en attente validation admin
- Replies : likes + signalements (reportsCount)

### `otp_codes`
| Colonne | Type | Description |
|---|---|---|
| email | String | Email ciblé |
| code | String | Hash bcrypt du code 6 chiffres |
| purpose | Enum | `EMAIL_VERIFICATION` / `PASSWORD_RESET` |
| expires_at | DateTime | Expiry (+10 min) |
| is_used | Boolean | Invalidé après usage |

### `conversations`, `messages` — Messagerie privée
### `notifications` — Notifications in-app
### `network_connections` — Réseau social (amis/mentors)

---

## Variables d'Environnement (.env)

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/lereseaubase
SECRET_KEY=your-secret-key
JWT_EXPIRATION=7d

# AWS S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=lereseau-premium-docs
AWS_REGION=eu-west-3

# OpenRouter AI
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemma-4-31b-it:free

# SMTP Gmail
MAIL_USERNAME=lereseau2026@gmail.com
MAIL_PASSWORD=xxxx xxxx xxxx xxxx   # App Password Gmail
MAIL_FROM=lereseau2026@gmail.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_STARTTLS=True
OTP_EXPIRE_MINUTES=10

# Paiement
CINETPAY_APIKEY=...
STRIPE_SECRET_KEY=...
```

---

## Tous les Endpoints API

### 🔐 Auth — `/api/auth`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| POST | `/register` | Créer un compte + envoi OTP email | — |
| POST | `/verify-email` | Vérifier OTP après inscription | — |
| POST | `/resend-otp` | Renvoyer OTP vérification | — |
| POST | `/login` | Connexion (retourne access + refresh token) | — |
| POST | `/refresh` | Renouveler access token via cookie | — |
| POST | `/logout` | Déconnexion + suppression cookies | ✅ |
| POST | `/forgot-password` | Étape 1 : envoi OTP réinitialisation | — |
| POST | `/verify-reset-otp` | Étape 2 : vérifier OTP, retourne reset_token | — |
| POST | `/reset-password` | Étape 3 : définir nouveau mot de passe | — |

---

### 👤 Users — `/api/users`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/` | Liste tous les users | — |
| GET | `/students` | Liste étudiants | — |
| GET | `/professionals` | Liste professionnels | — |
| GET | `/institutions` | Liste institutions | — |
| GET | `/mentors` | Liste mentors (professionnels) | — |
| GET | `/premium-mentors` | Mentors certifiés + Premium | ✅ Premium |
| GET | `/me` | Profil courant | ✅ |
| PATCH | `/me` | Modifier profil (FormData, avatar, cover) | ✅ |
| POST | `/me/certification-request` | Demander certification mentor/institution | ✅ |
| POST | `/me/premium-request` | Demander activation compte Premium | ✅ |
| POST | `/me/experiences` | Ajouter expérience | ✅ |
| DELETE | `/me/experiences/{id}` | Supprimer expérience | ✅ |
| PATCH | `/me/experiences/{id}` | Modifier expérience | ✅ |
| POST | `/me/educations` | Ajouter formation | ✅ |
| DELETE | `/me/educations/{id}` | Supprimer formation | ✅ |
| PATCH | `/me/educations/{id}` | Modifier formation | ✅ |
| GET | `/{id}` | Profil par ID | ✅ |

---

### 📰 Feed — `/api/feed`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/` | Fil d'actualité chronologique | — |
| POST | `/{id}/like` | Liker/unliker un post | ✅ |
| POST | `/{id}/repost` | Repartager un post | ✅ |
| POST | `/{id}/comments` | Commenter | ✅ |
| GET | `/{id}/comments` | Lire les commentaires | — |

---

### 📚 Documents — `/api/documents`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/` | Liste documents approuvés | — |
| GET | `/{id}` | Détail document | — |
| GET | `/{id}/download` | Télécharger (incrémente compteur) | ✅ |

---

### 🎓 Opportunités — `/api/opportunities`

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Liste opportunités actives |
| GET | `/{id}` | Détail opportunité |

---

### 💬 Forum — `/api/forum`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/channels` | Liste des canaux | — |
| GET | `/channels/{id}/topics` | Topics approuvés d'un canal | — |
| POST | `/channels/{id}/topics` | Créer un topic (→ PENDING) | ✅ |
| GET | `/topics/{id}/replies` | Réponses d'un topic | — |
| POST | `/topics/{id}/replies` | Répondre à un topic | ✅ |
| POST | `/replies/{id}/like` | Liker une réponse | ✅ |
| POST | `/replies/{id}/report` | Signaler une réponse | ✅ |
| PATCH | `/topics/{id}/view` | Incrémenter les vues | — |

---

### 🌐 Réseau — `/api/network`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/friends` | Liste d'amis | ✅ |
| POST | `/friends/{id}/request` | Envoyer demande d'ami | ✅ |
| PATCH | `/friends/{id}/accept` | Accepter une demande | ✅ |
| DELETE | `/friends/{id}` | Supprimer une relation | ✅ |

---

### 💬 Chat Privé — `/api/chat`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/` | Mes conversations | ✅ |
| POST | `/` | Démarrer une conversation | ✅ |
| GET | `/{conversation_id}/messages` | Messages + infos participants | ✅ |
| POST | `/{conversation_id}/messages` | Envoyer un message | ✅ |

---

### 🔔 Notifications — `/api/notifications`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| GET | `/` | Mes notifications | ✅ |
| PATCH | `/{id}/read` | Marquer comme lu | ✅ |
| PATCH | `/read-all` | Tout marquer comme lu | ✅ |

---

### 🤖 Chatbot IA — `/api/chatbot`

| Méthode | Route | Description | Auth |
|---|---|---|---|
| POST | `/ask` | Poser une question (contexte profil + plateforme) | ✅ |

---

### 📢 Publication Premium (Users) — `/api/publishing`

> Réservé aux `professional` et `institution` avec `isPremium = True`

| Méthode | Route | Description |
|---|---|---|
| POST | `/feed` | Publier une annonce (images, vidéo URL) |
| GET | `/feed` | Mes annonces |
| DELETE | `/feed/{id}` | Supprimer mon annonce |
| POST | `/documents` | Publier un document |
| GET | `/documents` | Mes documents |
| PUT | `/documents/{id}` | Modifier mon document |
| DELETE | `/documents/{id}` | Supprimer mon document |

---

### 🛡️ Admin — `/api/admin`

#### Users `/api/admin/users`
| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Tous les users (filtrable par role) |
| GET | `/stats` | Statistiques (total, par type, mentors certifiés) |
| POST | `/create` | Créer un admin |
| PATCH | `/{id}/status` | Bannir/activer un user |
| DELETE | `/{id}` | Supprimer (SUPER_ADMIN) |
| GET | `/certifications/pending` | Demandes certification en attente |
| PATCH | `/certifications/{id}/approve` | Valider certification |
| PATCH | `/certifications/{id}/reject` | Rejeter certification |
| GET | `/premium/pending` | Demandes Premium en attente |
| PATCH | `/premium/{id}/approve` | Activer Premium |
| PATCH | `/premium/{id}/reject` | Désactiver Premium |

#### Forum `/api/admin/forum`
| Méthode | Route | Description |
|---|---|---|
| GET | `/topics` | Topics en attente de validation |
| PATCH | `/topics/{id}/authorize` | Valider un topic |
| DELETE | `/topics/{id}` | Supprimer un topic |
| GET | `/topics/reported` | Topics signalés |
| GET | `/channels` | Tous les canaux |
| POST | `/channels` | Créer un canal (slug auto-généré) |
| PUT | `/channels/{id}` | Modifier un canal |
| DELETE | `/channels/{id}` | Supprimer un canal |

#### Publishing `/api/admin/publishing`
| Méthode | Route | Description |
|---|---|---|
| POST | `/feed` | Publier (images, vidéo URL) |
| PUT | `/feed/{id}` | Modifier |
| DELETE | `/feed/{id}` | Supprimer |
| POST | `/documents` | Publier document |
| PUT | `/documents/{id}` | Modifier |
| DELETE | `/documents/{id}` | Supprimer |
| POST | `/opportunities` | Publier opportunité |
| PUT | `/opportunities/{id}` | Modifier |
| DELETE | `/opportunities/{id}` | Supprimer |

#### Dashboard `/api/admin/dashboard`
| Méthode | Route | Description |
|---|---|---|
| GET | `/stats` | Métriques globales plateforme |

---

## ⚡ WebSocket (Socket.IO)

| Événement | Description |
|---|---|
| `connect` | Connexion, rejoint la room globale |
| `disconnect` | Déconnexion |
| `send_message` | Envoyer un message privé |
| `receive_message` | Recevoir un message |
| `notification` | Notification temps réel |

---

## 🔮 Fonctionnalités à Venir

### 1. Algorithme de Recommandation (LinkedIn/TikTok Style)

**Score de Pertinence :**

```
Score = (likes + reposts) × TypeFactor / ancienneté_heures^1.5
```

- `TypeFactor` : x2 pour Bourses, x1.5 pour Documents, x1 pour posts texte
- Fraîcheur : les nouveaux contenus remontent automatiquement

**Implémentation Backend prévue :**

```python
# GET /api/feed/recommended
def get_recommended_feed(db, current_user):
    now = datetime.now(timezone.utc)
    posts = db.query(FeedPost).filter(FeedPost.status == "APPROVED").all()
    
    user_tags = set(current_user.skills or [])
    
    scored = []
    for post in posts:
        hours_old = max((now - post.createdAt).total_seconds() / 3600, 0.1)
        type_factor = 2.0 if post.type == "RECOMMENDED_OPPORTUNITY" else 1.0
        engagement = post.likesCount + post.commentsCount
        
        # Affinité par tags (si le contenu a des tags correspondant au profil)
        post_tags = set(post.tags or []) if hasattr(post, 'tags') else set()
        tag_affinity = len(user_tags & post_tags) / max(len(user_tags), 1)
        
        score = ((engagement * type_factor) / (hours_old ** 1.5)) + (tag_affinity * 10)
        scored.append((score, post))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:50]]
```

**Profilage par Tags :**
- Chaque Document/Post est taggé (`["IA", "Finance", "Droit"]`)
- L'utilisateur a des `skills` identiques
- Le feed recommandé remonte en priorité les contenus dont les tags matchent à ≥ 80% les skills du profil

### 2. Notifications Push Email (LinkedIn Style)

Templates email automatiques prévus :
- ✉️ **Nouvelle demande d'ami** : "X vous a envoyé une invitation"
- 👍 **Like sur post** : "X a aimé votre publication"
- 🎓 **Nouveau mentor recommandé** : "Découvrez des mentors dans votre domaine"
- 📚 **Nouveau document** : "Un nouveau document dans votre domaine vient d'être ajouté"
- 🏆 **Certification approuvée** : "Félicitations ! Votre statut de Mentor Certifié est activé"
- 💎 **Premium activé** : "Votre compte Premium est maintenant actif"
- 🎯 **Nouvelle bourse** : Alertes hebdomadaires sur les nouvelles opportunités
- 💰 **Nouvelle offre d'emploi** : Alertes hebdomadaires sur les nouvelles offres d'emploi

### 3. Système de Points / Gamification
- Points gagnés : post liké, commentaire, connexion réseau, téléchargement document
- Badges : "Expert IA", "Top Mentor", "Contributeur Actif"
- Classement : Top contributeurs par domaine

### 4. 🕷️ Scraping Automatique des Bourses d'Études

Automatisation de la collecte de bourses depuis des plateformes officielles pour alimenter la base de données sans intervention manuelle.

**Plateformes ciblées :**
| Plateforme | Type de bourse |
|---|---|
| [Campus France](https://www.campusfrance.org) | Bourses gouvernementales France |
| [Scholarship Portal](https://www.scholarshipportal.com) | Bourses internationales |
| [DAAD](https://www.daad.de) | Bourses allemandes |
| [British Council](https://www.britishcouncil.org) | Bourses UK |
| [AUF](https://www.auf.org) | Agence Universitaire Francophonie |
| [Mastercard Foundation](https://mastercardfdn.org/scholars) | Bourses Afrique |
| Sites gouvernementaux locaux | Bourses nationales |

**Architecture technique prévue :**

```python
# app/services/scraper.py
import httpx
from bs4 import BeautifulSoup
from app.models.opportunity import Opportunity

class ScholarshipScraper:
    SOURCES = [
        {"name": "Campus France", "url": "https://www.campusfrance.org/bourses", "parser": "parse_campus_france"},
        {"name": "AUF", "url": "https://www.auf.org/offres/", "parser": "parse_auf"},
    ]

    @staticmethod
    async def scrape_all(db) -> dict:
        results = {"added": 0, "duplicates": 0, "errors": 0}
        async with httpx.AsyncClient(timeout=30) as client:
            for source in ScholarshipScraper.SOURCES:
                try:
                    resp = await client.get(source["url"])
                    scholarships = ScholarshipScraper.parse(resp.text, source["name"])
                    for s in scholarships:
                        # Éviter les doublons via titre + organisation
                        exists = db.query(Opportunity).filter(
                            Opportunity.title == s["title"],
                            Opportunity.organization == s["organization"]
                        ).first()
                        if not exists:
                            opp = Opportunity(**s, isActive=True)
                            db.add(opp)
                            results["added"] += 1
                        else:
                            results["duplicates"] += 1
                    db.commit()
                except Exception as e:
                    results["errors"] += 1
        return results
```

**Endpoints Admin prévus :**
| Méthode | Route | Description |
|---|---|---|
| POST | `/api/admin/scraper/run` | Lancer un scraping manuel immédiat |
| GET | `/api/admin/scraper/logs` | Voir les logs des dernières exécutions |
| PATCH | `/api/admin/scraper/schedule` | Configurer la fréquence (quotidien/hebdo) |

**Planification CRON (3h du matin, tous les jours) :**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=3, minute=0)
async def auto_scrape():
    db = SessionLocal()
    result = await ScholarshipScraper.scrape_all(db)
    print(f"[SCRAPER] {result}")
    db.close()

scheduler.start()
```

**Dépendances à ajouter :** `pip install httpx beautifulsoup4 lxml apscheduler`

**Stratégies anti-blocage :**
- Rotation de `User-Agent` pour éviter les bans
- Délai aléatoire de 1–3 secondes entre les requêtes
- Cache des URLs déjà scrapées pour éviter les doublons
- Respect des fichiers `robots.txt` des sites sources

---

## 🚀 DevOps & Déploiement

### Lancement Local

```bash
# 1. Cloner le projet
git clone https://github.com/lereseau/backend.git
cd backend

# 2. Créer et activer l'environnement virtuel
python -m venv .venv
.\.venv\Scripts\activate        # Windows
source .venv/bin/activate        # Linux/Mac

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
# Remplir les valeurs dans .env

# 5. Lancer les migrations
alembic upgrade head

# 6. Démarrer le serveur
uvicorn app.main:sio_app --reload
```

### Variables Obligatoires avant Production

| Variable | Comment obtenir |
|---|---|
| `DATABASE_URL` | URL PostgreSQL de production |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `AWS_*` | Console AWS > IAM > S3 |
| `MAIL_PASSWORD` | [Gmail App Passwords](https://myaccount.google.com/apppasswords) |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |


## 📊 Documentation Interactive

Une fois le serveur lancé, accédez à :
- **Swagger UI** : `http://localhost:8000/docs`
- **ReDoc** : `http://localhost:8000/redoc`

---

*Développé avec ❤️ pour l'écosystème éducatif et professionnel.*
