# Plan d'implémentation — Agent d'industrialisation du vibe coding (MVP V1)

> ⛔ **Statut : superseded (2026-09-18).** Ce plan est remplacé par la spécification normative
> [`docs/SPEC.md`](docs/SPEC.md), qui pilote désormais le développement (spec-driven development).
> Ce fichier est conservé pour l'historique du découpage en phases. **En cas de contradiction, `docs/SPEC.md` prime.**

> Document destiné à un agent de développement (Antigravity). Il se lit de haut en bas : contraintes, décisions, puis phases. Chaque phase se termine par un **gate** — ne pas enchaîner sur la phase suivante tant que le gate n'est pas vert. Toute décision non listée ici se prend en écrivant une ADR (voir §9) et en la soumettant avant implémentation.

Version : 0.1 — 2026-09-18
Référence : PRD "Agent d'industrialisation du vibe coding" (sections numérotées §PRD-x ci-dessous)

---

## 1. Objectif du MVP

Un agent qui prend en entrée le code source d'une application générée par IA ("vibe codée") et produit :

1. un **rapport de non-conformité priorisé** (auth, secrets, gouvernance LLM, isolation réseau — §PRD-1),
2. une **proposition de remédiation textuelle** par non-conformité (§PRD-4.5),
3. exposé comme **agent A2A** déployable sur Google Cloud, conforme aux critères d'éligibilité du AI Agent Ecosystem Program (§PRD-6).

Ce que le MVP ne fait pas (§PRD-2) : exécuter le code scanné, générer/appliquer des patches, remplacer une revue sécurité humaine, gérer un workflow d'approbation IT.

---

## 2. Contraintes non négociables

| # | Contrainte | Conséquence pour l'implémentation |
|---|---|---|
| C1 | Analyse **statique uniquement** | Aucun `subprocess` sur le code scanné, aucune installation de ses dépendances, aucun build. Le code scanné est de la donnée, jamais de l'exécutable. |
| C2 | Le code scanné est **sensible** | Pas de persistance au-delà du scan (répertoire temporaire, purge en `finally`). Aucun envoi de code brut à un modèle : seuls des **extraits** (fenêtre autour d'un finding, taille bornée) transitent vers Gemini. |
| C3 | Réutiliser l'**open source** plutôt que réécrire | Moteur de détection = outils OSS existants orchestrés (§3, ADR-002). Pas de parseur maison. |
| C4 | Référentiel de règles **déclaratif et extensible** | Format YAML documenté ; un client peut ajouter une règle sans toucher au code Python (§PRD-4.2, §PRD-5). |
| C5 | Cible **GCP-natif** pour le jeu de règles V1 | Les remédiations proposées référencent Cloud Run/GKE, IAP, Secret Manager, Vertex AI comme passerelle LLM (§PRD-5). |
| C6 | Traçabilité | Chaque scan produit un enregistrement : règles évaluées, version du pack, horodatage, identifiant de l'appelant (§PRD-5). |
| C7 | Pas de chiffre inventé | Aucune cible de performance ou de précision dans le code/doc tant qu'elle n'a pas été mesurée sur les fixtures (§PRD-7). |

---

## 3. Décisions d'architecture (ADR-lite)

Statut de chaque décision : **proposée** — à confirmer par le porteur du produit avant Phase 1. Formaliser chacune en ADR dans `docs/adr/` (§9).

| ADR | Décision proposée | Justification | Alternatives écartées (à ce stade) |
|---|---|---|---|
| ADR-001 | **Python 3.12**, gestion de dépendances `uv`, lint/format `ruff`, tests `pytest` | Écosystème natif de Google ADK et de Semgrep ; stack cohérente avec le déploiement Vertex AI | TypeScript (ADK JS existe mais moins mûr côté outillage sécurité) |
| ADR-002 | Moteur de détection = **Semgrep OSS** (règles code) + **gitleaks** (secrets), orchestrés depuis Python | Semgrep écrit ses règles en YAML → alignement direct avec C4 ; gitleaks est la référence OSS secrets | Écrire des détecteurs regex maison (fragile, C3) ; CodeQL (licence non compatible usage commercial) |
| ADR-003 | Format de pack de règles = **YAML propriétaire léger** qui *enveloppe* une règle Semgrep/gitleaks et ajoute les métadonnées produit (sévérité, famille, justification, exemple, remédiation GCP) | Sépare "comment détecter" (délégué à l'OSS) de "pourquoi c'est un problème et comment corriger" (valeur du produit) | Utiliser les métadonnées Semgrep brutes (insuffisantes pour la remédiation) |
| ADR-004 | Framework agent = **Google ADK (Python)**, modèle **Gemini via Vertex AI** | Critère d'éligibilité Marketplace (§PRD-6) ; ADK expose nativement un agent en A2A | LangGraph/CrewAI (n'apporte rien sur le critère Marketplace) |
| ADR-005 | Rôle de Gemini dans le MVP : (a) **rédaction de la remédiation** contextualisée à partir du finding + extrait borné, (b) **déduplication/regroupement** des findings redondants. **Pas** de détection par LLM en V1 | Déterminisme de la détection (testable), LLM là où il apporte de la valeur (langage naturel) | Détection "zero-rule" par LLM (non reproductible, non testable, hors C7) |
| ADR-006 | Déploiement **Cloud Run** (service HTTP A2A), image sans shell, utilisateur non-root, Semgrep/gitleaks embarqués dans l'image | Cible GCP-natif, cohérence avec les remédiations que l'agent recommande lui-même | GKE (surdimensionné pour un MVP) |
| ADR-007 | Ingestion V1 = **URL de dépôt Git** (clone `--depth 1`, HTTPS + token optionnel) **ou archive** (`.zip`/`.tar.gz`, taille bornée) | §PRD-4.1 | Intégration GitHub App / webhooks (V2) |
| ADR-008 | Périmètre langages V1 = **Python** (FastAPI, Flask, Streamlit) et **JavaScript/TypeScript** (Express, Next.js) + **Dockerfile** et **Terraform** pour la famille NET-ISO | Stacks dominantes des outils de génération IA grand public | Java/Go/.NET (V2, sur demande) |

**Point ouvert (bloquant pour Phase 4, pas avant)** : le critère Marketplace "usage de Vertex AI au-delà du simple appel LLM" (§PRD-6) n'est pas couvert par ADR-005. Candidats à évaluer en Phase 4 : Vertex AI Evaluation pour la boucle de qualité des remédiations, ou Vertex AI Search sur la base de règles. Ne rien implémenter sur ce point avant confirmation avec Google.

---

## 4. Structure du dépôt

```
vibe-guard/                          # nom de travail, à renommer
├── README.md
├── pyproject.toml
├── docs/
│   ├── adr/                         # une ADR par décision (§9)
│   ├── rule-pack-format.md          # spec du format YAML (livrable Phase 1)
│   └── report-schema.md             # spec du rapport JSON (livrable Phase 3)
├── rules/                           # le référentiel, versionné indépendamment du code
│   ├── pack.yaml                    # manifeste : version, familles, liste des règles
│   ├── auth/
│   ├── secrets/
│   ├── llm-gov/
│   └── net-iso/
├── src/vibe_guard/
│   ├── ingest/                      # git clone / extraction archive, purge
│   ├── rules/                       # chargement + validation du pack (schéma)
│   ├── engine/                      # orchestration semgrep / gitleaks, normalisation
│   ├── report/                      # modèle Finding/Report, priorisation, rendu
│   ├── remediation/                 # appel Gemini (ADR-005), prompts versionnés
│   ├── agent/                       # ADK agent, agent card A2A, serveur
│   └── audit/                       # trace de scan (C6)
├── fixtures/                        # apps "vibe codées" de test
│   ├── nonconform/                  # chaque fixture = 1 app + findings.expected.yaml
│   └── conform/                     # apps propres : zéro finding attendu
├── tests/
│   ├── unit/
│   ├── integration/                 # scan complet sur fixtures
│   └── eval/                        # gates mesurables (§6)
├── deploy/
│   ├── Dockerfile
│   └── cloudrun.yaml
└── .github/workflows/ci.yaml
```

---

## 5. Phases et tâches

### Phase 0 — Bootstrap (½ journée)

- [ ] Initialiser le dépôt selon §4, `uv`, `ruff`, `pytest`, pre-commit
- [ ] CI : lint + tests unitaires sur chaque PR
- [ ] Rédiger ADR-001 à ADR-008 dans `docs/adr/` avec statut `proposed`
- [ ] Vérifier que `semgrep --version` et `gitleaks version` tournent dans l'image de dev

**Gate 0** : CI verte sur un test trivial ; les 8 ADR existent.

### Phase 1 — Référentiel de règles v0

- [ ] Écrire `docs/rule-pack-format.md` : schéma YAML d'une règle (id, famille, sévérité `critical|high|medium|low`, titre, justification, exemple de non-conformité, remédiation GCP-natif, référence vers la règle Semgrep ou le détecteur gitleaks sous-jacent)
- [ ] Implémenter le chargeur + validation de schéma (`src/vibe_guard/rules/`) ; un pack invalide échoue explicitement avec le chemin de l'erreur
- [ ] Écrire les règles v0, **minimum 3 par famille** :
  - **AUTH** : route HTTP exposée sans middleware/décorateur d'auth (FastAPI/Flask/Express) ; auth "maison" par comparaison de mot de passe en clair ; absence de config IAP/identity sur un service exposé en Terraform
  - **SECRETS** : délégué à gitleaks (config par défaut + règles ajoutées pour clés Gemini/Vertex, OpenAI, Anthropic) ; fichier `.env` versionné ; secret passé en variable d'environnement en clair dans un Dockerfile/Terraform
  - **LLM-GOV** : appel direct à une API LLM (`api.openai.com`, `generativelanguage.googleapis.com`, SDK Anthropic/OpenAI) depuis le code applicatif sans passer par une passerelle configurée ; appel LLM sans timeout ; concaténation directe d'entrée utilisateur dans un prompt système
  - **NET-ISO** : Cloud Run `ingress = ALL` sans IAP en Terraform ; bind `0.0.0.0` sans reverse proxy ; conteneur exécuté en root ; port debug exposé
- [ ] Créer **au moins 4 fixtures non conformes** (1 par famille minimum, une fixture peut cumuler) avec `findings.expected.yaml`, et **2 fixtures conformes**
- [ ] Rédiger pour chaque règle la remédiation GCP-natif *statique* (celle que Gemini enrichira en Phase 3 — le produit doit rester utile sans LLM)

**Gate 1** : le pack se charge sans erreur ; chaque règle a ses 6 champs de métadonnées renseignés ; chaque fixture non conforme a un `findings.expected.yaml` relu par le porteur du produit.

### Phase 2 — Moteur de scan

- [ ] `ingest/` : clone shallow ou extraction d'archive dans un répertoire temporaire ; limites (taille, nombre de fichiers) ; purge garantie en `finally` (C2)
- [ ] `engine/` : exécuter Semgrep avec les règles du pack et gitleaks sur le répertoire ; parser leurs sorties JSON ; normaliser en objets `Finding` (règle, fichier, ligne, extrait borné, sévérité héritée du pack)
- [ ] Gestion d'erreurs : un outil qui échoue produit un `Finding` de type `tool_error`, le scan continue
- [ ] `audit/` : enregistrement de scan (C6) — version du pack, règles évaluées, durée, appelant, sans le code
- [ ] Tests d'intégration : scan complet de chaque fixture

**Gate 2** (eval mesurable, `tests/eval/`) :
- 100 % des findings attendus des fixtures non conformes sont détectés (rappel = 1 sur le corpus de fixtures)
- 0 finding sur les fixtures conformes (précision = 1 sur le corpus)
- Le répertoire temporaire n'existe plus après le scan, y compris en cas d'exception (test dédié)

> Ces deux premiers critères sont des critères de **cohérence sur le corpus interne**, pas des mesures de performance produit. Aucune extrapolation dans le README (C7).

### Phase 3 — Rapport et remédiation

- [ ] `docs/report-schema.md` puis modèle `Report` : findings triés par sévérité puis par famille ; résumé par famille ; métadonnées de scan
- [ ] Rendu **JSON** (contrat d'API) et **Markdown** (lecture humaine)
- [ ] `remediation/` : pour chaque finding, appel Gemini via Vertex AI avec : règle + remédiation statique + extrait borné (jamais le fichier entier, C2) → remédiation contextualisée. Prompts versionnés dans le dépôt. Fallback = remédiation statique si l'appel échoue
- [ ] Regroupement des findings redondants (même règle, même fichier, lignes contiguës) — ADR-005(b)
- [ ] Test : le rapport d'une fixture est identique entre deux runs **hors** champs générés par Gemini (déterminisme de la détection)

**Gate 3** : rapport JSON valide contre le schéma pour toutes les fixtures ; le mode `--no-llm` produit un rapport complet et utile ; aucun extrait envoyé à Gemini ne dépasse la borne configurée (test).

### Phase 4 — Exposition agent et déploiement

- [ ] `agent/` : agent ADK dont l'outil principal est `scan(source, options) -> Report` ; conversation minimale (l'agent explique un finding si on lui pose la question, à partir du rapport — jamais en re-scannant)
- [ ] Agent card A2A : capacités, schéma d'entrée/sortie, authentification requise
- [ ] `deploy/Dockerfile` : image distroless ou équivalente, non-root, Semgrep + gitleaks inclus, **l'image respecte elle-même les règles NET-ISO du pack** (la scanner avec l'agent est un test)
- [ ] Cloud Run : service privé (IAP ou IAM), Secret Manager pour la config, compte de service dédié à droits minimaux
- [ ] Trancher le point ouvert §3 (Vertex AI au-delà du LLM) — **ne pas implémenter avant confirmation**

**Gate 4** : un scan de bout en bout via l'agent A2A déployé sur Cloud Run, sur une fixture, renvoie le même rapport que l'exécution locale ; l'agent scanné par lui-même remonte zéro finding NET-ISO.

### Phase 5 — Préparation Marketplace (hors MVP technique, dépend d'informations Google)

À planifier seulement après clarification des inconnues §PRD-6 (pricing, délais, statut SFEIR dans le programme) :
- Intégration Pub/Sub (notifications d'abonnement)
- Liaison des comptes utilisateurs aux comptes Google
- Soumission Producer Portal

---

## 6. Gates d'évaluation — récapitulatif

| Gate | Ce qui est mesuré | Où |
|---|---|---|
| G1 | Pack valide, métadonnées complètes, fixtures relues | `tests/unit/rules/` + revue humaine |
| G2 | Rappel/précision = 1 sur le corpus de fixtures ; purge du temporaire | `tests/eval/test_corpus.py`, `tests/unit/ingest/test_cleanup.py` |
| G3 | Schéma de rapport ; mode `--no-llm` ; borne des extraits | `tests/integration/test_report.py` |
| G4 | Parité local/Cloud Run ; auto-scan sans finding NET-ISO | `tests/integration/test_e2e.py` (marqué `@cloud`) |

Toute évolution du pack de règles (nouvelle règle, changement de sévérité) passe par : nouvelle fixture ou mise à jour d'un `findings.expected.yaml` → G2 rejoué.

---

## 7. Hors périmètre V1 (ne pas implémenter, même si "facile")

- Génération ou application automatique de patches
- Détection de vulnérabilités par LLM sans règle
- Exécution dynamique, DAST, tests de pénétration
- Intégration CI du client (GitHub App, webhooks)
- Langages hors ADR-008
- Interface web — le rapport Markdown/JSON suffit pour le MVP

---

## 8. Inconnues à trancher (et quand)

| Inconnue | Bloque | Décideur |
|---|---|---|
| Usage Vertex AI "au-delà du LLM" exigé pour l'éligibilité | Phase 4 | Porteur produit + Google |
| Nom du produit | Phase 4 (agent card, image) | Porteur produit |
| Modèle de pricing Marketplace | Phase 5 | Porteur produit + Google |
| Périmètre langages au-delà d'ADR-008 | V2 | Porteur produit |

---

## 9. Conventions pour l'agent de développement

- **Une ADR par décision** non couverte par §3, dans `docs/adr/NNNN-titre.md` (contexte, décision, alternatives, conséquences), statut `proposed` → soumise avant implémentation
- **Tests avant code** pour `engine/`, `rules/`, `ingest/` ; les fixtures sont la source de vérité
- **Aucune nouvelle dépendance** sans justification en une ligne dans la PR (C3 : préférer l'OSS établi, mais ne pas empiler)
- Code, identifiants, commits en **anglais** ; documentation produit (`docs/`, `rules/*/remediation`) en **français**
- Commits atomiques par tâche cochée ; message = identifiant de tâche + verbe à l'impératif
- Aucun chiffre de performance dans le README ou les docstrings tant qu'il n'est pas issu de `tests/eval/` (C7)
- En cas de doute sur le périmètre : relire §7, puis s'arrêter et poser la question plutôt qu'interpréter
