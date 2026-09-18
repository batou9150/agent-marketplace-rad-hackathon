# ADR-004 : Framework agent Google ADK et Gemini sur Vertex AI

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
Vibe Guard a pour objectif d'être exposé comme un agent autonome A2A (Agent-to-Agent) déployable sur Google Cloud et éligible au AI Agent Ecosystem Program de Google Cloud Marketplace (§PRD-6).

## Décision
Utiliser le **Google Agent Development Kit (ADK)** en Python comme framework d'agent, et orchestrer le modèle **Gemini via l'API Vertex AI** pour les capacités génératives.

## Justification
* L'utilisation de Google ADK et Vertex AI répond directement aux critères d'éligibilité pour l'intégration à la Google Cloud Marketplace et au AI Agent Ecosystem Program.
* Google ADK fournit nativement les mécanismes d'exposition d'outils, la gestion de l'Agent Card A2A et les protocoles d'interaction standardisés.
* Intégration transparente avec l'authentification GCP (Workload Identity, Service Accounts).

## Alternatives écartées
* **LangGraph / CrewAI / AutoGen** : Bien qu'utilisés dans la communauté, ils n'apportent aucun avantage pour l'éligibilité au catalogue Google Cloud Marketplace et ajoutent des couches d'abstraction superflues.

## Conséquences
* L'architecture de l'agent doit être modélisée autour des abstractions Google ADK (`Tool`, `Agent`, `AgentCard`).
* L'environnement de test et de production nécessite une configuration d'authentification Google Cloud (ADC ou Service Account) pour les fonctionnalités LLM.
