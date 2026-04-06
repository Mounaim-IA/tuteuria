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
        font-size: 0.65em;
        font-weight: 500;
        display: block;
        margin-top: 2px;
        letter-spacing: 0.1px;
    }
    @media (max-width: 600px) {
        .header-chapitres { font-size: 0.55em !important; }
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
        .header-subtitle { font-size: 0.72em !important; }
        .main .block-container { padding-top: 70px !important; }
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
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. TRADUCTIONS FR/AR
# ============================================================
UI = {
    "Français": {
        "app_title":    "Tuteur Maths Primaire",
        "app_subtitle": "Cycle Primaire — 1ère à 6ème année",
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
        "app_subtitle": "السلك الابتدائي — من السنة الأولى إلى السادسة",
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
    """Utilise la DERNIÈRE occurrence de ✏️ ou 🎯 (rindex)."""
    patterns = [
        (r'(\d+)\s*\+\s*(\d+)', '+'),
        (r'(\d+)\s*-\s*(\d+)',  '-'),
        (r'(\d+)\s*[×x\*]\s*(\d+)', '*'),
    ]
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
                for pattern, op in patterns:
                    match = re.search(pattern, texte_exercice)
                    if match:
                        a, b = int(match.group(1)), int(match.group(2))
                        if op == '+': return (a, '+', b, a + b)
                        elif op == '-' and a >= b: return (a, '-', b, a - b)
                        elif op == '*': return (a, '*', b, a * b)
            break
    return None


def verifier_reponse(user_message, historique):
    exercice = extraire_exercice(historique)
    if not exercice: return None
    a, op, b, resultat_attendu = exercice
    nombres = re.findall(r'\d+', user_message.strip())
    if not nombres: return None
    return 'correct' if int(nombres[0]) == resultat_attendu else f'incorrect:{resultat_attendu}'


def injecter_verdict(user_message, historique, langue):
    """Injecte le verdict Python AVANT GPT."""
    verdict = verifier_reponse(user_message, historique)
    if verdict is None:
        return user_message
    if verdict == 'correct':
        if langue == "العربية":
            return f"{user_message}\n[VERDICT PYTHON: CORRECT ✅ — قل Bravo وشرح لماذا صحيح ثم انتقل للخطوة التالية]"
        else:
            return f"{user_message}\n[VERDICT PYTHON: CORRECT ✅ — Dis Bravo, explique pourquoi correct et passe à la suite]"
    else:
        resultat = verdict.split(':')[1]
        if langue == "العربية":
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌ — الجواب الصحيح = {resultat}\n"
                f"1. شجع الطالب بلطف 😊\n"
                f"2. اشرح كيف نحسب الجواب خطوة بخطوة\n"
                f"3. أعطِ الجواب الصحيح = {resultat}\n"
                f"4. أعطِ تمريناً جديداً وانتظر جواب الطالب]"
            )
        else:
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌ — Résultat correct = {resultat}\n"
                f"1. Encourage l'élève avec douceur 😊\n"
                f"2. Explique comment calculer étape par étape\n"
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
        reply_sans_bravo = re.sub(
            r'(🌟\s*)?(Bravo|Excellent|Parfait|Super|Correct|أحسنت|ممتاز)[^\n!]*[!.]?\s*',
            '', reply, count=1, flags=re.IGNORECASE
        ).strip()
        if langue == "العربية":
            return f"👏 أحسنت على المحاولة ! الجواب الصحيح هو **{resultat_correct}** 😊\n\n{reply_sans_bravo}"
        else:
            return f"👏 C'est bien d'avoir essayé ! La bonne réponse est **{resultat_correct}** 😊\n\n{reply_sans_bravo}"
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
def get_system_prompt(langue, context=""):
    """
    Prompt sans niveau ni chapitre fixe.
    GPT détecte automatiquement le sujet et adapte la pédagogie.
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

    return f"""Tu es un tuteur de mathématiques bienveillant pour le cycle primaire marocain (CE1 à CE6).
Langue : **{langue}**

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

OPÉRATIONS MIXTES (ex: 3 - 6 + 8) :
Si la première soustraction est impossible (3-6), apprends à l'élève à changer l'ordre pour mettre l'addition en premier :
1. "On déplace les nombres : 3 - 6 + 8 devient 3 + 8 - 6"
2. Étape 1 (Addition) : 3 + 8 = 11
3. Étape 2 (Soustraction) : 11 - 6 = 5
✅ Résultat final = 5.
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
session_key = "chat_session"
etape_key   = "etape_session"
score_key   = "score_session"

if session_key not in st.session_state: st.session_state[session_key] = []
if etape_key   not in st.session_state: st.session_state[etape_key]   = "amorce"
if score_key   not in st.session_state: st.session_state[score_key]   = {"bonnes": 0, "total": 0}

chat_history   = st.session_state[session_key]
etape_actuelle = st.session_state[etape_key]
score          = st.session_state[score_key]

etape_label = ETAPES[langue_choisie].get(etape_actuelle, "")
if etape_label and etape_actuelle != "amorce":
    st.markdown(f'<div class="etape-badge" dir="{direction}">{etape_label}</div>', unsafe_allow_html=True)

# Score affiché dans la sidebar

# ============================================================
# 13. MESSAGE DE BIENVENUE
# ============================================================
if len(chat_history) == 0:
    chat_history.append(AIMessage(content=""))

if len(chat_history) == 1 and isinstance(chat_history[0], AIMessage):
    if langue_choisie == "Français":
        msg = f"👋 Bonjour ! 🌟\n\nJe suis ton tuteur de mathématiques du cycle primaire 😊\n\n❓ Écris un calcul ou dis-moi ce que tu veux apprendre ! 🚀"
    else:
        msg = f"👋 مرحباً بك ! 🌟\n\nأنا معلم الرياضيات للسلك الابتدائي 😊\n\n❓ اكتب عملية حسابية أو أخبرني بما تريد تعلمه ! 🚀"
    chat_history[0] = AIMessage(content=msg)

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
lbl_print = "🖨️ Imprimer la leçon"   if langue_choisie == "Français" else "🖨️ طباعة الدرس"

col_n, col_p = st.columns(2)
with col_n:
    if st.button(lbl_new, use_container_width=True, key="btn_new"):
        st.session_state[session_key] = []
        st.session_state[etape_key]   = "amorce"
        st.session_state[score_key]   = {"bonnes": 0, "total": 0}
        st.rerun()
with col_p:
    if st.button(lbl_print, use_container_width=True, key="btn_print_lecon"):
        st.session_state["do_print"] = True

if st.session_state.get("do_print"):
    st.session_state["do_print"] = False
    # Injection JS robuste — fonctionne sur PC et mobile
    st.components.v1.html("""
    <script>
        window.parent.print();
    </script>
    """, height=0)

# ============================================================
# 16. CONVERSATION PRINCIPALE
# ============================================================
user_input = st.chat_input(t["chat_placeholder"])

if user_input:
    with st.chat_message("user"):
        st.markdown(f'<div dir="{direction}">{user_input}</div>', unsafe_allow_html=True)

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
    system_prompt = get_system_prompt(langue_choisie, context)
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
    st.rerun()

# ============================================================
# 17. FOOTER
# ============================================================
st.markdown(f"""
<style>
.footer-text {{
    text-align: center; font-family: 'Fredoka One', cursive;
    font-size: 0.9em; margin-top: 20px; color: #764ba2;
}}
</style>
<div class="footer-text" dir="{direction}">{t['footer']}</div>
""", unsafe_allow_html=True)
