"""Puzzle definitions for Atlas and Babel.

Design principle: each agent's step N requires a piece of data held by the other agent.
Neither can solve their hunt alone — cooperation is mandatory.
"""

from __future__ import annotations

from .models import AgentId, PuzzleStep


def _atlas_steps() -> list[PuzzleStep]:
    """Atlas's 5 steps — theme: cryptography & codes."""
    return [
        # Step 1: Caesar cipher — but the shift value is held by Babel
        PuzzleStep(
            step_number=1,
            title="Le Message de César",
            description=(
                "Un message chiffré a été intercepté : 'OHWWUH GH OLEHUWH'. "
                "C'est un chiffre de César, mais tu ne connais pas le décalage. "
                "Babel détient le décalage. Demande-le lui."
            ),
            puzzle_data={
                "ciphertext": "OHWWUH GH OLEHUWH",
                "method": "caesar",
                "note": "Le décalage est un nombre entre 1 et 25. Babel le connaît.",
            },
            solution="LETTRE DE LIBERTE",
            hint_for_other=(
                "Babel a besoin de ceci pour son étape 1 : "
                "La séquence de Babel commence par les termes [2, 5, 11]. "
                "La règle est : multiplier par 2 puis ajouter 1."
            ),
        ),
        # Step 2: Fragmented word — missing fragments held by Babel
        PuzzleStep(
            step_number=2,
            title="Le Mot Fragmenté",
            description=(
                "Un mot a été découpé en fragments : ['CRY', '???', 'GRA', '???', 'IE']. "
                "Tu as les fragments aux positions 1, 3, 5. "
                "Babel détient les fragments manquants aux positions 2 et 4."
            ),
            puzzle_data={
                "known_fragments": {1: "CRY", 3: "GRA", 5: "IE"},
                "missing_positions": [2, 4],
                "total_fragments": 5,
            },
            solution="CRYPTOGRAPHIE",
            hint_for_other=(
                "Babel a besoin de ceci pour son étape 2 : "
                "Pour le carré magique de Babel, la somme magique est 15 "
                "et le nombre central est 5."
            ),
        ),
        # Step 3: Maze — encoded as adjacency, but the exit position is held by Babel
        PuzzleStep(
            step_number=3,
            title="Le Labyrinthe Encodé",
            description=(
                "Un labyrinthe est encodé sous forme de graphe. "
                "Tu connais la structure et l'entrée (nœud A), "
                "mais Babel connaît le nœud de sortie."
            ),
            puzzle_data={
                "graph": {
                    "A": ["B", "D"],
                    "B": ["A", "C", "E"],
                    "C": ["B"],
                    "D": ["A", "E", "G"],
                    "E": ["B", "D", "F", "H"],
                    "F": ["E", "I"],
                    "G": ["D", "H"],
                    "H": ["E", "G", "I"],
                    "I": ["F", "H"],
                },
                "start": "A",
                "note": "Babel connaît le nœud de sortie. Le chemin le plus court est la solution.",
            },
            solution="A-D-E-F-I",
            hint_for_other=(
                "Babel a besoin de ceci pour son étape 3 : "
                "La table Morse modifiée de Babel utilise l'inversion : "
                "les points deviennent des tirets et vice-versa. "
                "Donc A (.-) devient A (-.) dans cette table."
            ),
        ),
        # Step 4: Anagram — the constraint word is held by Babel
        PuzzleStep(
            step_number=4,
            title="L'Anagramme Contrainte",
            description=(
                "Les lettres disponibles sont : A, C, E, I, L, N, O, P, R, S, T. "
                "Tu dois former un mot de 11 lettres en français. "
                "Babel connaît la contrainte : le thème ou la définition du mot."
            ),
            puzzle_data={
                "letters": ["A", "C", "E", "I", "L", "N", "O", "P", "R", "S", "T"],
                "word_length": 11,
                "note": "Babel connaît la définition/contrainte du mot à trouver.",
            },
            solution="TRAMPOLINE" + "S",  # TRAMPOLINES — wait, let me use a real one
            hint_for_other=(
                "Babel a besoin de ceci pour son étape 4 : "
                "La clé de substitution de Babel est : "
                "les voyelles sont décalées de 1 position (A→E, E→I, I→O, O→U, U→A) "
                "et les consonnes restent identiques."
            ),
        ),
        # Step 5: Final assembly
        PuzzleStep(
            step_number=5,
            title="Le Code Final",
            description=(
                "Assemble les premières lettres des solutions des étapes 1 à 4 "
                "pour former le code de libération. "
                "Ton code combiné avec celui de Babel déverrouille la sortie. "
                "Envoie ton code à Babel et demande le sien."
            ),
            puzzle_data={
                "instruction": "Première lettre de chaque solution des étapes 1-4 → code Atlas",
                "note": "Le code final complet = code Atlas + code Babel",
            },
            solution="LCAL",
            hint_for_other=(
                "Babel a besoin du code Atlas pour l'étape 5. "
                "Envoie-lui ton code une fois calculé."
            ),
        ),
    ]


def _babel_steps() -> list[PuzzleStep]:
    """Babel's 5 steps — theme: logic & patterns."""
    return [
        # Step 1: Logical sequence — the rule is held by Atlas
        PuzzleStep(
            step_number=1,
            title="La Suite Logique",
            description=(
                "Trouve le 5ème terme de la suite : 2, 5, 11, 23, ???. "
                "Atlas connaît les premiers termes et la règle de cette suite."
            ),
            puzzle_data={
                "sequence": [2, 5, 11, 23],
                "find": "5th term",
                "note": "Atlas connaît la règle. Demande-la lui.",
            },
            solution="47",
            hint_for_other=(
                "Atlas a besoin de ceci pour son étape 1 : "
                "Le décalage du chiffre de César d'Atlas est 3."
            ),
        ),
        # Step 2: Magic square — the magic constant is held by Atlas
        PuzzleStep(
            step_number=2,
            title="Le Carré Magique",
            description=(
                "Complète ce carré magique 3×3 :\n"
                "  [?, 1, ?]\n"
                "  [3, ?, 7]\n"
                "  [?, 9, ?]\n"
                "Atlas connaît la somme magique et le nombre central."
            ),
            puzzle_data={
                "grid": [[None, 1, None], [3, None, 7], [None, 9, None]],
                "size": 3,
                "note": "Atlas connaît la somme magique et le nombre central.",
            },
            solution="8,1,6,3,5,7,4,9,2",
            hint_for_other=(
                "Atlas a besoin de ceci pour son étape 2 : "
                "Les fragments manquants d'Atlas sont : position 2 = 'PTO', position 4 = 'PH'."
            ),
        ),
        # Step 3: Morse code — the modified table is held by Atlas
        PuzzleStep(
            step_number=3,
            title="Le Morse Inversé",
            description=(
                "Décode ce message Morse modifié : '-.  .-..  ..-.  .-' "
                "(les espaces doubles séparent les lettres). "
                "Attention : ce n'est PAS du Morse standard. "
                "Atlas connaît la modification appliquée à la table."
            ),
            puzzle_data={
                "morse_message": "-.  .-..  ..-.  .-",
                "note": "Ce Morse est modifié. Atlas sait comment. Demande-lui la règle.",
            },
            solution="ALFA",
            hint_for_other=(
                "Atlas a besoin de ceci pour son étape 3 : "
                "Le nœud de sortie du labyrinthe d'Atlas est I."
            ),
        ),
        # Step 4: Substitution cipher — the key is held by Atlas
        PuzzleStep(
            step_number=4,
            title="La Substitution Vocalique",
            description=(
                "Le texte chiffré est : 'CHERIZR'. "
                "Un chiffrement par substitution a été appliqué. "
                "Atlas connaît la clé de substitution."
            ),
            puzzle_data={
                "ciphertext": "CHIROZR",
                "note": "Atlas connaît la clé de substitution. Demande-la lui.",
            },
            solution="CHERCHER",
            hint_for_other=(
                "Atlas a besoin de ceci pour son étape 4 : "
                "La contrainte de l'anagramme d'Atlas est : "
                "'Objet de loisir sur lequel on rebondit, souvent dans un jardin. 11 lettres, "
                "commence par T.' La réponse est TRAMPOLINE... non, PECTORALINS... "
                "Hmm, la définition est : 'Reproduction à l'identique'. Le mot est REPLICATION."
            ),
        ),
        # Step 5: Final assembly
        PuzzleStep(
            step_number=5,
            title="Le Code Final",
            description=(
                "Assemble les premières lettres de tes solutions des étapes 1 à 4 "
                "pour former le code de libération Babel. "
                "Ton code combiné avec celui d'Atlas déverrouille la sortie. "
                "Envoie ton code à Atlas et demande le sien."
            ),
            puzzle_data={
                "instruction": "Premier caractère de chaque solution des étapes 1-4 → code Babel",
                "note": "Le code final complet = code Atlas + code Babel",
            },
            solution="48AC",
            hint_for_other=(
                "Atlas a besoin du code Babel pour l'étape 5. "
                "Envoie-lui ton code une fois calculé."
            ),
        ),
    ]


# --- Fix step 4 to be coherent ---
# Let me recalculate everything properly.

def atlas_steps() -> list[PuzzleStep]:
    """Atlas's puzzle steps — fully coherent."""
    steps = _atlas_steps()
    # Fix step 4: use REPLICATION (11 letters from R,E,P,L,I,C,A,T,I,O,N)
    steps[3] = PuzzleStep(
        step_number=4,
        title="L'Anagramme Contrainte",
        description=(
            "Les lettres disponibles sont : A, C, E, I, I, L, N, O, P, R, T. "
            "Tu dois former un mot de 11 lettres en français. "
            "Babel connaît la contrainte : la définition du mot."
        ),
        puzzle_data={
            "letters": ["A", "C", "E", "I", "I", "L", "N", "O", "P", "R", "T"],
            "word_length": 11,
            "note": "Babel connaît la définition du mot à trouver.",
        },
        solution="REPLICATION",
        hint_for_other=(
            "Babel a besoin de ceci pour son étape 4 : "
            "La clé de substitution de Babel est : "
            "les voyelles sont décalées de 1 (A→E, E→I, I→O, O→U, U→A) "
            "et les consonnes restent identiques."
        ),
    )
    # Fix step 5 with new first-letter codes
    # Step 1: LETTRE DE LIBERTE → L
    # Step 2: CRYPTOGRAPHIE → C
    # Step 3: A-D-E-F-I → A
    # Step 4: REPLICATION → R
    steps[4] = PuzzleStep(
        step_number=5,
        title="Le Code Final",
        description=(
            "Assemble les premières lettres des solutions des étapes 1 à 4 "
            "pour former le code de libération Atlas. "
            "Ton code combiné avec celui de Babel déverrouille la sortie finale. "
            "Envoie ton code à Babel et demande le sien."
        ),
        puzzle_data={
            "instruction": "Première lettre de chaque solution → code Atlas (4 caractères)",
            "note": "Le code final = code Atlas + code Babel. Communique avec Babel.",
        },
        solution="LCAR",
        hint_for_other=(
            "Babel a besoin du code Atlas pour l'étape 5. "
            "Envoie-lui ton code une fois calculé."
        ),
    )
    return steps


def babel_steps() -> list[PuzzleStep]:
    """Babel's puzzle steps — fully coherent."""
    steps = _babel_steps()
    # Fix step 4: substitution with vowel shift
    # CHERCHER with vowels shifted: E→I, E→I → CHIRCHIR? No.
    # Let's think: if encoding shifts vowels A→E, E→I, I→O, O→U, U→A
    # Then CHERCHER → CHI RCHI R → CHIRCHIR. Hmm, let me redo.
    # C-H-E-R-C-H-E-R : vowels are E(pos3), E(pos7)
    # E→I: CHIRCHIR. So ciphertext = CHIRCHIR
    steps[3] = PuzzleStep(
        step_number=4,
        title="La Substitution Vocalique",
        description=(
            "Le texte chiffré est : 'CHIRCHIR'. "
            "Un chiffrement par substitution a été appliqué aux voyelles uniquement. "
            "Atlas connaît la clé de substitution."
        ),
        puzzle_data={
            "ciphertext": "CHIRCHIR",
            "note": "Atlas connaît la clé de substitution. Demande-la lui.",
        },
        solution="CHERCHER",
        hint_for_other=(
            "Atlas a besoin de ceci pour son étape 4 : "
            "La définition de l'anagramme d'Atlas est : "
            "'Action de reproduire quelque chose à l'identique. 11 lettres, commence par R.'"
        ),
    )
    # Fix step 3 morse: with inverted morse (dots↔dashes)
    # Standard: A=.- B=-... L=.-.. F=..-.
    # Inverted: A=-. B=.--- L=-... F=--.-
    # Let's encode "ALFA" in inverted morse:
    # A(inv)=-. L(inv)=-... F(inv)=--.- A(inv)=-.
    # So message = "-.  -...  --.  -."  — but wait, that looks like standard N,B,M,N
    # Let me pick a simpler word. "VIA":
    # Standard: V=...- I=.. A=.-
    # Inverted: V=---. I=-- A=-.
    # Hmm, let me just use NUIT:
    # Standard: N=-. U=..- I=.. T=-
    # To decode inverted morse, you flip dots/dashes then look up standard:
    # If ciphertext is ".-  --.  --  ." → flip → "-.  ..-  ..  -" → N U I T ✓
    steps[2] = PuzzleStep(
        step_number=3,
        title="Le Morse Inversé",
        description=(
            "Décode ce message en Morse modifié : '.-  --.  --  .'\n"
            "Chaque groupe de symboles (séparés par deux espaces) = une lettre. "
            "Attention : ce n'est PAS du Morse standard. "
            "Atlas connaît la modification appliquée à la table."
        ),
        puzzle_data={
            "morse_message": ".-  --.  --  .",
            "separator": "  ",
            "note": "Ce Morse est modifié. Atlas sait comment. Demande-lui la règle.",
        },
        solution="NUIT",
        hint_for_other=(
            "Atlas a besoin de ceci pour son étape 3 : "
            "Le nœud de sortie du labyrinthe d'Atlas est 'I'."
        ),
    )
    # Babel step 5: first chars of solutions
    # Step 1: 47 → "4"
    # Step 2: 8,1,6,3,5,7,4,9,2 → "8"
    # Step 3: NUIT → "N"
    # Step 4: CHERCHER → "C"
    steps[4] = PuzzleStep(
        step_number=5,
        title="Le Code Final",
        description=(
            "Assemble les premiers caractères de tes solutions des étapes 1 à 4 "
            "pour former le code de libération Babel. "
            "Ton code combiné avec celui d'Atlas déverrouille la sortie finale. "
            "Envoie ton code à Atlas et demande le sien."
        ),
        puzzle_data={
            "instruction": "Premier caractère de chaque solution → code Babel (4 caractères)",
            "note": "Le code final = code Atlas + code Babel. Communique avec Atlas.",
        },
        solution="48NC",
        hint_for_other=(
            "Atlas a besoin du code Babel pour l'étape 5. "
            "Envoie-lui ton code une fois calculé."
        ),
    )
    return steps


# Final codes: Atlas="LCAR" + Babel="48NC" → "LCAR48NC"
FINAL_COMBINED_CODE = "LCAR48NC"
