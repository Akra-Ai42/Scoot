"""
Générateur de newsletter hebdomadaire.
Exécution : python -m src.newsletter.generator
"""

import os
import requests
from datetime import datetime, timedelta, timezone
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

NEWSLETTER_PROMPT = """
Tu es un rédacteur expert en opportunités SaaS et IA.
Rédige une newsletter hebdomadaire en Markdown à partir des opportunités de marché ci-dessous.

Format attendu :
# 🦖 Scout Weekly — Les Opportunités de la Semaine

## 📊 En chiffres
- X opportunités analysées cette semaine
- Top score : Y/10

## 🏆 Top 3 des Opportunités

### 1. [Titre]
**Douleur :** ...
**Solution IA :** ...
**Score :** X.X/10 | Demande: X | Faisabilité: X | Marché: X
**Source :** [Reddit Thread](url)

---

## 💡 Autres Pépites
(liste des autres opportunités A_VALIDER)

---
*Généré automatiquement par l'Agent Scout V2 — {date}*

Opportunités de la semaine :
{opportunities_json}

Rédige la newsletter complète en français. Ton = professionnel mais direct. Pas de bullshit.
"""


def fetch_weekly_opportunities() -> list[dict]:
    """Récupère les opportunités validées de la semaine depuis Supabase."""
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    response = (
        client.table("market_gaps")
        .select("*")
        .eq("status", "A_VALIDER")
        .gte("detected_at", one_week_ago)
        .order("opportunity_score", desc=True)
        .execute()
    )

    return response.data


def generate_newsletter(opportunities: list[dict]) -> str:
    """Génère la newsletter via Together AI."""
    import together

    client = together.Together(api_key=os.environ["TOGETHER_API_KEY"])

    import json
    prompt = NEWSLETTER_PROMPT.format(
        opportunities_json=json.dumps(opportunities, ensure_ascii=False, indent=2),
        date=datetime.now().strftime("%d/%m/%Y"),
    )

    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )

    return response.choices[0].message.content


def send_to_loops(newsletter_content: str) -> bool:
    """Envoie le brouillon de newsletter vers Loops.so."""
    api_key = os.environ.get("LOOPS_API_KEY")
    if not api_key:
        print("  ⚠️  LOOPS_API_KEY non configurée — export local uniquement")
        return False

    # Loops.so : création d'un brouillon via API transactionnelle
    response = requests.post(
        "https://app.loops.so/api/v1/transactional",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "transactionalId": "scout-weekly-newsletter",
            "email": os.environ.get("NEWSLETTER_RECIPIENT", ""),
            "dataVariables": {"content": newsletter_content},
        },
    )

    return response.status_code == 200


def run_newsletter():
    """Point d'entrée principal du générateur de newsletter."""
    print("📰 Générateur de Newsletter Scout — Démarrage")
    print("=" * 50)

    print("\n📥 Récupération des opportunités de la semaine...")
    opportunities = fetch_weekly_opportunities()
    print(f"   → {len(opportunities)} opportunités trouvées")

    if not opportunities:
        print("\n❌ Aucune opportunité cette semaine. Pas de newsletter.")
        return

    print("\n✍️  Génération de la newsletter via Together AI...")
    try:
        newsletter = generate_newsletter(opportunities)
        print(f"   → {len(newsletter)} caractères générés")
    except Exception as e:
        print(f"   ✗ Erreur de génération : {e}")
        return

    # Export local (toujours)
    filename = f"newsletter_{datetime.now().strftime('%Y-%m-%d')}.md"
    output_path = os.path.join("output", filename)
    os.makedirs("output", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(newsletter)
    print(f"\n💾 Newsletter sauvegardée : {output_path}")

    print("\n📤 Envoi vers Loops.so...")
    if send_to_loops(newsletter):
        print("   ✓ Brouillon envoyé avec succès")
    else:
        print("   → Vérifier la configuration LOOPS_API_KEY")

    print("\n✅ Newsletter générée avec succès")
    print("=" * 50)


if __name__ == "__main__":
    run_newsletter()
