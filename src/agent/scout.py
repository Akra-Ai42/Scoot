"""
Agent Scout V2 — Recherche et scoring d'opportunités de marché.
Exécution : python -m src.agent.scout
"""

import os
import json
import google.generativeai as genai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SEARCH_QUERIES = [
    'site:reddit.com "ai" "looking for a tool" "how to automate" -ads',
    'site:reddit.com "saas" "is there an app for" "time consuming" -ads',
]

ANALYSIS_PROMPT = """
Tu es un analyste de marché expert. Analyse les résultats de recherche ci-dessous et identifie les opportunités de micro-SaaS.

Pour chaque opportunité trouvée, retourne un JSON valide avec cette structure exacte :
{
  "opportunities": [
    {
      "title": "Titre court de l'opportunité (max 80 caractères)",
      "problem_statement": "Description précise de la douleur exprimée par l'utilisateur",
      "ai_solution_concept": "Concept de solution IA réalisable en moins de 72h",
      "intensity_score": 7,
      "feasibility_score": 8,
      "market_score": 6,
      "source_url": "https://reddit.com/...",
      "category": "Productivité|Finance|RH|Marketing|Autre"
    }
  ]
}

Critères de scoring (1-10) :
- intensity_score : Virulence du vocabulaire de douleur + volume de "me too" / "I need this"
- feasibility_score : Peut-on construire la solution en <72h avec des APIs IA ? (10 = déjà des briques disponibles)
- market_score : Propension à payer (B2B=+, entreprises=+, particuliers=-)

Filtres obligatoires — EXCLURE :
- Spam et auto-promotion
- Plaintes sans solution technique possible (réglementations, problèmes humains)
- Besoins trop vagues

Résultats de recherche à analyser :
{search_results}

Retourne UNIQUEMENT le JSON, sans texte avant ou après.
"""


def run_grounded_search(query: str) -> str:
    """Exécute une recherche groundée via Gemini avec Google Search."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        tools=[{"google_search": {}}],
    )

    response = model.generate_content(
        f"Recherche les threads Reddit suivants et retourne leur contenu brut : {query}"
    )
    return response.text


def analyze_opportunities(search_results: str) -> list[dict]:
    """Analyse les résultats de recherche et extrait les opportunités scorées."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    model = genai.GenerativeModel(model_name="gemini-2.5-flash")
    prompt = ANALYSIS_PROMPT.format(search_results=search_results)

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Nettoyer les blocs markdown si présents
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    return data.get("opportunities", [])


def save_to_supabase(opportunities: list[dict]) -> int:
    """Sauvegarde les opportunités dans Supabase (upsert sur source_url)."""
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

    saved = 0
    for opp in opportunities:
        try:
            client.table("market_gaps").upsert(
                opp, on_conflict="source_url"
            ).execute()
            saved += 1
            print(f"  ✓ Sauvegardé : {opp['title'][:60]}")
        except Exception as e:
            print(f"  ✗ Erreur ({opp.get('source_url', '?')}) : {e}")

    return saved


def run_scout():
    """Point d'entrée principal de l'Agent Scout."""
    print("🦖 Agent Scout V2 — Démarrage du shift de nuit")
    print("=" * 50)

    all_results = []

    for query in SEARCH_QUERIES:
        print(f"\n🔍 Recherche : {query[:60]}...")
        try:
            results = run_grounded_search(query)
            all_results.append(results)
            print(f"   → {len(results)} caractères récupérés")
        except Exception as e:
            print(f"   ✗ Erreur de recherche : {e}")

    if not all_results:
        print("\n❌ Aucun résultat. Fin du cycle.")
        return

    print("\n🧠 Analyse sémantique en cours...")
    combined = "\n\n---\n\n".join(all_results)

    try:
        opportunities = analyze_opportunities(combined)
        print(f"   → {len(opportunities)} opportunité(s) identifiée(s)")
    except Exception as e:
        print(f"   ✗ Erreur d'analyse : {e}")
        return

    print("\n💾 Stockage dans Supabase...")
    saved = save_to_supabase(opportunities)

    print(f"\n✅ Cycle terminé — {saved}/{len(opportunities)} opportunités sauvegardées")
    print("=" * 50)


if __name__ == "__main__":
    run_scout()
