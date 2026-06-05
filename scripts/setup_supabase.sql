-- ============================================================
-- Projet Scout V2 — Setup Supabase
-- Exécuter dans : Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. Nettoyage des anciennes structures si existantes
DROP TABLE IF EXISTS market_gaps CASCADE;
DROP TYPE IF EXISTS opportunity_status CASCADE;

-- 2. Création de l'énumération de statut du workflow produit
CREATE TYPE opportunity_status AS ENUM (
    'A_VALIDER',
    'EN_DEVELOPPEMENT',
    'PRODUIT_FINI',
    'REJETE'
);

-- 3. Création de la table principale
CREATE TABLE market_gaps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title varchar(255) NOT NULL,
    problem_statement text NOT NULL,
    ai_solution_concept text NOT NULL,
    intensity_score integer NOT NULL CHECK (intensity_score BETWEEN 1 AND 10),
    feasibility_score integer NOT NULL CHECK (feasibility_score BETWEEN 1 AND 10),
    market_score integer NOT NULL CHECK (market_score BETWEEN 1 AND 10),
    opportunity_score numeric(4,2),  -- Calculé automatiquement par trigger
    source_url text UNIQUE NOT NULL,
    category varchar(100) DEFAULT 'Général',
    status opportunity_status DEFAULT 'A_VALIDER',
    detected_at timestamp with time zone DEFAULT timezone('utc'::text, now()),
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now())
);

-- 4. Fonction de calcul automatique du score pondéré (So)
-- Formule : So = (0.5 × D) + (0.3 × F) + (0.2 × M)
CREATE OR REPLACE FUNCTION calculate_opportunity_score()
RETURNS TRIGGER AS $$
BEGIN
    NEW.opportunity_score := (
        (NEW.intensity_score * 0.5) +
        (NEW.feasibility_score * 0.3) +
        (NEW.market_score * 0.2)
    );
    NEW.updated_at := timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Trigger d'automatisation
CREATE TRIGGER trg_calculate_score
BEFORE INSERT OR UPDATE ON market_gaps
FOR EACH ROW
EXECUTE FUNCTION calculate_opportunity_score();

-- 6. Index pour optimiser les lectures du Dashboard
CREATE INDEX idx_gaps_opportunity_score ON market_gaps(opportunity_score DESC);
CREATE INDEX idx_gaps_status ON market_gaps(status);
CREATE INDEX idx_gaps_detected_at ON market_gaps(detected_at DESC);

-- 7. Données de test (optionnel — à supprimer en production)
INSERT INTO market_gaps (title, problem_statement, ai_solution_concept, intensity_score, feasibility_score, market_score, source_url, category)
VALUES (
    'Outil de résumé automatique de réunions Zoom',
    'Les utilisateurs passent 30 min après chaque réunion à rédiger le compte-rendu manuellement',
    'Agent IA qui transcrit, résume et envoie automatiquement le CR par email aux participants',
    8, 9, 7,
    'https://reddit.com/r/productivity/test-example',
    'Productivité'
);
