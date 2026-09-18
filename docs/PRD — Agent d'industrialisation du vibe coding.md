# **'PRD — Agent d'industrialisation du vibe coding**

Sep 18, 2026 · @Antoine LEFETZ

## **1\. Contexte et problème adressé**

Les outils de génération de code par IA (Copilot Studio, Replit, Lovable, Cursor, etc.) permettent à des utilisateurs métier de produire des applications fonctionnelles sans passer par une équipe d'ingénierie. Ce mode de production — le "vibe coding" — est en expansion rapide dans les grandes organisations.

Ce pattern d'app "vibe codée" présente typiquement les mêmes angles morts :

* Authentification absente ou mal implémentée (pas d'auth managée)  
* Appels API en clair, secrets exposés dans le code ou la configuration  
* Appels directs à des API LLM sans passerelle de gouvernance (coût, rate limiting, traçabilité)  
* Absence d'isolation réseau, dépendances non maîtrisées

Ces apps passent souvent en production telles quelles, faute de processus de revue dédié — l'équipe sécurité/architecture découvre leur existence après coup ("shadow AI apps").

**Hypothèse de marché** : aucun agent identifié dans l'échantillon Google Cloud Marketplace consulté (article du 23/04/2026 sur l'Agent Gallery, \~70 agents partenaires cités) ne couvre l'audit/remédiation a posteriori d'apps générées par IA. Les agents proches (Replit Agent, Lovable) sont des outils de génération, pas de gouvernance. **Statut : hypothèse non vérifiée à l'échelle du catalogue Marketplace complet** — l'échantillon vu est partiel.

## **2\. Objectifs et non-objectifs**

**Objectifs V1**

* Détecter, dans une base de code d'app générée par IA, les non-conformités aux quatre familles de risque identifiées en section 1 (auth, secrets, gouvernance LLM, isolation réseau)  
* Produire un rapport de non-conformité priorisé, lisible par une équipe non-spécialiste sécurité  
* Proposer un chemin de remédiation concret par non-conformité détectée (pas seulement un diagnostic)  
* Remplir les critères techniques d'éligibilité au AI Agent Ecosystem Program (voir section 6\)

**Non-objectifs V1**

* Générer et appliquer automatiquement le patch de remediation (reporté à une V2 — voir section 9\)  
* Couvrir des stacks au-delà de celles couvertes par le référentiel de règles initial (voir section 4\)  
* Remplacer une revue de sécurité humaine sur les apps à criticité élevée — l'agent est un outil de triage et de priorisation, pas une validation finale  
* Gérer le cycle de vie complet de gouvernance des agents (scoring de risque organisationnel, workflow d'approbation IT) — sujet distinct traité par la piste "Copilote de gouvernance agentique" identifiée en parallèle

## **3\. Utilisateurs cibles et cas d'usage**

| Persona | Besoin | Déclencheur |
| :---- | :---- | :---- |
| Responsable plateforme / SRE | Savoir quelles apps "vibe codées" tournent hors du périmètre d'ingénierie et à quel niveau de risque | Une app remontée en incident ou découverte lors d'un audit d'infrastructure |
| RSSI / équipe sécurité | Auditer en amont une app avant sa mise en production, sans mobiliser un pentester pour chaque cas | Demande de mise en prod d'une app créée par une équipe métier |
| DSI | Arbitrer entre bloquer, encadrer ou industrialiser une pratique de vibe coding qui se généralise dans l'organisation | Multiplication des demandes d'usage d'outils de génération IA par les équipes métier |

**Cas d'usage principal (V1)** : un responsable plateforme soumet le repo ou l'URL d'une app générée par IA à l'agent ; il reçoit en retour un rapport de non-conformité priorisé et un chemin de remédiation, sans devoir solliciter l'équipe sécurité pour un premier passage.

**Statut : personas et déclencheurs formulés par hypothèse** — non validés par des entretiens utilisateurs à ce stade.

## **4\. Exigences fonctionnelles (MVP)**

1. **Ingestion**  
   * Accepter un repo Git (URL \+ accès en lecture) ou un upload d'archive de code source  
   * Ne pas exiger d'exécution de l'app (analyse statique uniquement en V1)  
2. **Référentiel de règles**  
   * Format déclaratif (ex. YAML) plutôt que règles codées en dur, pour permettre l'extension par un client  
   * Jeu de règles initial couvrant : auth managée requise, secrets hors code, appels LLM via passerelle, isolation réseau minimale  
   * Chaque règle documentée avec : sévérité, justification, exemple de non-conformité  
3. **Moteur de scan**  
   * Réutilisation d'outils SAST/IaC-scan open source existants comme fondation plutôt que build from scratch (à arbitrer en phase de conception — candidats à évaluer, aucun choisi à ce stade)  
   * Détection par pattern (règles section 2\) plus, en option, un passage par un modèle Gemini pour les cas non couverts par des règles statiques (contribue aussi à l'éligibilité Marketplace — section 6\)  
4. **Rapport de non-conformité**  
   * Liste des non-conformités détectées, priorisées par sévérité  
   * Pour chaque non-conformité : localisation dans le code, règle enfreinte, impact  
5. **Proposition de remédiation**  
   * Description textuelle du chemin de remediation par non-conformité (ex. "wrapper cette app derrière un BFF partagé avec passerelle LLM mutualisée")  
   * Génération de patch automatique explicitement hors scope V1 (voir section 2\)

**Non vérifié** : le choix de l'outil de scan sous-jacent et le périmètre exact des langages/frameworks couverts en V1 restent à trancher — aucune décision d'architecture prise à ce stade.

## **5\. Exigences non-fonctionnelles**

* **Sécurité** : le code source soumis à l'agent est une donnée sensible — isolation stricte par tenant, pas de rétention au-delà de la durée du scan sauf consentement explicite, aucun envoi de code à un modèle tiers hors périmètre contractuel Google Cloud  
* **Portabilité du référentiel** : le format déclaratif de règles (section 4\) doit permettre à un client d'ajouter ses propres règles sans intervention de SFEIR  
* **Performance** : temps de scan cible non chiffré à ce stade — **à définir après un premier prototype**, pas de chiffre inventé  
* **Portabilité cloud** : la V1 Marketplace doit exposer un jeu de règles GCP-natif (Cloud Run/GKE, Identity-Aware Proxy, Vertex AI comme passerelle LLM) pour rester cohérent avec l'écosystème de publication  
* **Auditabilité** : chaque scan doit produire une trace exploitable (quelles règles évaluées, quand, par qui) — recoupe l'exigence de traçabilité par identité cryptographique du Gemini Enterprise Agent Platform (section 6\)

## **6\. Éligibilité et intégration Google Cloud Marketplace**

**Programme** : AI Agent Ecosystem Program — ouvert aux ISV **et aux systems integrators**, SFEIR entre dans cette seconde catégorie (vérifié).

**Critères techniques d'éligibilité (vérifiés)** :

* Adresser un objectif précis avec capacités d'outils/raisonnement/planification — rempli par la boucle scan → diagnostic → remediation  
* Utiliser un modèle Gemini ou un modèle tiers du Model Garden — couvert par le passage Gemini optionnel du moteur de scan (section 4\)  
* Être déployé sur Google Cloud  
* Utiliser ou prévoir de migrer vers des services Vertex AI au-delà du simple appel LLM — **à concevoir explicitement** : candidat naturel \= Vertex AI pour le scoring de risque ou le classement de sévérité des non-conformités, non encore architecturé

**Intégration technique requise (vérifiée)** :

* Backend connecté à Pub/Sub (notifications d'abonnement client, topic créé par le Partner Engineer Google)  
* Gestion de comptes utilisateurs avec liaison aux comptes Google  
* Rédaction d'une agent card conforme à la spécification A2A  
* Soumission via le Producer Portal, revue par l'équipe Cloud Marketplace avant publication

**Non vérifié — à clarifier avec Google avant de committer un plan** :

* Modèle de pricing/revenue share applicable  
* Délai réel entre soumission et publication  
* Existence de coûts ou prérequis de certification côté équipe pour la labellisation "Google Cloud Ready – Gemini Enterprise"  
* Statut d'inscription effectif de SFEIR au programme (candidature à déposer ou déjà identifié comme partenaire SI éligible ?)

## **7\. Métriques de succès**

Aucun chiffre cible fixé à ce stade — le produit n'a pas encore de trafic ni de référence de marché propre. Indicateurs à instrumenter dès la V1 pour fixer des cibles chiffrées en V2 :

* Nombre de scans exécutés et taux de complétion (sans erreur bloquante)  
* Taux de non-conformités marquées "résolues" après remediation proposée (nécessite un mécanisme de retour utilisateur, non spécifié en section 4\)  
* Taux de faux positifs signalés par les utilisateurs  
* Nombre d'installations depuis l'Agent Gallery et taux de ré-utilisation (scans récurrents vs one-shot)

**Statut : cadre de mesure proposé, aucune cible chiffrée** — conforme à la consigne de ne pas inventer de chiffres sans donnée de référence.

## **8\. Risques, inconnues et dépendances**

| Risque | Impact | Statut |
| :---- | :---- | :---- |
| Concurrence Marketplace non exhaustivement cartographiée | Un agent équivalent pourrait déjà exister hors de l'échantillon de \~70 agents consulté | Non vérifié — recherche complémentaire nécessaire dans le catalogue complet avant d'investir |
| Dépendance au choix de l'outil de scan sous-jacent | Conditionne l'effort de développement et la couverture langages/frameworks | Non tranché (section 4\) |
| Conditions commerciales Marketplace (pricing, revenue share) | Conditionne la viabilité économique du produit | Non vérifié (section 6\) — à clarifier avec Google |
| Généricité du référentiel de règles | Un référentiel trop spécifique à un contexte limiterait l'adoption hors AFM | À valider par un second cas d'usage avant généralisation |

## **9\. Roadmap et phasage**

1. **Cadrage** — cartographier la concurrence Marketplace complète, clarifier les conditions commerciales avec Google  
2. **Prototype (V0)** — généraliser le référentiel de règles, choisir l'outil de scan sous-jacent, valider sur un second cas d'usage  
3. **MVP conforme Marketplace (V1)** — intégration Pub/Sub, agent card A2A, usage Vertex AI, soumission Producer Portal  
4. **V2 (post-lancement)** — génération automatique de patch de remediation, extension du référentiel multi-cloud, boucle de retour utilisateur pour mesurer les faux positifs

Aucune date cible fixée — **dépend des arbitrages du workshop du 18/09/2026** (statut de SFEIR dans le programme, conditions commerciales).