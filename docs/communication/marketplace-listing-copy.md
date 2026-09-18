# Google Cloud Marketplace Listing : Vibe Guard

**Nom du Produit** : Vibe Guard — AI Agent for Vibe Coding Industrialization & Security  
**Catégorie Marketplace** : Security & Compliance / AI & Machine Learning / Developer Tools  
**Type d'offre** : SaaS & Container Deployment (Google Cloud Run)  
**Partenaire Éditeur** : SFEIR  

---

## 1. Titres & Taglines

* **Titre Produit (50 caractères max)** :  
  `Vibe Guard: Vibe Coding Industrialization Agent`
* **Sous-titre / Tagline (100 caractères max)** :  
  `Automated security, governance, and GCP-native remediation for AI-generated codebases.`
* **Accroche Commerciale (1 ligne)** :  
  *Transform your AI prototypes into production-ready, GCP-compliant applications in seconds.*

---

## 2. Description Courte (Short Overview - 250 mots)

Le développement accéléré par l'IA ("vibe coding" avec Cursor, Lovable, Bolt, v0, Copilot) révolutionne la création logicielle mais génère massivement des failles critiques : clés d'API en clair, routes non authentifiées, appels LLM non gouvernés et conteneurs non isolés. 

**Vibe Guard** est l'agent d'industrialisation autonome conçu pour réconcilier la vélocité du vibe coding et les exigences de sécurité d'entreprise sur Google Cloud.

Alimenté par un moteur déterministe hybride (Semgrep OSS + Gitleaks) et contextualisé par **Gemini 3.8 Flash via Vertex AI**, Vibe Guard audite les bases de code en moins de 15 secondes sans jamais persister le code source. Il génère des plans de remédiation complets et directement exploitables ciblant l'infrastructure managée de Google Cloud : **Cloud Run, Secret Manager, Identity-Aware Proxy (IAP) et Vertex AI**.

Déployable directement dans le tenant Google Cloud privé du client et interconnecté avec votre **Gemini Enterprise App**, Vibe Guard s'achète avec vos crédits d'engagements **EDP (Enterprise Discount Program)** ou à l'usage via la facturation unifiée Google Cloud.

---

## 3. Points Clés & Différenciateurs (Key Features & Highlights)

1. **Détection Déterministe 100 % Reproductible (Zéro Hallucination)** :
   * Analyse statique basée sur des règles industrielles éprouvées (Semgrep & Gitleaks) couvrant 4 familles de risques critiques : `AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO`.
   * Garantie d'un taux de faux positifs minimal et conformité stricte aux exigences d'auditabilité CISO.
2. **Remédiation Contextualisée GCP-Native par Gemini 3.8 Flash** :
   * Ne se limite pas à diagnostiquer : propose le code de correction exact (Terraform, configuration Cloud Run, appels Secret Manager, passerelle Vertex AI).
   * Seuls des extraits de code strictement bornés (10-30 lignes) sont envoyés au LLM, protégeant l'intégrité de la propriété intellectuelle.
3. **Expérience Conversationnelle au sein de votre Gemini Enterprise App** :
   * Intégration transparente via le protocole Agent-to-Agent (A2A) du Google ADK.
   * Les citizen developers, chefs de projet et développeurs dialoguent directement avec l'agent dans leur interface d'entreprise sécurisée pour auditer leur code.
4. **Souveraineté des Données & Confidentialité "Zero-Egress"** :
   * Scan éphémère avec purge garantie de l'espace de travail dès la fin de l'analyse.
   * Déploiement au sein de votre propre projet GCP avec support de VPC Service Controls (VPC-SC) et clés gérées par le client (CMEK).
5. **Achat Simplifié & Financement sur Engagements EDP** :
   * Facturation directement intégrée à votre facture mensuelle Google Cloud.
   * Possibilité de souscrire via une offre privée personnalisée (CPPO) opérée par SFEIR.

---

## 4. Spécifications Techniques & Compatibilité

* **Architecture** : Conteneur Cloud Run sans privilèges root (distroless/minimal), architecture A2A basée sur Google Agent Development Kit (ADK).
* **Modèle IA** : Gemini 3.8 Flash via API Vertex AI du projet client.
* **Langages analysés (V1)** : Python (FastAPI, Flask, Streamlit), TypeScript/JavaScript (Next.js, Express, React), Dockerfile, Terraform.
* **Modes d'ingestion** : URL de dépôt Git (HTTPS, GitHub, GitLab, Cloud Source Repositories) ou archive de code (`.zip`, `.tar.gz`).
* **Format des rapports** : JSON structuré normalisé (compatible SIEM/Security Command Center), Markdown interactif, Agent-to-Agent card.

---

## 5. Grille Tarifaire Marketplace (Pricing Model)

| Formule | Tarif Public Marketplace | Description & Usage |
|---|---|---|
| **Community / Trial** | **Gratuit (0 $)** | Jusqu'à 20 scans / mois sur dépôts publics ou hackathons. Remédiation statique. |
| **Pay-As-You-Go** | **1,99 $ / scan traité** | Facturation à l'usage sur Google Cloud Billing. Remédiation enrichie Gemini 3.8 Flash, support dépôts privés. |
| **Enterprise Private Offer (CPPO)** | **Sur devis (ex: 25k$ - 150k$ / an)** | Déploiement dédié dans le tenant client, nombre de scans illimité, packs de règles personnalisés, support SLA SFEIR, éligible à 100 % au tirage sur engagements **EDP/CUD Google Cloud**. |

---

## 6. Support & Services Professionnels SFEIR

En tant que partenaire premier Google Cloud, **SFEIR** accompagne le déploiement et la personnalisation de Vibe Guard :
* **Vibe Coding Security Assessment (2-3 jours)** : Diagnostic flash de votre parc applicatif d'IA générative et cartographie des risques.
* **Intégration sur-mesure** : Raccordement à votre Security Command Center (SCC), vos pipelines CI/CD Cloud Build / GitLab CI, et déploiement de votre Gemini Enterprise App interne.
* **Support SLA 24/7 et maintenance des packs de règles**.
