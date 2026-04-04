__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import os
import re
import streamlit as st
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
        border-radius: 25px;
        padding: 30px 20px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 15px 40px rgba(0,0,0,0.2);
        border: 4px solid white;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .header-icon { font-size: 70px; animation: bounce 1.5s infinite; display: block; }
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-15px); }
    }
    .header-title {
        font-family: 'Fredoka One', cursive;
        color: white; font-size: 2.5em;
        text-shadow: 3px 3px 0px rgba(0,0,0,0.2);
        margin: 10px 0 5px 0;
    }
    .header-subtitle { color: rgba(255,255,255,0.95); font-size: 1.1em; font-weight: 800; }
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
        border-radius: 15px; padding: 10px 20px; text-align: center;
        font-family: 'Fredoka One', cursive; font-size: 1.1em;
        color: white; margin-bottom: 15px;
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
    .main .block-container { max-width: 800px; padding: 1rem 1.5rem; }
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
        "footer":       "🧮 Tuteur Maths Primaire | PFE FSE Rabat 🌟"
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
# 4. CHAPITRES PAR NIVEAU
# ============================================================
CHAPITRES_PAR_NIVEAU = {
    "1ère année": ["Addition", "Soustraction"],
    "2ème année": ["Addition", "Soustraction", "Multiplication"],
    "3ème année": ["Addition", "Soustraction", "Multiplication"],
    "4ème année": ["Addition", "Soustraction", "Multiplication", "Fractions"],
    "5ème année": ["Addition", "Soustraction", "Multiplication", "Fractions"],
    "6ème année": ["Addition", "Soustraction", "Multiplication", "Fractions"],
}

NIVEAUX = {
    "1ère année": {"emoji": "🌱", "fr": "1ère année", "ar": "السنة الأولى"},
    "2ème année": {"emoji": "🌿", "fr": "2ème année", "ar": "السنة الثانية"},
    "3ème année": {"emoji": "🌳", "fr": "3ème année", "ar": "السنة الثالثة"},
    "4ème année": {"emoji": "⭐", "fr": "4ème année", "ar": "السنة الرابعة"},
    "5ème année": {"emoji": "🌟", "fr": "5ème année", "ar": "السنة الخامسة"},
    "6ème année": {"emoji": "🏆", "fr": "6ème année", "ar": "السنة السادسة"},
}

CHAPITRES = {
    "Addition":       {"emoji": "➕", "fr": "Addition",       "ar": "الجمع"},
    "Soustraction":   {"emoji": "➖", "fr": "Soustraction",   "ar": "الطرح"},
    "Multiplication": {"emoji": "✖️", "fr": "Multiplication", "ar": "الضرب"},
    "Fractions":      {"emoji": "🔢", "fr": "Fractions",      "ar": "الكسور"},
}

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
# 5. SÉLECTION LANGUE
# ============================================================
st.markdown('<div class="selector-title">🌐 Choisis ta langue / اختر لغتك</div>', unsafe_allow_html=True)
langue_choisie = st.radio(
    "Langue", ["Français", "العربية"],
    horizontal=True, label_visibility="collapsed", key="langue_radio"
)
t         = UI[langue_choisie]
direction = "rtl" if langue_choisie == "العربية" else "ltr"

# ============================================================
# 6. HEADER
# ============================================================
st.markdown(f"""
<div class="header-container" dir="{direction}">
    <span class="header-icon">🧮</span>
    <div class="header-title">{t['app_title']}</div>
    <div class="header-subtitle">{t['app_subtitle']}</div>
</div>
""", unsafe_allow_html=True)

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
# 8. SÉLECTION NIVEAU ET CHAPITRE (dynamiques)
# ============================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown(f'<div class="selector-title">{t["choose_level"]}</div>', unsafe_allow_html=True)
    niveau_cle = st.selectbox(
        "Niveau", list(NIVEAUX.keys()),
        format_func=lambda x: NIVEAUX[x]["ar"] if langue_choisie == "العربية" else NIVEAUX[x]["fr"],
        label_visibility="collapsed"
    )

chapitres_dispo = CHAPITRES_PAR_NIVEAU.get(niveau_cle, ["Addition", "Soustraction"])

with col2:
    st.markdown(f'<div class="selector-title">{t["choose_chap"]}</div>', unsafe_allow_html=True)
    chapitre_cle = st.selectbox(
        "Chapitre", chapitres_dispo,
        format_func=lambda x: CHAPITRES[x]["ar"] if langue_choisie == "العربية" else CHAPITRES[x]["fr"],
        label_visibility="collapsed"
    )

niveau_info          = NIVEAUX[niveau_cle]
chapitre_info        = CHAPITRES[chapitre_cle]
niveau_nom_affiche   = niveau_info["ar"]   if langue_choisie == "العربية" else niveau_info["fr"]
chapitre_nom_affiche = chapitre_info["ar"] if langue_choisie == "العربية" else chapitre_info["fr"]

st.markdown(f"""
<div class="progress-badge" dir="{direction}">
    {niveau_info['emoji']} {niveau_nom_affiche} &nbsp;|&nbsp; {chapitre_info['emoji']} {chapitre_nom_affiche}
</div>
""", unsafe_allow_html=True)

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
    """Détecte une soustraction à résultat négatif."""
    match = re.search(r'(\d+)\s*-\s*(\d+)', message)
    if match:
        a, b = int(match.group(1)), int(match.group(2))
        if a < b:
            return True
    return False


def message_negatif(langue: str) -> str:
    if langue == "العربية":
        return (
            "يا لك من بطل فضولي ! 🌟\n\n"
            "تخيل لو كان لديك 3 تفاحات 🍎، هل يمكنك أن تعطي منها 10 لأصدقائك ؟ لا، لأنك لا تملك ما يكفي ! 😊\n\n"
            "في الابتدائي، نطرح دائماً الصغير من الكبير. ستتعلم كيف تفعل ذلك في الإعدادي 📚\n\n"
            "جرب وضع العدد الأكبر في البداية ! 💪"
        )
    else:
        return (
            "Quelle bonne curiosité ! 🌟\n\n"
            "Imagine : si tu as 3 bonbons 🍬, est-ce que tu peux en donner 10 à tes amis ? Non, car tu n'en as pas assez ! 😊\n\n"
            "En primaire, on retire toujours un petit nombre d'un plus grand. Tu découvriras le secret des nombres négatifs au collège 📚\n\n"
            "Essaie en mettant le plus grand nombre en premier ! 💪"
        )

def detecter_signe_incompatible(message, chapitre_cle, langue):
    """Détecte un signe d'un autre chapitre."""
    msg = message.lower().strip()
    mots_ok = [
        "changer", "autre", "quitter", "menu", "leçon", "cours", "بدل", "تغيير",
        "addition", "soustraction", "multiplication", "fractions",
        "الجمع", "الطرح", "الضرب", "الكسور",
        "oui", "non", "rester", "continuer", "نعم", "لا", "أريد", "بقاء"
    ]
    if any(m in msg for m in mots_ok):
        return None

    DICO_REGEX = {
        "Addition":       r"(\d\s*\+\s*\d|\s\+\s)",
        "Soustraction":   r"(\d\s*-\s*\d|\s-\s)",
        "Multiplication": r"(\d\s*[×\*x]\s*\d|\s[×\*x]\s)",
        "Fractions":      r"(\d\s*[\/÷]\s*\d|\s[\/÷]\s)",
    }
    for chap, pattern in DICO_REGEX.items():
        if chap == chapitre_cle:
            continue
        if re.search(pattern, msg):
            chap_fr = {"Addition": "l'Addition", "Soustraction": "la Soustraction",
                       "Multiplication": "la Multiplication", "Fractions": "les Fractions"}
            chap_ar = {"Addition": "الجمع", "Soustraction": "الطرح",
                       "Multiplication": "الضرب", "Fractions": "الكسور"}
            nom_chap = chap_ar[chapitre_cle] if langue == "العربية" else chap_fr[chapitre_cle]
            if langue == "العربية":
                return f"😊 لاحظت أنك تستخدم علامة من درس آخر !\nدرسنا اليوم هو **{nom_chap}**.\nهل تريد الاستمرار مع **{nom_chap}** ؟\nأجب بـ **نعم** أو **لا** 😊"
            else:
                return f"😊 Je remarque que tu utilises un signe d'un autre chapitre !\nNotre séance porte sur **{nom_chap}**.\nTu veux continuer avec **{nom_chap}** ?\nRéponds par **Oui** ou **Non** 😊"
    return None


# ============================================================
# 10. PROMPT — SYNCHRONISÉ AVEC app_rag.py
# ============================================================
def get_system_prompt(niveau, chapitre_nom, langue, context=""):
    if context:
        rag_section = f"""
📚 BASE DE CONNAISSANCES :
─────────────────────────
{context}
─────────────────────────
Utilise UNIQUEMENT ces extraits. Ne génère JAMAIS de contenu hors de ces extraits.
"""
    else:
        rag_section = """
⚠️ Contenu non disponible. Dis : "Je n'ai pas encore ce contenu. Choisis un autre chapitre 📚"
"""

    if langue == "العربية":
        r6_msg = f'قل : "لاحظت علامة من درس آخر. درسنا **{chapitre_nom}**. هل تريد الاستمرار ؟ نعم أو لا."'
        r6_oui = f'نعم → استأنف **{chapitre_nom}**'
        r6_non = "موافق ! لتغيير الدرس، يرجى استخدام القائمة المنسدلة في أعلى اليمين. هذا هو المكان الذي يمكنك فيه اختيار درس جديد ! 📚"
        r7_hors = f'"ههه، خيالك واسع جداً !  لكن لكي تصبح بطلاً في الأرقام، يجب أن نركز على مهمتنا السرية: إتقان **{chapitre_nom}** ! 🧮 هل نكمل المغامرة ؟"'
        r7_chap = '"اختر هذا الدرس من القائمة 📚"'
        r7_niv  = '"هذا سؤال للأبطال ! 🌟 حالياً نتعلم العد بالأشياء الكاملة. لاحقاً ستتعلم عد القطع الصغيرة ! 🍰 لنكمل تدريبنا بالأعداد الكاملة ! 💪"'
    else:
        r6_msg = f'Dis : "Je remarque un signe d\'un autre chapitre. Notre séance : **{chapitre_nom}**. Tu continues ? Oui ou Non."'
        r6_oui = f'Oui → reprends **{chapitre_nom}**'
        r6_non = "D'accord ! Pour changer de leçon, utilise le menu déroulant en haut à gauche. C'est là que tu peux choisir une nouvelle mission ! 📚"
        r7_hors = f'"Hihi, tu as beaucoup d\'imagination !  Mais pour devenir un magicien des nombres, restons concentrés sur notre mission : la **{chapitre_nom}** ! 🧮 Prêt à reprendre l\'aventure ?"'
        r7_chap = '"Choisis ce chapitre dans le menu 📚"'
        r7_niv  = '"C\'est une question de géant ! 🌟 Pour l\'instant, on compte avec des objets entiers. Plus tard, tu apprenras à compter les morceaux et les miettes ! 🍰 Restons sur les nombres entiers ! 💪"'
    return f"""Tu es un tuteur de mathématiques pour enfants du cycle primaire.
Niveau : **{niveau}** | Chapitre : **{chapitre_nom}** | Langue : **{langue}**

{rag_section}

════════════════════════════════
RÈGLES ABSOLUES — LIRE EN PREMIER
════════════════════════════════

1. JAMAIS de LaTeX : écris 3 + 4 = 7, JAMAIS (3+4) ou [3+4]
2. JAMAIS le nom ou numéro d'étape : ❌ "Étape 3" ❌ "ÉTAPE 0" ❌ "📖 EXPLICATION :"
3. JAMAIS "Bravo" si l'élève n'a pas répondu à un exercice posé par toi.
4. TOUJOURS UN SEUL exemple dans l'explication. JAMAIS deux.
5. Chiffres arabes uniquement : 0-9. JAMAIS ١٢٣
6. INTERDICTION : L'exercice doit TOUJOURS utiliser des nombres différents de l'exemple. Si l'exemple est 3 x 7, l'exercice doit être 4 x 2 ou 3 x 5. Ne donne JAMAIS la réponse de l'exercice dans l'explication.

════════════════════════════════
SÉQUENCE PÉDAGOGIQUE (ordre strict)
════════════════════════════════

📖 EXPLICATION (Enseignement de la méthode) :
1. ANALOGIE : Explique **{chapitre_nom}** avec un objet concret (pommes 🍎, billes 🔵) + emojis.
2. STRATÉGIE MENTALE : Montre comment faire dans sa tête.
   - Addition : "Mets le plus gros nombre dans ta tête (ex: 6) et compte la suite sur tes doigts (7, 8...)."
   - Soustraction : "Pars du petit nombre et regarde combien il manque pour arriver au grand."
3. MODÉLISATION : Détaille un exemple : "Pour 5 + 3, je garde 5 dans ma tête et j'ajoute 3 doigts : 6, 7, 8 ! 😊"
4. Termine par : "On essaie ensemble ? 😊 Prêt à utiliser tes doigts ?"

✏️ EXERCICE 1 :
→ "✏️ À toi ! Combien font [a] [op] [b] ? 😊"
→ Nombres DIFFÉRENTS de l'exemple. ATTENDS la réponse.

📝 CORRECTION (Étayage indiciel progressif) :
→ Si CORRECT : "🌟 Bravo ! Tu as utilisé la bonne technique. [Rappel bref]."
→ Si INCORRECT : 
   1. "👏 C'est bien d'avoir essayé ! On apprend ensemble."
   2. INDICE MÉTHODOLOGIQUE : "Mets {{{{a}}}} dans ta tête. Maintenant, ajoute {{{{b}}}} doigts. Qu'est-ce que tu trouves ?"
   3. RÉPONSE : "La bonne réponse est {{{{resultat}}}}."
→ JAMAIS de "Bravo" si c'est faux.

🎯 QUIZ :
→ 1-2 questions rapides pour valider la stratégie.

🏆 CONCLUSION :
"🏆 Félicitations ! Tu as terminé ta séance sur **{chapitre_nom}** ! 😊
Qu'est-ce que tu veux faire ?
  1️⃣ Autre exercice sur **{chapitre_nom}**
  2️⃣ Passer à un autre chapitre"
════════════════════════════════
RÈGLES DE CONTENU
════════════════════════════════

🔴 Résultats négatifs : Python gère ce cas automatiquement.
🔴 Décimaux selon le niveau :
→ 1ère/2ème/3ème : interdits → STOP + "👏 Tu découvriras les décimaux en 4ème année 📚 💪"
→ 4ème : lecture/écriture seulement → si opérations → STOP + "👏 Les opérations décimaux en 5ème 📚 💪"
→ 5ème : +/- seulement → si ×/÷ → STOP + "👏 ×/÷ décimaux en 6ème 📚 💪"
→ 6ème : tout autorisé ✅
🔴 Signe _ : n'est PAS une soustraction → "👋 Utilise - pour soustraire : 3 - 2 😊"
🔴 Opération incomplète (3+, 5-) : "😊 Il manque un nombre ! Écris par exemple : 3 + 4 💪"
🔴 Signe incompatible : {r6_msg} → STOP. ATTENDS Oui ou Non. | {r6_oui} | Non → {r6_non}

════════════════════════════════
LANGUE ET TON
════════════════════════════════
→ Réponds UNIQUEMENT en **{langue}**
→ Bascule FR/AR immédiatement si l'élève change de langue
→ Toujours bienveillant, encourageant, doux avec les enfants
→ Si message incompréhensible : "👋 Bonjour ! Tu veux commencer la leçon sur **{chapitre_nom}** ? Écris 'Oui' ! 😊"
→ Hors maths : {r7_hors} | Autre chapitre : {r7_chap} | Hors niveau : {r7_niv}
════════════════════════════════
EXEMPLES DE COMPORTEMENT ATTENDU
════════════════════════════════

1. ACCUEIL :
Élève : "je veux apprendre l'addition"
Tuteur : "👋 Bonjour ! 😊 L'addition c'est regrouper des objets. Si tu as 5 oranges 🍊 et j'en ajoute 3 🍊, tu en auras 8. Tu as compris ? On essaie ! ✏️ Combien font 4 + 2 ? 😊"

2. RÉPONSE INCORRECTE :
Élève : "7 + 5 ça fait 11"
Tuteur : "👏 C'est bien d'avoir essayé ! La bonne réponse est 12. Regarde : 7 + 3 = 10, puis 10 + 2 = 12 ! 😊💪 ✏️ On tente un autre ? Combien font 4 + 3 ?"

3. RÉSULTAT NÉGATIF :
Élève : "3 - 10"
Tuteur : "Belle curiosité ! Mais on ne peut pas retirer plus que ce qu'on possède. 😊 Au primaire, on met toujours le plus gros nombre devant. Tu verras le reste au collège ! 📚💪"

4. OPÉRATION INCOMPLÈTE :
Élève : "8 +"
Tuteur : "😊 Il manque un nombre ! Écris par exemple 8 + 4. Complète et on continue ! 💪"""

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
session_key = f"chat_{niveau_cle}_{chapitre_cle}"
etape_key   = f"etape_{niveau_cle}_{chapitre_cle}"
score_key   = f"score_{niveau_cle}_{chapitre_cle}"

if session_key not in st.session_state: st.session_state[session_key] = []
if etape_key   not in st.session_state: st.session_state[etape_key]   = "amorce"
if score_key   not in st.session_state: st.session_state[score_key]   = {"bonnes": 0, "total": 0}

chat_history   = st.session_state[session_key]
etape_actuelle = st.session_state[etape_key]
score          = st.session_state[score_key]

etape_label = ETAPES[langue_choisie].get(etape_actuelle, "")
if etape_label:
    st.markdown(f'<div class="etape-badge" dir="{direction}">{etape_label}</div>', unsafe_allow_html=True)

if score["total"] > 0:
    texte_score = t["score_text"].format(bonnes=score['bonnes'], total=score['total'])
    st.markdown(f'<div style="text-align:center;font-family:Fredoka One;color:#764ba2;margin-bottom:10px" dir="{direction}">{texte_score}</div>', unsafe_allow_html=True)

# ============================================================
# 13. MESSAGE DE BIENVENUE
# ============================================================
if len(chat_history) == 0:
    chat_history.append(AIMessage(content=""))

if len(chat_history) == 1 and isinstance(chat_history[0], AIMessage):
    if langue_choisie == "Français":
        msg = f"👋 Bonjour ! 🌟\n\nJe suis ton tuteur de mathématiques pour la **{niveau_nom_affiche}** !\n\n❓ Qu'est-ce que tu voudrais savoir sur la **{chapitre_nom_affiche}** aujourd'hui ?"
    else:
        msg = f"👋 مرحباً بك ! 🌟\n\nأنا معلم الرياضيات الخاص بك لـ **{niveau_nom_affiche}** !\n\n❓ ماذا تريد أن تتعلم في **{chapitre_nom_affiche}** اليوم ؟"
    chat_history[0] = AIMessage(content=msg)

# ============================================================
# 14. AFFICHAGE HISTORIQUE
# ============================================================
for msg in chat_history:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(f'<div dir="{direction}">{msg.content}</div>', unsafe_allow_html=True)

# ============================================================
# 15. BOUTONS D'ACTION
# ============================================================
col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    if st.button(t["btn_new"]):
        st.session_state[session_key] = []
        st.session_state[etape_key]   = "amorce"
        st.session_state[score_key]   = {"bonnes": 0, "total": 0}
        st.rerun()

with col_btn2:
    if st.button(t["btn_help"]):
        st.session_state[session_key].append(AIMessage(content=t["help_text"]))
        st.rerun()

with col_btn3:
    if st.button(t["btn_menu"]):
        for key in list(st.session_state.keys()):
            if key.startswith(("chat_", "etape_", "score_")):
                del st.session_state[key]
        st.rerun()

# ============================================================
# 16. CONVERSATION PRINCIPALE
# ============================================================
user_input = st.chat_input(t["chat_placeholder"])

if user_input:
    with st.chat_message("user"):
        st.markdown(f'<div dir="{direction}">{user_input}</div>', unsafe_allow_html=True)

    # ── Détection résultat négatif — Python AVANT GPT ──────
    if chapitre_cle == "Soustraction" and detecter_resultat_negatif(user_input):
        reply = message_negatif(langue_choisie)
        st.session_state[session_key].append(HumanMessage(content=user_input))
        st.session_state[session_key].append(AIMessage(content=reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div dir="{direction}">{reply}</div>', unsafe_allow_html=True)
        st.rerun()

    # ── Détection signe incompatible — Python AVANT GPT ────
    signe_incompatible = detecter_signe_incompatible(user_input, chapitre_cle, langue_choisie)
    if signe_incompatible:
        st.session_state[session_key].append(HumanMessage(content=user_input))
        st.session_state[session_key].append(AIMessage(content=signe_incompatible))
        with st.chat_message("assistant"):
            st.markdown(f'<div dir="{direction}">{signe_incompatible}</div>', unsafe_allow_html=True)
        st.rerun()

    # RAG
    context = ""
    if vectorstore:
        query   = f"{chapitre_nom_affiche} {niveau_nom_affiche} {user_input}"
        docs    = vectorstore.similarity_search(query, k=3)
        context = "\n\n".join([doc.page_content for doc in docs])

    # Prompt
    system_prompt = get_system_prompt(
        niveau_nom_affiche, chapitre_nom_affiche, langue_choisie, context
    )
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
                    "chat_history": chat_history[-20:]
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
                    st.session_state[score_key]["total"] += 1  # ✅ Comptage corrigé
                elif "🎯" in assistant_reply or "quiz" in reply_lower or "اختبار" in assistant_reply:
                    st.session_state[etape_key] = "quiz"
                    st.session_state[score_key]["total"] += 1  # ✅ Comptage corrigé
                elif "🏆" in assistant_reply or "félicitations" in reply_lower or "أحسنت" in assistant_reply:
                    st.session_state[etape_key] = "felicitations"
                    st.session_state[score_key]["bonnes"] += 1
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
