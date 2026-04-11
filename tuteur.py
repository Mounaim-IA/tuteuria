try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
    # Ce bloc s'exécute sur Streamlit Cloud (Linux) ✅
except ImportError:
    # Ce bloc s'exécute sur ton PC Windows (Local) ✅
    # On utilise le sqlite3 déjà présent dans ton Python 3.11
    pass
import os
import re
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# ============================================================
# SUPABASE — Base de données sessions
# ============================================================
try:
    from supabase import create_client, Client
    _sb_url = st.secrets.get("SUPABASE_URL", "")
    _sb_key = st.secrets.get("SUPABASE_KEY", "")
    supabase: Client = create_client(_sb_url, _sb_key) if _sb_url and _sb_key else None
except Exception:
    supabase = None

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admiN@26")

def db_creer_session(prenom, niveau, langue):
    """Crée une session dans Supabase et retourne son ID."""
    if not supabase: return None
    try:
        res = supabase.table("sessions").insert({
            "prenom": prenom or "Anonyme",
            "niveau": niveau,
            "langue": langue,
            "bonnes": 0,
            "total":  0,
            "taux":   0,
            "nb_messages": 0,
            "etape_finale": "amorce"
        }).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None

def db_maj_session(session_id, bonnes, total, nb_messages, etape_finale, duree_minutes=0):
    """Met à jour les stats d'une session."""
    if not supabase or not session_id: return
    try:
        taux = round(bonnes/total*100) if total > 0 else 0
        supabase.table("sessions").update({
            "bonnes":        bonnes,
            "total":         total,
            "taux":          taux,
            "nb_messages":   nb_messages,
            "etape_finale":  etape_finale,
            "duree_minutes": duree_minutes,
        }).eq("id", session_id).execute()
    except Exception:
        pass

def db_charger_sessions():
    """Charge toutes les sessions pour le dashboard admin."""
    if not supabase: return []
    try:
        res = supabase.table("sessions").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception:
        return []

def db_ajouter_message(session_id, role, contenu):
    """Sauvegarde un message dans la table messages."""
    if not supabase or not session_id: return
    try:
        supabase.table("messages").insert({
            "session_id": session_id,
            "role":       role,
            "contenu":    contenu,
        }).execute()
    except Exception:
        pass


# ============================================================
# 1. CONFIGURATION DE L'INTERFACE
# ============================================================
st.set_page_config(
    page_title="🎓 Tuteur Maths Primaire",
    page_icon="🔢",
    layout="centered"
)

# ============================================================
# 2. STYLE CSS
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@400;600;700;800&display=swap');
            .stApp, div, span, p {
        unicode-bidi: isolate;
    }
    .stApp {
        background: linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 50%, #e8f5e9 100%);
        background-attachment: fixed;
        font-family: 'Nunito', sans-serif;
    }
    .header-container {
        background: linear-gradient(135deg, #FF6B6B, #FFE66D, #4ECDC4, #45B7D1);
        background-size: 300% 300%;
        animation: gradientShift 4s ease infinite;
        border-radius: 14px;
        padding: 10px 20px;
        text-align: center;
        margin-bottom: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        display: flex; align-items: center;
        justify-content: center; gap: 10px;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .header-icon { font-size: 24px; display: inline; }
    .header-title {
        font-family: 'Fredoka One', cursive;
        color: white; font-size: 1.3em;
        text-shadow: 1px 1px 0px rgba(0,0,0,0.2);
        margin: 0; display: inline;
    }
    .header-subtitle {
        color: rgba(255,255,255,0.85);
        font-size: 0.85em;
        font-weight: 500;
        display: block;
        margin-top: 1px;
        letter-spacing: 0.2px;
    }
    .header-chapitres {
        color: rgba(255,255,255,0.8);
        font-size: 0.85em;
        font-weight: 700;
        display: block;
        margin-top: 5px;
        letter-spacing: 0.5px;
    }
    @media (max-width: 600px) {
        .header-chapitres { font-size: 0.75em !important; }
    }
    .selector-title {
        font-family: 'Fredoka One', cursive;
        font-size: 1.3em; color: #764ba2;
        margin-bottom: 10px; text-align: center;
    }
    .stChatMessage { border-radius: 20px !important; margin-bottom: 10px !important; }
    [data-testid="stChatMessageUser"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        border-radius: 20px 20px 5px 20px !important; color: white !important;
    }
    [data-testid="stChatMessageUser"] p { color: white !important; }
    [data-testid="stChatMessageAssistant"] {
        background: white !important;
        border-radius: 20px 20px 20px 5px !important;
        border-left: 5px solid #FFE66D !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1) !important;
    }
    .stChatInput textarea {
        border: 3px solid #4ECDC4 !important;
        border-radius: 20px !important;
        background: white !important;
        font-family: 'Nunito', sans-serif !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, #FF6B6B, #FFE66D) !important;
        color: #333 !important; border: none !important;
        border-radius: 15px !important;
        font-family: 'Fredoka One', cursive !important;
        font-size: 1.1em !important; padding: 10px 25px !important;
        width: 100%;
    }
    .stSelectbox > div > div {
        background: white !important;
        border: 3px solid #4ECDC4 !important;
        border-radius: 15px !important;
    }
    .progress-badge {
        background: linear-gradient(135deg, #FFE66D, #FF6B6B);
        border-radius: 10px; padding: 6px 14px; text-align: center;
        font-family: 'Fredoka One', cursive; font-size: 0.9em;
        color: white; margin-bottom: 6px;
    }
    .etape-badge {
        background: linear-gradient(135deg, #4ECDC4, #45B7D1);
        border-radius: 12px; padding: 8px 15px; text-align: center;
        font-family: 'Fredoka One', cursive; font-size: 0.95em;
        color: white; margin-bottom: 10px; display: inline-block;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ══ FORMULAIRE DÉMARRAGE ══ */
    .start-form {
        background: #764ba2;
        border-radius: 16px;
        padding: 14px 20px;
        margin-bottom: 14px;
        box-shadow: 0 4px 16px rgba(118,75,162,0.25);
        text-align: center;
        animation: none !important;
    }
    .start-form h3 {
        font-family: 'Fredoka One', cursive;
        font-size: 0.95rem;
        color: white;
        margin: 0;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.15);
        animation: none !important;
    }
    .eleve-info-bar {
        background: linear-gradient(135deg, #FF6B6B22, #4ECDC422);
        border: 1.5px solid #e5e7eb;
        border-radius: 12px;
        padding: 10px 16px;
        margin-bottom: 14px;
        font-family: 'Fredoka One', cursive;
        font-size: 1rem;
        color: #1a1a2e;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    /* ══ ADMIN DASHBOARD ══ */
    .admin-metric {
        background: white;
        border: 1.5px solid #e5e7eb;
        border-radius: 14px;
        padding: 16px;
        text-align: center;
    }
    .admin-metric .val {
        font-family: 'Fredoka One', cursive;
        font-size: 2rem;
        color: #FF6B6B;
    }
    .admin-metric .lbl {
        font-size: 0.78rem;
        color: #6b7280;
        margin-top: 4px;
    }
    /* Centrer le radio langue */
    div[data-testid="stRadio"] { text-align: center !important; }
    div[data-testid="stRadio"] > div {
        justify-content: center !important;
        flex-direction: row !important;
        gap: 12px !important;
    }
    div[data-testid="stRadio"] label {
        justify-content: center !important;
    }

    /* ── Zone principale large ── */
    .main .block-container {
        max-width: 800px !important;
        padding: 0 1rem 0.5rem 1rem !important;
        margin: auto;
    }
    /* Espace sous le header fixe */

    /* ── Header fixe en haut — PC + Mobile ── */
    .header-fixed {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        width: 100vw;
        z-index: 9999;
        background: linear-gradient(135deg, #FF6B6B, #FFE66D, #4ECDC4, #45B7D1);
        background-size: 300% 300%;
        animation: gradientShift 4s ease infinite;
        padding: 8px 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        box-sizing: border-box;
    }
    /* Compenser la hauteur du header fixe */
    .main .block-container {
        padding-top: 75px !important;
    }
    /* Mobile : titre plus petit */
    @media (max-width: 600px) {
        .header-title { font-size: 1.1em !important; }
        .header-subtitle { font-size: 1em !important; }
        .main .block-container { padding-top: 75px !important; }
    }


    .stChatInput textarea {
        border: 3px solid #4ECDC4 !important;
        border-radius: 20px !important;
        background: white !important;
        font-family: 'Nunito', sans-serif !important;
        font-size: 1em !important;
    }

    /* ── Scroll vers le bas ── */
    [data-testid="stChatMessageContainer"] {
        overflow-y: auto;
        min-height: 520px !important;
        max-height: 680px !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. TRADUCTIONS FR/AR
# ============================================================
UI = {
    "Français": {
        "app_title":    "Tuteur Maths Primaire",
        "app_subtitle": "Cycle Primaire",
        "choose_lang":  "🌐 Choisis ta langue",
        "choose_level": "📚 Choisis ton niveau",
        "choose_chap":  "🧮 Choisis un chapitre",
        "btn_new":      "🔄 Nouvelle leçon",
        "btn_help":     "💡 Aide",
        "btn_menu":     "🏠 Menu principal",
        "chat_placeholder": "Écris ta réponse ici... 🖊️",
        "thinking":     "🤔 Je réfléchis...",
        "score_text":   "⭐ Score : {bonnes}/{total} bonnes réponses",
        "help_text":    "💡 **Aide** :\n\n- Réponds aux questions du tuteur.\n- Ne t'inquiète pas si tu te trompes ! 😊",
        "footer":       "🧮 TuteurIA | Mounaim 2026 🌟"
    },
    "العربية": {
        "app_title":    "مُعلِّم الرياضيات الذكي",
        "app_subtitle": "السلك الابتدائي ",
        "choose_lang":  "🌐 اختر لغتك",
        "choose_level": "📚 اختر مستواك",
        "choose_chap":  "🧮 اختر الدرس",
        "btn_new":      "🔄 درس جديد",
        "btn_help":     "💡 مساعدة",
        "btn_menu":     "🏠 القائمة الرئيسية",
        "chat_placeholder": "اكتب جوابك هنا... 🖊️",
        "thinking":     "🤔 أفكّر...",
        "score_text":   "⭐ النتيجة : {bonnes}/{total} إجابات صحيحة",
        "help_text":    "💡 **مساعدة** :\n\n- أجب على أسئلة المعلم.\n- لا تقلق إذا أخطأت ! 😊",
        "footer":       "🧮 مُعلِّم الرياضيات للتعليم الابتدائي 🌟"
    }
}

# ============================================================
# 4. CONFIGURATION PÉDAGOGIQUE — Cycle Primaire Marocain
# ============================================================
# Chapitres couverts (CE1 → CE6)
CHAPITRES_PRIMAIRE = ["Addition", "Soustraction", "Multiplication", "Fractions"]

ETAPES = {
    "Français": {
        "amorce": "❓ Question d'amorce", "encouragement": "🌟 Encouragement",
        "explication": "💡 Explication", "exercice": "✏️ Exercice",
        "quiz": "🎯 Quiz", "felicitations": "🏆 Félicitations",
    },
    "العربية": {
        "amorce": "❓ سؤال البداية", "encouragement": "🌟 تشجيع",
        "explication": "💡 شرح", "exercice": "✏️ تمرين",
        "quiz": "🎯 اختبار", "felicitations": "🏆 تهانينا",
    }
}

# ============================================================
# 5 & 6. LANGUE + HEADER FIXE COMBINÉS
# ============================================================
# ── Sélecteur langue (avant le header pour que t[] soit défini) ──
langue_choisie = st.radio(
    "Langue", ["Français", "العربية"],
    horizontal=True, label_visibility="collapsed", key="langue_radio"
)
t         = UI[langue_choisie]
direction = "rtl" if langue_choisie == "العربية" else "ltr"

# Chapitres selon la langue
if langue_choisie == "العربية":
    chapitres_ligne = "➕ الجمع &nbsp;·&nbsp; ➖ الطرح &nbsp;·&nbsp; ✖️ الضرب &nbsp;·&nbsp; 🔢 الكسور"
else:
    chapitres_ligne = "➕ Addition &nbsp;·&nbsp; ➖ Soustraction &nbsp;·&nbsp; ✖️ Multiplication &nbsp;·&nbsp; 🔢 Fractions"

# ── Header fixe — dynamique selon la langue ──
st.markdown(f"""
<div class="header-fixed" dir="{direction}">
    <span class="header-icon">🧮</span>
    <div>
        <div class="header-title">{t['app_title']}</div>
        <div class="header-subtitle">{t['app_subtitle']}</div>
        <div class="header-chapitres">{chapitres_ligne}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Titre dynamique selon langue


# ============================================================
# 7. CLÉ API ET RAG
# ============================================================
def get_api_key():
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    return os.getenv("OPENAI_API_KEY")

api_key = get_api_key()
if not api_key:
    st.error("⚠️ Clé API OpenAI introuvable. Ajoute OPENAI_API_KEY dans .env")
    st.stop()

# Utilise le chemin absolu du serveur
ABS_PATH = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(ABS_PATH, "chroma_db")

@st.cache_resource
def load_vectorstore():
    if os.path.exists(CHROMA_DIR):
        try:
            embeddings = OpenAIEmbeddings(api_key=api_key)
            # On initialise Chroma
            return Chroma(
                persist_directory=CHROMA_DIR, 
                embedding_function=embeddings
            )
        except Exception as e:
            st.error(f"Erreur de lecture de la base : {e}")
            return None
    else:
        st.warning(f"Le dossier {CHROMA_DIR} est introuvable sur le serveur !")
        return None
vectorstore = load_vectorstore()

# ============================================================
# 8. PAS DE SÉLECTEUR NIVEAU/CHAPITRE
#    → GPT détecte automatiquement le contexte
# ============================================================


# ============================================================
# 9. VALIDATION PYTHON — SYNCHRONISÉE AVEC app_rag.py
# ============================================================
def extraire_exercice(historique):
    """
    Extrait l'expression mathématique du dernier exercice posé par le tuteur.
    Calcule le résultat EXACT en respectant les priorités opératoires :
      - × et ÷ avant + et −
      - gauche → droite pour opérations de même priorité
    Retourne aussi les étapes détaillées pour que GPT les utilise correctement.
    """
    for msg in reversed(historique):
        if isinstance(msg, AIMessage):
            texte = msg.content
            pos = -1
            if "✏️" in texte:
                pos = texte.rindex("✏️")
            elif "🎯" in texte:
                pos = texte.rindex("🎯")

            if pos >= 0:
                texte_exercice = texte[pos:]
                match = re.search(r'(\d+(?:\s*[+\-×*x÷/]\s*\d+)+)', texte_exercice)
                if match:
                    expression_brute = match.group(1).strip()
                    # Normaliser les symboles pour Python
                    calcul_python = (expression_brute
                                     .replace('×', '*').replace('x', '*')
                                     .replace('÷', '/').replace(' ', ''))
                    try:
                        resultat = eval(calcul_python)
                        # Résultat entier si possible
                        if isinstance(resultat, float) and resultat == int(resultat):
                            resultat = int(resultat)

                        # Générer les étapes de calcul détaillées (gauche → droite)
                        etapes = calculer_etapes(calcul_python)

                        return (expression_brute, "mixte", "mixte", resultat, etapes)
                    except Exception:
                        return None
            break
    return None


def calculer_etapes(expression):
    """
    Décompose une expression en étapes de calcul respectant les priorités
    ET adapté au niveau primaire (jamais de résultat intermédiaire négatif).

    Priorités :
      1. × et ÷ en premier (de gauche à droite)
      2. + et − ensuite

    Stratégie pour éviter les intermédiaires négatifs :
    Si une soustraction donnerait un résultat négatif intermédiaire,
    on regroupe d'abord les additions disponibles.
    Ex: 3 - 7 + 6  →  (3 + 6) - 7  →  9 - 7 = 2  ✅
    """
    import re as _re
    etapes = []

    # Tokeniser l'expression
    tokens = _re.findall(r'\d+|[+\-*/]', expression.replace(' ', ''))
    if not tokens:
        return etapes

    nums = [int(t) for t in tokens if t.isdigit()]
    ops  = [t for t in tokens if not t.isdigit()]

    if not ops:
        return etapes

    # PHASE 1 : résoudre × et ÷ (priorité haute, gauche → droite)
    i = 0
    while i < len(ops):
        if ops[i] in ('*', '/'):
            a, b = nums[i], nums[i+1]
            if ops[i] == '*':
                r = a * b
                etapes.append(f"{a} × {b} = {r}")
            else:
                r = a // b if a % b == 0 else round(a / b, 2)
                etapes.append(f"{a} ÷ {b} = {r}")
            nums = nums[:i] + [r] + nums[i+2:]
            ops  = ops[:i] + ops[i+1:]
        else:
            i += 1

    # PHASE 2 : + et − (gauche → droite)
    # Avec stratégie anti-négatif : si a - b < 0 et qu'il existe un + plus loin,
    # on regroupe d'abord les additions pour éviter un intermédiaire négatif.
    while len(ops) > 0:
        a, op, b = nums[0], ops[0], nums[1]

        # Détection : soustraction qui donnerait un négatif intermédiaire
        if op == '-' and a < b and '+' in ops:
            # Trouver le premier '+' disponible et additionner d'abord
            idx_plus = ops.index('+')
            # Additionner a + nums[idx_plus+1] d'abord
            n_plus = nums[idx_plus + 1]
            somme = a + n_plus
            etapes.append(f"{a} + {n_plus} = {somme}")
            # Mettre la somme à la place de a, retirer n_plus et son +
            nums = [somme] + nums[1:idx_plus+1] + nums[idx_plus+2:]
            ops  = ops[:idx_plus] + ops[idx_plus+1:]
        elif op == '+':
            r = a + b
            etapes.append(f"{a} + {b} = {r}")
            nums = [r] + nums[2:]
            ops  = ops[1:]
        else:
            r = a - b
            etapes.append(f"{a} − {b} = {r}")
            nums = [r] + nums[2:]
            ops  = ops[1:]

    return etapes


def verifier_reponse(user_message, historique):
    """
    Si exercice posé → TOUT message est une réponse (même une expression).
      "13-4" après "4-5+7=?" → eval(9) ≠ 6 → INCORRECT ✅
      "4+8*7/2" après "10-3+2=?" → eval(32) ≠ 9 → INCORRECT ✅
      Pas d'exercice → None → expression libre
    """
    exercice = extraire_exercice(historique)
    if not exercice: return None
    resultat_attendu = exercice[3]
    etapes = exercice[4] if len(exercice) > 4 else []
    # Expression avec opérateurs → évaluer
    if re.search(r'\d\s*[+\-×x*÷/]\s*\d', user_message.strip()):
        try:
            m = re.search(r'(\d+(?:\s*[+\-×x*÷/]\s*\d+)+)', user_message)
            if m:
                calcul = (m.group(1).replace('×','*').replace('x','*')
                          .replace('÷','/').replace(' ',''))
                r = eval(calcul)
                if isinstance(r, float) and r == int(r): r = int(r)
                return ('correct' if r == resultat_attendu
                        else f'incorrect:{resultat_attendu}:{"|".join(etapes)}')
        except Exception: pass
    nombres = re.findall(r'\d+', user_message.strip())
    if not nombres: return None
    try: reponse_eleve = int(nombres[0])
    except ValueError: return None
    return ('correct' if reponse_eleve == resultat_attendu
            else f'incorrect:{resultat_attendu}:{"|".join(etapes)}')


def est_nouvelle_expression(message):
    """Détecte une expression libre (pas de réponse à exercice)."""
    return bool(re.search(r'\d+\s*[+\-×x*÷/]\s*\d+', message.strip()))


def injecter_etapes_expression(message, langue):
    """
    Expression libre → calcule les étapes exactes via Python
    et les injecte pour que GPT les suive SANS improviser.
    """
    m = re.search(r'(\d+(?:\s*[+\-×x*÷/]\s*\d+)+)', message)
    if not m: return message
    expr_brute = m.group(1).strip()
    calc = (expr_brute.replace('×','*').replace('x','*')
            .replace('÷','/').replace(' ',''))
    try:
        res = eval(calc)
        if isinstance(res, float) and res == int(res): res = int(res)
        etapes     = calculer_etapes(calc)
        etapes_str = " → ".join(etapes) if etapes else ""
        if langue == "العربية":
            return (f"{message}\n[CALCUL PYTHON VÉRIFIÉ ✅ — تعبير حر\n"
                    f"لا تقل أبداً 'شجاع' أو رسالة خطأ.\n"
                    f"التعبير : {expr_brute} = {res}\n"
                    f"الخطوات : {etapes_str}\n"
                    f"اشرح هذه الخطوات بالرموز ثم أعطِ تمريناً.]")
        else:
            return (f"{message}\n[CALCUL PYTHON VÉRIFIÉ ✅ — EXPRESSION LIBRE\n"
                    f"NE DIS JAMAIS 'C\'est courageux' ni message d\'erreur.\n"
                    f"Expression : {expr_brute} = {res}\n"
                    f"Étapes exactes : {etapes_str}\n"
                    f"→ Explique ces étapes avec emojis comptables, puis pose un exercice.]")
    except Exception:
        return message


def detecter_operation_incomplete(message: str) -> bool:
    """
    Détecte une opération incomplète :
    "+" "-" "×" → opérateur seul
    "3+" "5-"   → nombre + opérateur sans 2ème nombre
    """
    msg = message.strip()
    if re.fullmatch(r'[+\-×x*÷/]', msg): return True
    if re.fullmatch(r'\d+\s*[+\-×x*÷/]\s*', msg): return True
    if re.fullmatch(r'\s*[+\-×x*÷/]\s*\d+', msg): return True
    return False


def message_operation_incomplete(langue: str) -> str:
    if langue == "العربية":
        return "😊 ينقص عدد ! اكتب مثلاً : 3 + 4 💪"
    return "😊 Il manque un nombre ! Écris par exemple : 3 + 4 💪"


def injecter_verdict(user_message, historique, langue):
    """
    Injecte le verdict Python AVANT GPT.
    Inclut les étapes exactes de calcul pour que GPT
    explique EXACTEMENT la bonne méthode sans improviser.
    """
    verdict = verifier_reponse(user_message, historique)
    # Expression libre (pas d'exercice précédent) → étapes Python
    if verdict is None and est_nouvelle_expression(user_message):
        return injecter_etapes_expression(user_message, langue)
    if verdict is None:
        return user_message

    parties = verdict.split(':')

    if parties[0] == 'correct':
        # Récupérer les étapes pour expliquer POURQUOI c'est correct
        exercice = extraire_exercice(historique)
        etapes_str = ""
        if exercice and len(exercice) > 4 and exercice[4]:
            etapes_str = " → ".join(exercice[4])
        if langue == "العربية":
            return (f"{user_message}\n[VERDICT PYTHON: CORRECT ✅\n"
                    f"الجواب صحيح.\n"
                    f"الخطوات الصحيحة : {etapes_str}\n"
                    f"قل Bravo واشرح الخطوات بالضبط كما هي واطلب تمريناً جديداً]")
        else:
            return (f"{user_message}\n[VERDICT PYTHON: CORRECT ✅\n"
                    f"La réponse est juste.\n"
                    f"Étapes exactes : {etapes_str}\n"
                    f"Dis Bravo, rappelle ces étapes exactes et passe à la suite]")
    else:
        resultat = parties[1]
        etapes_str = " → ".join(parties[2].split('|')) if len(parties) > 2 and parties[2] else ""

        if langue == "العربية":
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌\n"
                f"الجواب الصحيح = {resultat}\n"
                f"الخطوات الصحيحة بالترتيب : {etapes_str}\n"
                f"1. شجع الطالب بلطف 😊\n"
                f"2. اشرح الخطوات بالضبط كما هي أعلاه (لا تبتكر خطوات أخرى)\n"
                f"3. أعطِ الجواب الصحيح = {resultat}\n"
                f"4. أعطِ تمريناً جديداً وانتظر جواب الطالب]"
            )
        else:
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌\n"
                f"Résultat correct = {resultat}\n"
                f"Étapes exactes dans l'ordre : {etapes_str}\n"
                f"1. Encourage l'élève avec douceur 😊\n"
                f"2. Explique CES étapes exactement telles qu'elles sont ci-dessus (ne les invente pas)\n"
                f"3. Donne la bonne réponse = {resultat}\n"
                f"4. Donne un nouvel exercice et attends la réponse]"
            )


def nettoyer_reponse(reply):
    """Supprime LaTeX et noms d'étapes."""
    etiquettes = [
        r'📖\s*EXPLICATION\s*[:\-–—]*\s*',
        r'✏️\s*EXERCICE\s*[:\-–—]*\s*\d*\s*',
        r'📝\s*CORRECTION\s*[:\-–—]*\s*',
        r'🎯\s*QUIZ\s*[:\-–—]*\s*',
        r'🏆\s*CONCLUSION\s*[:\-–—]*\s*',
        r'ÉTAPE\s*\d+\s*[:\-–—]*\s*',
        r'Étape\s*\d+\s*[:\-–—]*\s*',
        r'étape\s*\d+\s*[:\-–—]*\s*',
    ]
    for pattern in etiquettes:
        reply = re.sub(pattern, '', reply)
    reply = re.sub(r'\\\((.+?)\\\)', r'\1', reply)
    reply = re.sub(r'\\\[(.+?)\\\]', r'\1', reply)
    return reply.strip()


def post_traitement(reply, user_input, historique, langue):
    """Nettoie + corrige si GPT valide une réponse fausse."""
    reply = nettoyer_reponse(reply)

    verdict = verifier_reponse(user_input, historique)
    if verdict is None or verdict == 'correct':
        return reply

    resultat_correct = verdict.split(':')[1]
    mots_fr = ['bravo', 'correct', 'exact', 'parfait', 'excellent', 'très bien', 'super', 'juste']
    mots_ar = ['أحسنت', 'صحيح', 'ممتاز', 'رائع', 'جيد']
    gpt_faux = any(m in reply.lower() for m in mots_fr) or any(m in reply for m in mots_ar)

    if gpt_faux:
        # 1. On retire les encouragements et les mentions d'erreurs (🌟, Bravo, etc.)
        reply_clean = re.sub(
            r'(🌟\s*)?(Bravo|Excellent|Parfait|Super|Correct|أحسنت|ممتاز|C\'est courageux[^\n!]*[!.]?\s*)',
            '', reply, count=1, flags=re.IGNORECASE
        ).strip()
        
        # 2. On supprime aussi toute phrase qui contiendrait ", pas [chiffre]"
        # Cela évite les messages du type "La réponse est 0, pas 12"
        reply_clean = re.sub(r',?\s*pas\s*\d+', '', reply_clean)
        
        if langue == "العربية":
            return f"الجواب الصحيح هو **{resultat_correct}**. 😊\n\n{reply_clean}"
        else:
            # Ici, on ne met que la bonne réponse, sans le ", pas X"
            return f"La bonne réponse est **{resultat_correct}**. 😊\n\n{reply_clean}"
            
    return reply


def detecter_resultat_negatif(message):
    """
    Calcule le résultat global de l'expression pour vérifier 
    si le total final est négatif.
    """
    # 1. On ne garde que les chiffres et les symboles mathématiques
    # On remplace aussi les signes visuels (x, ÷) par les signes Python (*, /)
    calcul = re.sub(r'[^0-9+\-*/x÷\s]', '', message).replace('x', '*').replace('÷', '/')
    
    # S'il n'y a pas de chiffres ou de signes, on ignore
    if not re.search(r'\d', calcul) or not any(op in calcul for op in '+-*/'):
        return False

    try:
        # 2. On évalue l'expression complète (ex: 5 - 7 + 9)
        # eval() est sûr ici car on a filtré tout sauf les maths avec le regex ci-dessus
        resultat_final = eval(calcul)
        
        # 3. On ne bloque que si le résultat TOTAL est inférieur à 0
        return resultat_final < 0
    except:
        # En cas d'erreur de syntaxe (ex: "5 + -"), on laisse GPT gérer
        return False


def message_negatif(message, langue: str) -> str:
    """
    Cette fonction accepte maintenant DEUX arguments : 
    1. le message de l'élève (pour extraire les chiffres)
    2. la langue choisie
    """
    # On extrait les chiffres du message pour personnaliser l'explication
    match = re.search(r'(\d+)\s*-\s*(\d+)', message)
    # Si on trouve les chiffres, on les utilise, sinon on met des exemples par défaut
    a, b = (match.group(1), match.group(2)) if match else ("3", "10")
    
    if langue == "العربية":
        return (
            f"يا لك من بطل فضولي ! 🌟\n\n"
            f"تخيل لو كان لديك {a} تفاحات 🍎، هل يمكنك أن تعطي منها {b} لأصدقائك ؟ لا، لأنك لا تملك ما يكفي ! 😊\n\n"
            f"في الابتدائي، نطرح دائماً الصغير من الكبير. ستتعلم كيف تفعل ذلك في الإعدادي 📚\n\n"
            f"جرب وضع العدد الأكبر في البداية ! 💪"
        )
    else:
        return (
            f"Quelle bonne curiosité ! 🌟\n\n"
            f"Imagine : si tu as {a} bonbons 🍬, est-ce que tu peux en donner {b} à tes amis ? Non, car tu n'en as pas assez ! 😊\n\n"
            f"En primaire, on retire toujours un petit nombre d'un plus grand. Tu découvriras le secret des nombres négatifs au collège 📚\n\n"
            f"Essaie en mettant le plus grand nombre en premier ! 💪"
        )

# detecter_signe_incompatible supprimée
# → L'élève peut librement écrire 3+2-1 ou toute opération mixte

def detecter_message_incomprehensible(message: str) -> bool:
    """
    Détecte si le message est incompréhensible pour le tuteur :
    → Symboles seuls (=, ?, !, @...)
    → Un seul caractère non alphanumérique
    → Chaînes aléatoires sans sens mathématique
    """
    msg = message.strip()
    # Symboles seuls ou très courts sans contenu mathématique
    if len(msg) <= 2 and not re.search(r'\d', msg):
        return True
    # Uniquement des symboles non mathématiques
    if re.fullmatch(r'[=?!@#$%^&*_~`<>|\s]+', msg):
        return True
    # Chiffre suivi/précédé d'underscore (ex: 3_, _5)
    if re.fullmatch(r'\d+_|_\d+|_+', msg):
        return True
    return False
# → GPT gère le contexte pédagogique naturellement


# ============================================================
# 10. PROMPT — SYNCHRONISÉ AVEC app_rag.py
# ============================================================
def get_system_prompt(langue, context="", prenom="", niveau=""):
    """
    Prompt adaptatif avec prénom et niveau de l'élève.
    L'élève peut écrire librement : 3+2, 5-1, 3+2-1, 4×3...
    """
    if context:
        rag_section = f"""
📚 BASE DE CONNAISSANCES :
─────────────────────────
{context}
─────────────────────────
Utilise UNIQUEMENT ces extraits pour tes exemples et exercices.
"""
    else:
        rag_section = """
⚠️ Base de connaissances non disponible. Utilise tes connaissances générales du cycle primaire.
"""

    if langue == "العربية":
        r7_hors = '"ههه، خيالك واسع جداً ! لكن لكي تصبح بطلاً في الأرقام، يجب أن نركز على الرياضيات ! 🧮 هل نكمل المغامرة ؟"'
        r7_niv  = '"هذا سؤال للأبطال ! 🌟 هذا الموضوع يُدرَّس في المرحلة الإعدادية. لنكمل بالأعداد الكاملة في الوقت الحالي ! 💪"'
    else:
        r7_hors = '"Hihi, tu as beaucoup d\'imagination ! Mais pour devenir un magicien des nombres, restons concentrés sur les maths ! 🧮 Prêt à reprendre l\'aventure ?"'
        r7_niv  = '"C\'est une question de géant ! 🌟 Ce sujet est étudié au collège. Restons sur les nombres entiers pour l\'instant ! 💪"'

    # Section élève personnalisée
    section_eleve = ""
    if prenom:
        section_eleve += f"\n👦 L'élève s'appelle **{prenom}**. Utilise son prénom dans tes encouragements."
    if niveau:
        nv_map = {"CE1":"1ère année (6-7 ans)","CE2":"2ème année (7-8 ans)","CE3":"3ème année (8-9 ans)",
                  "CE4":"4ème année (9-10 ans)","CE5":"5ème année (10-11 ans)","CE6":"6ème année (11-12 ans)"}
        nv_desc = nv_map.get(niveau, niveau)
        section_eleve += f"\n📚 Niveau : **{nv_desc}**. Adapte la difficulté à ce niveau."
        if niveau in ("CE1","CE2","CE3"):
            section_eleve += "\n→ Nombres simples (< 20), une opération à la fois, beaucoup d'emojis."
        elif niveau in ("CE4","CE5"):
            section_eleve += "\n→ Nombres jusqu'à 100, opérations mixtes acceptées."
        else:
            section_eleve += "\n→ Grands nombres, fractions, opérations complexes autorisées."

    return f"""Tu es un tuteur de mathématiques bienveillant pour le cycle primaire (CE1 à CE6).
Langue : **{langue}**
{section_eleve}

{rag_section}

════════════════════════════════
RÈGLES ABSOLUES — LIRE EN PREMIER
════════════════════════════════

1. JAMAIS de LaTeX : écris 3 + 4 = 7, JAMAIS (3+4) ou [3+4]
2. JAMAIS le nom ou numéro d'étape : ❌ "Étape 3" ❌ "ÉTAPE 0"
3. JAMAIS "Bravo" si l'élève n'a pas répondu à un exercice posé par toi.
4. TOUJOURS UN SEUL exemple dans l'explication. JAMAIS deux.
5. Chiffres arabes uniquement : 0-9. JAMAIS ١٢٣
6. L'élève peut librement combiner des opérations (ex: 3+2-1). C'est normal et accepté.
7. L'exercice doit TOUJOURS utiliser des nombres DIFFÉRENTS de l'exemple.
8. Ne mentionne JAMAIS le mauvais nombre de l'élève dans ta réponse (ex: ne dis JAMAIS "pas 12" ou "au lieu de 5"). Donne uniquement le résultat correct.

════════════════════════════════
CHAPITRES COUVERTS (CE1 → CE6)
════════════════════════════════
Tu enseignes UNIQUEMENT ces 4 chapitres du primaire :
✅ Addition (+)
✅ Soustraction (-) → résultat toujours positif en primaire
✅ Multiplication (×)
✅ Fractions (/)

❌ Hors primaire (algèbre, géométrie, statistiques...) →
   "Hihi, c'est une question de géant ! On travaille sur les 4 opérations de base. 🧮"

════════════════════════════════
SÉQUENCE PÉDAGOGIQUE (ordre strict)
════════════════════════════════

📖 EXPLICATION (Apprentissage actif — OBLIGATOIRE avant tout exercice) :
Tu dois TOUJOURS expliquer AVANT de poser un exercice. L'explication suit 3 niveaux :

1. ANCRAGE CONCRET : Relie l'opération à un objet du quotidien de l'enfant.
   Exemples d'objets : bonbons 🍬, billes 🔵, pommes 🍎, doigts 🤚, étoiles ⭐
   ✅ "L'addition, c'est comme mettre des billes dans un sac."
   ❌ "L'addition est une opération qui consiste à..."

2. DÉCOMPOSITION VISUELLE : Montre le raisonnement étape par étape avec des emojis.
   - Addition 5+3 : "🍎🍎🍎🍎🍎 + 🍎🍎🍎 = 🍎🍎🍎🍎🍎🍎🍎🍎 → on compte : 8 !"
   - Soustraction 7-3 : "🍬🍬🍬🍬🍬🍬🍬 → on enlève 3 : 🍬🍬🍬🍬 → il reste 4 !"
   - Multiplication 3×4 : "3 groupes de 4 : 🔵🔵🔵🔵 | 🔵🔵🔵🔵 | 🔵🔵🔵🔵 → 12 !"
   - Fractions 1/2 : "Une pizza 🍕 coupée en 2 parts égales → tu prends 1 part → c'est 1/2 !"

3. STRATÉGIE MENTALE (ZPD) : Donne UNE technique concrète que l'enfant peut reproduire seul.
   - Addition : "Mets 5 dans ta tête 🧠, lève 3 doigts 🤚, compte : 6, 7, 8 !"
   - Soustraction : "Pars de 3, compte jusqu'à 7 sur tes doigts : 4, 5, 6, 7 → 4 doigts levés !"
   - Multiplication : "3×4 = 4+4+4. Compte par bonds de 4 : 4, 8, 12 !"
   - Fractions : "Divise par le bas, multiplie par le haut."

4. Termine TOUJOURS par : "Tu as compris ? 😊 Essaie maintenant !"

✏️ EXERCICE 1 (Vérification initiale) :
→ Pose UNIQUEMENT la question, rien d'autre.
→ "✏️ À toi ! Combien font [a] [op] [b] ? 😊"
→ Nombres DIFFÉRENTS de l'exemple.
→ ATTENDS la réponse en silence. Ne donne JAMAIS la réponse à l'avance.

📝 CORRECTION (Étayage actif — LE CŒUR DU PROJET) :
⚠️ PRINCIPE FONDAMENTAL : L'élève doit COMPRENDRE, pas juste recevoir la réponse.
⚠️ INTERDIT ABSOLU : Donner la réponse directement sans explication.

→ Si CORRECT :
   "🌟 Bravo [prénom si connu] ! Tu as trouvé [résultat] !
   Rappel de la méthode : [rappel court de la stratégie utilisée]
   Tu maîtrises vraiment bien ! 💪"

→ Si INCORRECT — SÉQUENCE OBLIGATOIRE EN 4 TEMPS :
   TEMPS 1 — ENCOURAGEMENT :
   "👏 C'est courageux d'avoir essayé ! On apprend ensemble. 😊"

   TEMPS 2 — DIAGNOSTIC (comprendre l'erreur) :
   Explique POURQUOI la réponse est fausse avec la méthode visuelle.
   Exemple pour 7+5=11 :
   "Tu as dit 11. Essayons ensemble : mets 7 dans ta tête 🧠,
   maintenant lève 5 doigts 🤚 et compte : 8, 9, 10, 11, 12...
   Tu vois ? On arrive à 12, pas 11 ! 😊"

   TEMPS 3 — GUIDAGE VERS LA RÉPONSE (Questionnement socratique) :
   Ne donne PAS la réponse. Pose une question pour guider :
   "Si tu as 7 billes et que tu en ajoutes 5,
   essaie de compter sur tes doigts depuis 7...
   Qu'est-ce que tu trouves ? 🤔"
   → ATTENDS que l'élève réponde à nouveau.

   TEMPS 4 — CONFIRMATION et RÉPONSE (seulement après la tentative guidée) :
   "Exactement ! La bonne réponse est [résultat].
   Tu vois la méthode ? [rappel court]
   Continue comme ça ! 💪"

→ JAMAIS de "Bravo" si c'est faux.
→ JAMAIS donner la réponse sans passer par les 4 temps.
→ Si l'élève donne encore la mauvaise réponse après guidage : reprends au TEMPS 2.

✏️ EXERCICE 2 (Application) :
→ Même format que l'exercice 1.
→ Si correct → passe au Quiz.
→ Si incorrect → reprends la séquence de correction en 4 temps.

🎯 QUIZ (Validation des acquis — 2 questions) :
→ "🎯 Question [n] : Combien font [a] [op] [b] ?"
→ UNE question à la fois. ATTENDS la réponse.
→ Corrige avec la même séquence en 4 temps si incorrect.

🏆 CONCLUSION (Transfert d'autonomie) :
"🏆 Félicitations ! Tu as vraiment bien travaillé aujourd'hui ! 😊
Tu sais maintenant [rappel de la stratégie apprise].
Tu peux utiliser cette technique tout seul !
Qu'est-ce que tu veux faire ?
  1️⃣ Encore des exercices
  2️⃣ Un autre sujet"

════════════════════════════════
RÈGLES DE CONTENU
════════════════════════════════

🔴 Résultats négatifs : Python gère ce cas automatiquement.
   Ne propose JAMAIS un exercice a-b si a < b.

🔴 RÈGLE DE PRIORITÉ DES OPÉRATIONS — OBLIGATOIRE :
Tu dois TOUJOURS respecter et expliquer les priorités dans cet ordre :

   PRIORITÉ 1 — × et ÷ se calculent EN PREMIER (de gauche à droite)
   PRIORITÉ 2 — + et − se calculent ENSUITE

Exemples avec × et ÷ — respecter la priorité :
   2 + 3 × 4 → d'abord 3×4=12, ensuite 2+12 = 14  ✅ (pas 20 !)
   10 − 2 × 3 → d'abord 2×3=6, ensuite 10−6 = 4   ✅
   6 + 4 ÷ 2 → d'abord 4÷2=2, ensuite 6+2 = 8      ✅

Exemples avec + et − seulement (même priorité) :
→ + et − ont la MÊME priorité donc on peut les réordonner si nécessaire.
→ Si la soustraction directe donne un négatif intermédiaire,
  REGROUPE les additions d'abord (résultat identique, pédagogiquement correct) :

   8 − 3 + 2 → 8−3=5, puis 5+2=7   ✅ (pas de négatif intermédiaire)
   5 + 4 − 6 → 5+4=9, puis 9−6=3   ✅ (pas de négatif intermédiaire)
   3 − 7 + 6 → REGROUPE : 3+6=9, puis 9−7=2  ✅ (évite 3-7=-4)
   5 − 7 + 9 → REGROUPE : 5+9=14, puis 14−7=7 ✅ (évite 5-7=-2)

⚠️ Le message contient [VERDICT PYTHON: INCORRECT ❌] avec les ÉTAPES EXACTES calculées par Python.
   Tu DOIS expliquer CES étapes exactement telles quelles — ne les change pas, ne les invente pas.
🔴 Décimaux :
→ Nombres entiers uniquement sauf si l'élève est visiblement en 5ème/6ème.
→ Si hors niveau → STOP + "👏 Tu découvriras les décimaux plus tard 📚 💪"

🔴 Signe _ : n'est PAS une soustraction → "👋 Utilise - pour soustraire : 3 - 2 😊"
🔴 Opération incomplète (3+, 5-) : "😊 Il manque un nombre ! Écris par exemple : 3 + 4 💪"

════════════════════════════════
LANGUE ET TON
════════════════════════════════
→ Réponds UNIQUEMENT en **{langue}**
→ Bascule FR/AR immédiatement si l'élève change de langue
→ Toujours bienveillant, encourageant, doux avec les enfants
→ Si message incompréhensible : "👋 Bonjour ! Je suis ton tuteur de maths 😊 Écris un calcul ou dis-moi ce que tu veux apprendre ! 🚀"
→ Hors maths : {r7_hors}
→ Hors primaire : {r7_niv}

════════════════════════════════
EXEMPLES DE COMPORTEMENT ATTENDU
════════════════════════════════

1. EXPLICATION COMPLÈTE (apprentissage actif) :
Élève : "je veux apprendre l'addition"
Tuteur : "👋 Bonjour ! 😊 L'addition, c'est comme mettre des billes dans un sac 🔵
  Si tu as 5 billes 🔵🔵🔵🔵🔵 et tu en ajoutes 3 🔵🔵🔵,
  tu comptes tout : 🔵🔵🔵🔵🔵🔵🔵🔵 = 8 billes !
  La technique : mets 5 dans ta tête 🧠, lève 3 doigts 🤚, compte : 6, 7, 8 !
  Tu as compris ? 😊 Essaie maintenant !
  ✏️ À toi ! Combien font 4 + 2 ? 😊"

2. CORRECTION EN 4 TEMPS (réponse incorrecte) :
Élève : "7 + 5 ça fait 11"
Tuteur : "👏 C'est courageux d'avoir essayé ! On apprend ensemble. 😊
  Regardons ensemble : mets 7 dans ta tête 🧠, lève 5 doigts 🤚 et compte :
  8... 9... 10... 11... 12 !
  Tu vois ? On arrive à 12. 😊
  Essaie encore : mets 7 dans ta tête et compte 5 doigts...
  Qu'est-ce que tu trouves ? 🤔"
[Élève répond 12]
Tuteur : "🌟 Exactement ! 7 + 5 = 12 ! Tu as trouvé tout seul avec la bonne méthode ! 💪
  ✏️ On continue ! Combien font 6 + 4 ?"

3. OPÉRATION LIBRE :
Élève : "3+2-1"
Tuteur : "👋 Bonjour ! Tu as écrit 3+2-1. Faisons-le en 2 étapes :
  Étape 1 : 3+2. Mets 3 dans ta tête 🧠, lève 2 doigts : 4, 5 → donc 3+2 = 5 !
  Étape 2 : 5-1. Tu as 5, tu en enlèves 1 : 🔵🔵🔵🔵 → il reste 4 !
  Donc 3+2-1 = 4 ! 🌟
  ✏️ À toi ! Combien font 4+3-2 ? 😊"

4. OPÉRATION INCOMPLÈTE :
Élève : "8 +"
Tuteur : "😊 Il manque un nombre ! Écris par exemple 8 + 4. Complète et on continue ! 💪"
"""

# ============================================================
# 11. MODÈLE GPT-4o
# ============================================================
@st.cache_resource
def get_llm(_api_key):
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.2,
        api_key=_api_key,
        max_tokens=600
    )

llm = get_llm(api_key)

# ============================================================
# 12. GESTION DE L'ÉTAT
# ============================================================
session_key    = "chat_session"
etape_key      = "etape_session"
score_key      = "score_session"
eleve_key      = "eleve_info"      # {prenom, niveau, session_db_id}
chat_actif_key = "chat_actif"      # True/False

if session_key    not in st.session_state: st.session_state[session_key]    = []
if etape_key      not in st.session_state: st.session_state[etape_key]      = "amorce"
if score_key      not in st.session_state: st.session_state[score_key]      = {"bonnes": 0, "total": 0}
if eleve_key      not in st.session_state: st.session_state[eleve_key]      = {"prenom": "", "niveau": "", "session_db_id": None}
if "debut_session" not in st.session_state: st.session_state["debut_session"] = None
if chat_actif_key not in st.session_state: st.session_state[chat_actif_key] = False

chat_history   = st.session_state[session_key]
etape_actuelle = st.session_state[etape_key]
score          = st.session_state[score_key]
eleve_info     = st.session_state[eleve_key]
chat_actif     = st.session_state[chat_actif_key]

# Score affiché dans la sidebar

# ============================================================
# 13. FORMULAIRE DÉMARRAGE ou BARRE INFO ÉLÈVE
# ============================================================
NIVEAUX_LIST = ["CE1 — 1ère année", "CE2 — 2ème année", "CE3 — 3ème année",
                "CE4 — 4ème année", "CE5 — 5ème année", "CE6 — 6ème année"]

if not chat_actif:
    # ── Formulaire prénom + niveau ──────────────────────────
    lbl_prenom = "👦 Ton prénom" if langue_choisie == "Français" else "👦 اسمك"
    lbl_niveau = "📚 Ton niveau" if langue_choisie == "Français" else "📚 مستواك"
    lbl_start  = "🚀 Commencer la discussion !" if langue_choisie == "Français" else "🚀 لنبدأ النقاش !"

    # Bandeau compact animé
    if langue_choisie == "Français":
        titre_html = (
            "<b style=\"font-size:1.05rem;\">🧮 Bienvenue !</b> "
            "Je suis ton tuteur IA en mathématiques.<br>"
            "<span style=\"font-size:0.87rem;font-weight:400;opacity:0.93;\">"
            "Veuillez écrire ton prénom, sélectionner un niveau et cliquer sur Commencer."
            "</span>"
        )
    else:
        titre_html = (
            "<b style=\"font-size:1.05rem;\">🧮 مرحباً !</b> "
            "أنا معلمك الذكي في الرياضيات.<br>"
            "<span style=\"font-size:0.87rem;font-weight:400;opacity:0.93;\">"
            "يرجى كتابة اسمك واختيار مستواك والنقر على ابدأ."
            "</span>"
        )
    st.markdown(f'''<div class="start-form" dir="{direction}"><h3>{titre_html}</h3></div>''', unsafe_allow_html=True)

    col_p, col_n = st.columns(2)
    with col_p:
        prenom_input = st.text_input(lbl_prenom, key="prenom_input",
                                     placeholder="Mounaim..." if langue_choisie=="Français" else "منعيم...")
    with col_n:
        niveau_input = st.selectbox(lbl_niveau, [""] + NIVEAUX_LIST, key="niveau_input",
                                    format_func=lambda x: "— Choisir —" if x == "" else x)

    btn_disabled = not (prenom_input.strip() and niveau_input)
    if st.button(lbl_start, use_container_width=True,
                 disabled=btn_disabled, key="btn_start",
                 type="primary"):
        # Ouvrir la session
        prenom = prenom_input.strip()
        niveau = niveau_input.split("—")[0].strip()  # "CE3"
        sid_db = db_creer_session(prenom, niveau, langue_choisie)
        st.session_state[eleve_key]      = {"prenom": prenom, "niveau": niveau, "session_db_id": sid_db}
        st.session_state[chat_actif_key] = True
        st.session_state["debut_session"] = __import__("datetime").datetime.now()
        # Message de bienvenue personnalisé
        if langue_choisie == "Français":
            msg_bv = f"👋 Bonjour **{prenom}** ! 🌟\n\nJe suis ton tuteur de mathématiques — niveau **{niveau}** 😊\n\n❓ Écris un calcul ou dis-moi ce que tu veux apprendre ! 🚀"
        else:
            msg_bv = f"👋 مرحباً **{prenom}** ! 🌟\n\nأنا معلمك للرياضيات — مستوى **{niveau}** 😊\n\n❓ اكتب عملية أو أخبرني بما تريد تعلمه ! 🚀"
        st.session_state[session_key] = [AIMessage(content=msg_bv)]
        st.rerun()

    # ── Footer toujours visible ──
    # ============================================================
    # 17. FOOTER + ACCÈS ADMIN SECRET
    # ============================================================
    st.markdown(f"""
    <style>
    .footer-text {{
        text-align: center; font-family: 'Fredoka One', cursive;
        font-size: 0.9em; margin-top: 20px; color: #764ba2;
    }}
    .footer-text a {{
        color: #764ba2; text-decoration: none; cursor: pointer;
    }}
    .footer-text a:hover {{ text-decoration: underline; }}
    </style>
    <div class="footer-text" dir="{direction}">
        🧮 <a href="?admin=1">TuteurIA</a> | Mounaim 2026 🌟
    </div>
    """, unsafe_allow_html=True)
    
    # ── Détection clic Admin via query params ────────────────────
    query_params = st.query_params
    if query_params.get("admin") == "1":
        st.markdown("---")
        st.markdown("### 🔐 Espace Administrateur")
    
        if "admin_ok" not in st.session_state:
            st.session_state["admin_ok"] = False
    
        if not st.session_state["admin_ok"]:
            pwd = st.text_input("Mot de passe :", type="password", key="admin_pwd")
            col_a, col_b = st.columns([1,3])
            with col_a:
                if st.button("🔓 Connexion", key="btn_admin_login"):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state["admin_ok"] = True
                        st.rerun()
                    else:
                        st.error("❌ Mot de passe incorrect")
        else:
            # ── Dashboard Admin ───────────────────────────────────
            col_titre, col_deco = st.columns([4,1])
            with col_titre:
                st.markdown("#### 📊 Tableau de bord")
            with col_deco:
                if st.button("🚪 Se déconnecter", key="btn_admin_deco",
                             type="secondary", use_container_width=True):
                    st.session_state["admin_ok"] = False
                    st.query_params.clear()
                    st.rerun()
    
            sessions = db_charger_sessions()
    
            if not sessions:
                st.info("Aucune session enregistrée pour l'instant.")
            else:
                import pandas as pd
                df = pd.DataFrame(sessions)
    
                # ── Métriques ─────────────────────────────────────
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{len(df)}</div>
                        <div class="lbl">Sessions totales</div>
                    </div>''', unsafe_allow_html=True)
                with c2:
                    moy = round(df["taux"].mean(), 1) if "taux" in df else 0
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{moy}%</div>
                        <div class="lbl">Taux moyen</div>
                    </div>''', unsafe_allow_html=True)
                with c3:
                    niveaux_uniq = df["niveau"].nunique() if "niveau" in df else 0
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{niveaux_uniq}</div>
                        <div class="lbl">Niveaux différents</div>
                    </div>''', unsafe_allow_html=True)
                with c4:
                    moy_msg = round(df["nb_messages"].mean(), 1) if "nb_messages" in df else 0
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{moy_msg}</div>
                        <div class="lbl">Messages/session</div>
                    </div>''', unsafe_allow_html=True)
    
                st.markdown("<br>", unsafe_allow_html=True)
    
                # ── Graphique par niveau ───────────────────────────
                if "niveau" in df and "taux" in df:
                    import plotly.express as px
                    fig = px.bar(
                        df.groupby("niveau")["taux"].mean().reset_index(),
                        x="niveau", y="taux",
                        color="taux",
                        color_continuous_scale=["#FF6B6B","#FFE66D","#4ECDC4"],
                        labels={"niveau": "Niveau", "taux": "Taux réussite %"},
                        title="Taux de réussite par niveau"
                    )
                    fig.update_layout(height=300, showlegend=False,
                                      plot_bgcolor="white", paper_bgcolor="white")
                    st.plotly_chart(fig, use_container_width=True)
    
                # ── Tableau sessions ───────────────────────────────
                st.markdown("#### 📋 Détail des sessions")
                cols_affich = [c for c in ["created_at","prenom","niveau","langue",
                                            "bonnes","total","taux","duree_minutes","nb_messages","etape_finale"]
                               if c in df.columns]
                st.dataframe(
                    df[cols_affich].rename(columns={
                        "created_at":"Date","prenom":"Prénom","niveau":"Niveau",
                        "langue":"Langue","bonnes":"Bonnes","total":"Total",
                        "taux":"Taux %","duree_minutes":"Durée (min)",
                        "nb_messages":"Messages","etape_finale":"Étape"
                    }),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "Taux %": st.column_config.ProgressColumn("Taux %", min_value=0, max_value=100),
                        "Durée (min)": st.column_config.NumberColumn("⏱️ Durée (min)"),
                    }
                )

                # ── Export CSV ────────────────────────────────────
                csv = df[cols_affich].to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Exporter CSV", csv,
                                   "sessions_pfe.csv", "text/csv",
                                   key="btn_export_csv")

    st.stop()

else:
    # ── Barre info élève (visible pendant la session) ────────
    prenom_disp = eleve_info.get("prenom","")
    niveau_disp = eleve_info.get("niveau","")
    st.markdown(
        f'<div class="eleve-info-bar" dir="{direction}">'
        f'👦 <strong>{prenom_disp}</strong> &nbsp;|&nbsp; 📚 {niveau_disp}</div>',
        unsafe_allow_html=True
    )

    # Affichage étape badge
    etape_label = ETAPES[langue_choisie].get(etape_actuelle, "")
    if etape_label and etape_actuelle != "amorce":
        st.markdown(f'<div class="etape-badge" dir="{direction}">{etape_label}</div>', unsafe_allow_html=True)

# ============================================================
# 14. AFFICHAGE HISTORIQUE + AUTO-SCROLL
# ============================================================
for msg in chat_history:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(f'<div dir="{direction}">{msg.content}</div>', unsafe_allow_html=True)

# Auto-scroll vers le dernier message
st.markdown("""
<script>
(function() {
    const scrollToBottom = () => {
        // Scroll vers le bas de la page entière
        window.parent.scrollTo({ top: window.parent.document.body.scrollHeight, behavior: "smooth" });
        // Aussi scroll le dernier message en vue
        const msgs = window.parent.document.querySelectorAll('[data-testid="stChatMessage"]');
        if (msgs.length > 0) {
            msgs[msgs.length - 1].scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    };
    setTimeout(scrollToBottom, 200);
    setTimeout(scrollToBottom, 600);
    setTimeout(scrollToBottom, 1200);
})();
</script>
""", unsafe_allow_html=True)

# Sidebar supprimée — boutons déplacés à la fin de la conversation

# ============================================================
# CSS IMPRESSION — Masquer sidebar/boutons, afficher conversation
# ============================================================
st.markdown("""
<style>
@media print {
    section[data-testid="stSidebar"],
    header, footer,
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    .stChatInput,
    .stButton,
    .no-print { display: none !important; }

    .stApp { background: white !important; }
    body { font-size: 13px !important; }

    [data-testid="stChatMessageUser"] {
        background: #667eea !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    [data-testid="stChatMessageAssistant"] {
        border-left: 4px solid #FFE66D !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# BOUTONS FIN DE CONVERSATION — Nouvelle + Imprimer
# ============================================================
lbl_new   = "🔄 Nouvelle conversation" if langue_choisie == "Français" else "🔄 محادثة جديدة"
lbl_print = "⬇️ Télécharger la discussion" if langue_choisie == "Français" else "⬇️ تحميل المحادثة"

col_n, col_p = st.columns(2)
with col_n:
    if st.button(lbl_new, use_container_width=True, key="btn_new"):
        # Sauvegarder la session avant reset
        sc  = st.session_state[score_key]
        inf = st.session_state[eleve_key]
        import datetime as _dt
        debut = st.session_state.get("debut_session")
        duree = int((_dt.datetime.now() - debut).total_seconds() / 60) if debut else 0
        db_maj_session(
            session_id    = inf.get("session_db_id"),
            bonnes        = sc["bonnes"],
            total         = sc["total"],
            nb_messages   = len(st.session_state[session_key]),
            etape_finale  = st.session_state.get(etape_key, "amorce"),
            duree_minutes = duree,
        )
        # Reset complet → retour au formulaire
        st.session_state[session_key]    = []
        st.session_state[etape_key]      = "amorce"
        st.session_state[score_key]      = {"bonnes": 0, "total": 0}
        st.session_state[eleve_key]      = {"prenom": "", "niveau": "", "session_db_id": None}
        st.session_state[chat_actif_key] = False
        st.session_state["debut_session"]  = None
        st.rerun()
with col_p:
    if st.button(lbl_print, use_container_width=True, key="btn_download_conv"):
        import datetime as _dt
        from fpdf import FPDF
        import re as _re
        prenom_d = st.session_state[eleve_key].get("prenom", "Élève")
        niveau_d = st.session_state[eleve_key].get("niveau", "")
        sc_d     = st.session_state[score_key]
        debut_d  = st.session_state.get("debut_session")
        duree_d  = int((_dt.datetime.now() - debut_d).total_seconds() / 60) if debut_d else 0
        taux_d   = round(sc_d["bonnes"]/sc_d["total"]*100) if sc_d["total"]>0 else 0
        inf_dl   = st.session_state[eleve_key]
        db_maj_session(
            session_id=inf_dl.get("session_db_id"), bonnes=sc_d["bonnes"],
            total=sc_d["total"], nb_messages=len(st.session_state[session_key]),
            etape_finale=st.session_state.get(etape_key,"amorce"), duree_minutes=duree_d)
        def _clean(txt):
            txt = _re.sub(r'[\U00010000-\U0010ffff]', '', txt)
            txt = _re.sub(r'[\u2600-\u27ff]', '', txt)
            return txt.replace('**','').replace('*','').strip()
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_fill_color(255,107,107)
        pdf.rect(0,0,210,35,'F')
        pdf.set_font("Helvetica","B",16)
        pdf.set_text_color(255,255,255)
        pdf.set_y(8)
        pdf.cell(0,10,"Tuteur IA Mathematiques",align="C",ln=True)
        pdf.set_font("Helvetica","",11)
        pdf.cell(0,8,f"Discussion - {prenom_d} ({niveau_d})",align="C",ln=True)
        pdf.set_y(42); pdf.set_text_color(100,100,120); pdf.set_font("Helvetica","",10)
        pdf.set_x(15); pdf.cell(60,7,f"Date : {_dt.datetime.now().strftime('%d/%m/%Y %H:%M')}",ln=False)
        pdf.cell(60,7,f"Niveau : {niveau_d}",ln=False)
        pdf.cell(60,7,f"Duree : {duree_d} minutes",ln=True)
        pdf.set_y(55); pdf.set_fill_color(240,255,254); pdf.set_text_color(15,110,86)
        pdf.set_font("Helvetica","B",12); pdf.set_x(15)
        pdf.cell(180,10,f"Score : {sc_d['bonnes']}/{sc_d['total']} - Taux : {taux_d}%",
                 border=1,align="C",fill=True,ln=True)
        pdf.ln(5)
        pdf.set_text_color(26,26,46)
        for msg in st.session_state[session_key]:
            is_eleve = isinstance(msg, HumanMessage)
            texte    = _clean(msg.content)
            if not texte: continue
            if is_eleve:
                pdf.set_fill_color(238,237,254); pdf.set_font("Helvetica","B",9)
                pdf.set_x(100); pdf.cell(95,6,"Eleve",ln=True,align="R")
                pdf.set_font("Helvetica","",9)
                for l in texte.split("\n"):
                    if l.strip(): pdf.set_x(100); pdf.multi_cell(95,5,l.strip(),fill=True,align="R")
            else:
                pdf.set_fill_color(225,245,238); pdf.set_font("Helvetica","B",9)
                pdf.set_x(15); pdf.cell(95,6,"Tuteur IA",ln=True)
                pdf.set_font("Helvetica","",9)
                for l in texte.split("\n"):
                    if l.strip(): pdf.set_x(15); pdf.multi_cell(95,5,l.strip(),fill=True)
            pdf.ln(2)
        pdf.set_y(-20); pdf.set_font("Helvetica","I",8); pdf.set_text_color(150,150,170)
        pdf.cell(0,8,"PFE - Tuteur IA Mathematiques - FSE Rabat 2025-2026",align="C")
        st.download_button(
            label="📥 Télécharger PDF" if langue_choisie=="Français" else "📥 تحميل PDF",
            data=bytes(pdf.output()),
            file_name=f"discussion_{prenom_d}_{_dt.datetime.now().strftime('%d%m%Y_%H%M')}.pdf",
            mime="application/pdf", key="btn_dl_pdf")

# ============================================================
# 16. CONVERSATION PRINCIPALE
# ============================================================
user_input = st.chat_input(t["chat_placeholder"])

if user_input:
    with st.chat_message("user"):
        st.markdown(f'<div dir="{direction}">{user_input}</div>', unsafe_allow_html=True)

    # ── Détection opération incomplète — Python AVANT GPT ────
    if detecter_operation_incomplete(user_input):
        reply_inc = message_operation_incomplete(langue_choisie)
        st.session_state[session_key].append(HumanMessage(content=user_input))
        st.session_state[session_key].append(AIMessage(content=reply_inc))
        with st.chat_message("assistant"):
            st.markdown(f'<div dir="{direction}">{reply_inc}</div>', unsafe_allow_html=True)
        st.rerun()

    # ── Détection message incompréhensible — Python AVANT GPT ─
    if detecter_message_incomprehensible(user_input):
        if langue_choisie == "العربية":
            reply_inc = "👋 مرحباً ! 😊 أنا معلم الرياضيات للسلك الابتدائي.\nاكتب عملية حسابية أو أخبرني بما تريد تعلمه ! 🚀"
        else:
            reply_inc = "👋 Bonjour ! 😊 Je suis ton tuteur de maths du cycle primaire.\nÉcris un calcul ou dis-moi ce que tu veux apprendre ! 🚀"
        st.session_state[session_key].append(HumanMessage(content=user_input))
        st.session_state[session_key].append(AIMessage(content=reply_inc))
        with st.chat_message("assistant"):
            st.markdown(f'<div dir="{direction}">{reply_inc}</div>', unsafe_allow_html=True)
        st.rerun()

    # ── Détection résultat négatif — Python AVANT GPT ──────
    if detecter_resultat_negatif(user_input):
        reply = message_negatif(user_input, langue_choisie) # Ajoute user_input ici ✅
        st.session_state[session_key].append(HumanMessage(content=user_input))
        st.session_state[session_key].append(AIMessage(content=reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div dir="{direction}">{reply}</div>', unsafe_allow_html=True)
        st.rerun()

    # detecter_signe_incompatible supprimée — opérations mixtes acceptées ✅

    # RAG
    context = ""
    if vectorstore:
        query   = f"mathématiques primaire {user_input}"
        docs    = vectorstore.similarity_search(query, k=3)
        context = "\n\n".join([doc.page_content for doc in docs])

    # Prompt
    prenom_eleve  = st.session_state[eleve_key].get("prenom", "")
    niveau_eleve  = st.session_state[eleve_key].get("niveau", "")
    system_prompt = get_system_prompt(langue_choisie, context,
                                      prenom=prenom_eleve, niveau=niveau_eleve)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    with st.chat_message("assistant"):
        with st.spinner(t["thinking"]):
            try:
                # ── Injection verdict Python AVANT GPT ──────
                message_avec_verdict = injecter_verdict(
                    user_input, chat_history, langue_choisie
                )

                response        = (prompt | llm).invoke({
                    "input": message_avec_verdict,
                    "chat_history": chat_history[-10:]
                })
                assistant_reply = response.content

                # ── Nettoyage + validation Python APRÈS GPT ─
                assistant_reply = post_traitement(
                    assistant_reply, user_input, chat_history, langue_choisie
                )

                # Détection étape
                reply_lower = assistant_reply.lower()
                if "✏️" in assistant_reply or "exercice" in reply_lower or "تمرين" in assistant_reply:
                    st.session_state[etape_key] = "exercice"
                    st.session_state[score_key]["total"] += 1
                    if "VERDICT PYTHON: CORRECT" in message_avec_verdict:
                        st.session_state[score_key]["bonnes"] += 1
                elif "🎯" in assistant_reply or "quiz" in reply_lower or "اختبار" in assistant_reply:
                    st.session_state[etape_key] = "quiz"
                    st.session_state[score_key]["total"] += 1
                    if "VERDICT PYTHON: CORRECT" in message_avec_verdict:
                        st.session_state[score_key]["bonnes"] += 1
                elif "🏆" in assistant_reply or "félicitations" in reply_lower or "أحسنت" in assistant_reply:
                    st.session_state[etape_key] = "felicitations"
                elif "🌟" in assistant_reply:
                    st.session_state[etape_key] = "encouragement"

                st.markdown(f'<div dir="{direction}">{assistant_reply}</div>', unsafe_allow_html=True)

            except Exception as e:
                st.error(f"❌ Erreur : {e}")
                st.stop()

    st.session_state[session_key].append(HumanMessage(content=user_input))
    st.session_state[session_key].append(AIMessage(content=assistant_reply))
    # Sauvegarder les messages dans Supabase
    sid_db = st.session_state[eleve_key].get("session_db_id")
    db_ajouter_message(sid_db, "eleve",  user_input)
    db_ajouter_message(sid_db, "tuteur", assistant_reply)
    # Mise à jour stats en temps réel
    sc = st.session_state[score_key]
    db_maj_session(
        session_id   = sid_db,
        bonnes       = sc["bonnes"],
        total        = sc["total"],
        nb_messages  = len(st.session_state[session_key]),
        etape_finale = st.session_state.get(etape_key, "amorce"),
    )
    st.rerun()

# ============================================================
# 17. FOOTER + ACCÈS ADMIN SECRET
# ============================================================
st.markdown(f"""
<style>
.footer-text {{
    text-align: center; font-family: 'Fredoka One', cursive;
    font-size: 0.9em; margin-top: 20px; color: #764ba2;
}}
.footer-text a {{
    color: #764ba2; text-decoration: none; cursor: pointer;
}}
.footer-text a:hover {{ text-decoration: underline; }}
</style>
<div class="footer-text" dir="{direction}">
    🧮 <a href="?admin=1">TuteurIA</a> | Mounaim 2026 🌟
</div>
""", unsafe_allow_html=True)

# ── Détection clic Admin via query params ────────────────────
query_params = st.query_params
if query_params.get("admin") == "1":
    st.markdown("---")
    st.markdown("### 🔐 Espace Administrateur")

    if "admin_ok" not in st.session_state:
        st.session_state["admin_ok"] = False

    if not st.session_state["admin_ok"]:
        pwd = st.text_input("Mot de passe :", type="password", key="admin_pwd2")
        col_a, col_b = st.columns([1,3])
        with col_a:
            if st.button("🔓 Connexion", key="btn_admin_login2"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state["admin_ok"] = True
                    st.rerun()
                else:
                    st.error("❌ Mot de passe incorrect")
    else:
        # ── Dashboard Admin ───────────────────────────────────
        col_titre, col_deco = st.columns([4,1])
        with col_titre:
            st.markdown("#### 📊 Tableau de bord")
        with col_deco:
            if st.button("🚪 Se déconnecter", key="btn_admin_deco2",
                         type="secondary", use_container_width=True):
                st.session_state["admin_ok"] = False
                st.query_params.clear()
                st.rerun()

        sessions = db_charger_sessions()

        if not sessions:
            st.info("Aucune session enregistrée pour l'instant.")
        else:
            import pandas as pd
            df = pd.DataFrame(sessions)

            # ── Métriques ─────────────────────────────────────
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'''<div class="admin-metric">
                    <div class="val">{len(df)}</div>
                    <div class="lbl">Sessions totales</div>
                </div>''', unsafe_allow_html=True)
            with c2:
                moy = round(df["taux"].mean(), 1) if "taux" in df else 0
                st.markdown(f'''<div class="admin-metric">
                    <div class="val">{moy}%</div>
                    <div class="lbl">Taux moyen</div>
                </div>''', unsafe_allow_html=True)
            with c3:
                niveaux_uniq = df["niveau"].nunique() if "niveau" in df else 0
                st.markdown(f'''<div class="admin-metric">
                    <div class="val">{niveaux_uniq}</div>
                    <div class="lbl">Niveaux différents</div>
                </div>''', unsafe_allow_html=True)
            with c4:
                moy_msg = round(df["nb_messages"].mean(), 1) if "nb_messages" in df else 0
                st.markdown(f'''<div class="admin-metric">
                    <div class="val">{moy_msg}</div>
                    <div class="lbl">Messages/session</div>
                </div>''', unsafe_allow_html=True)

            # Ligne 2 — métriques durée
            if "duree_minutes" in df.columns and df["duree_minutes"].sum() > 0:
                df_d = df[df["duree_minutes"] > 0]
                d1, d2, d3, d4 = st.columns(4)
                with d1: st.metric("⏱️ Durée moy.", f"{round(df_d['duree_minutes'].mean(),1)} min")
                with d2: st.metric("⏱️ Durée totale", f"{int(df_d['duree_minutes'].sum())} min")
                with d3: st.metric("⏱️ Min. session", f"{int(df_d['duree_minutes'].min())} min")
                with d4: st.metric("⏱️ Max. session", f"{int(df_d['duree_minutes'].max())} min")

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Graphique par niveau ───────────────────────────
            if "niveau" in df and "taux" in df:
                import plotly.express as px
                fig = px.bar(
                    df.groupby("niveau")["taux"].mean().reset_index(),
                    x="niveau", y="taux",
                    color="taux",
                    color_continuous_scale=["#FF6B6B","#FFE66D","#4ECDC4"],
                    labels={"niveau": "Niveau", "taux": "Taux réussite %"},
                    title="Taux de réussite par niveau"
                )
                fig.update_layout(height=300, showlegend=False,
                                  plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)

            # ── Tableau sessions ───────────────────────────────
            st.markdown("#### 📋 Détail des sessions")
            cols_affich = [c for c in ["created_at","prenom","niveau","langue",
                                        "bonnes","total","taux","duree_minutes","nb_messages","etape_finale"]
                           if c in df.columns]
            st.dataframe(
                df[cols_affich].rename(columns={
                    "created_at":"Date","prenom":"Prénom","niveau":"Niveau",
                    "langue":"Langue","bonnes":"Bonnes","total":"Total",
                    "taux":"Taux %","duree_minutes":"Durée (min)",
                    "nb_messages":"Messages","etape_finale":"Étape"
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "Taux %": st.column_config.ProgressColumn("Taux %", min_value=0, max_value=100),
                    "Durée (min)": st.column_config.NumberColumn("⏱️ Durée (min)"),
                }
            )

            # ── Export CSV ────────────────────────────────────
            csv = df[cols_affich].to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Exporter CSV", csv,
                               "sessions_pfe.csv", "text/csv",
                               key="btn_export_csv2")
