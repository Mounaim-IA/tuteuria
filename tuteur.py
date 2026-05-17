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
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# ============================================================
# SUPABASE — Base de données sessions
# ============================================================
try:
    from supabase import create_client, Client
    # Lire depuis st.secrets (Streamlit Cloud) ou .env (local)
    import os as _os
    _sb_url = st.secrets.get("SUPABASE_URL", "") or _os.getenv("SUPABASE_URL", "")
    _sb_key = st.secrets.get("SUPABASE_KEY", "") or _os.getenv("SUPABASE_KEY", "")
    supabase: Client = create_client(_sb_url, _sb_key) if _sb_url and _sb_key else None
except Exception:
    supabase = None

import os as _os2
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "") or _os2.getenv("ADMIN_PASSWORD", "admiN@26")

def db_creer_session(prenom, niveau, langue):
    """Crée une session dans Supabase et retourne son ID."""
    if not supabase: return None
    try:
        res = supabase.table("sessions").insert({
            "prenom":        prenom or "Anonyme",
            "niveau":        niveau,
            "langue":        langue,
            "bonnes":        0,
            "total":         0,
            "taux":          0,
            "nb_messages":   0,
            "etape_finale":  "amorce",
            "duree_minutes": 0,
        }).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        print(f"⚠️ Supabase db_creer_session : {e}")
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
    except Exception as e:
        print(f"⚠️ Supabase db_maj_session : {e}")

def db_charger_sessions():
    """Charge toutes les sessions pour le dashboard admin."""
    if not supabase: return []
    try:
        res = supabase.table("sessions").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"⚠️ Supabase db_charger_sessions : {e}")
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
        /* On utilise EXACTEMENT le dégradé du bouton exercice */
        background: linear-gradient(135deg, #4ECDC4, #45B7D1) !important; 
        
        /* On supprime la bordure rouge de l'image précédente */
        border: none !important; 
        
        border-radius: 20px !important; 
        padding: 30px !important;
        text-align: center !important;
        margin-bottom: 20px !important;
        box-shadow: 0 10px 25px rgba(78, 205, 196, 0.4) !important;
        display: block !important;
    }

    /* On force le texte en blanc pour qu'il soit lisible sur le turquoise */
    .header-subtitle {
        color: white !important;
        font-weight: 800 !important;
        opacity: 0.95 !important;
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
    /* Placeholder gris sans italic */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div {
        color: #9ca3af !important;
        font-style: normal !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] [class*="singleValue"] {
        color: #1a1a2e !important;
        font-style: normal !important;
        font-weight: 600 !important;
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
   /* ══ FORMULAIRE DÉMARRAGE ══ */
    .start-form {
        background: linear-gradient(135deg, #4ECDC4, #45B7D1);
        border-radius: 16px;
        padding: 14px 20px;
        margin-bottom: 14px;
        box-shadow: 0 4px 16px rgba(78,205,196,0.25);
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
        background: linear-gradient(135deg, #4ECDC422, #45B7D122);
        border: 1.5px solid #4ECDC4;
        border-radius: 12px;
        padding: 8px 18px;
        margin-bottom: 14px;
        font-family: 'Fredoka One', cursive;
        font-size: 1rem;
        color: #0F6E56;
        display: inline-block;
        text-align: center;
    }
    .eleve-info-wrap {
        text-align: center;
        margin-bottom: 14px;
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
        .stButton > button {
            padding: 8px 10px !important;
            font-size: 0.85em !important;
        }
    }



    .stChatInput textarea {
        border: 3px solid #4ECDC4 !important;
        border-radius: 20px !important;
        background: white !important;
        font-family: 'Nunito', sans-serif !important;
        font-size: 1em !important;
        min-height: 80px !important;
        max-height: 80px !important;
        height: 80px !important;
        resize: none !important;
        padding-top: 10px !important;
        overflow-y: auto !important;
    }
    /* Remplacer la flèche par "Envoyer" */
    [data-testid="stChatInputSubmitButton"] {
        background: linear-gradient(135deg, #FF6B6B, #FFE66D) !important;
        border-radius: 12px !important;
        width: auto !important;
        padding: 6px 14px !important;
        min-width: 80px !important;
    }
    [data-testid="stChatInputSubmitButton"] svg {
        display: none !important;
    }
    [data-testid="stChatInputSubmitButton"]::after {
        content: "Envoyer" !important;
        font-family: 'Fredoka One', cursive !important;
        font-size: 0.9rem !important;
        color: #333 !important;
        font-weight: 500 !important;
    }

    /* ── Scroll vers le bas ── */
    [data-testid="stChatMessageContainer"] {
        overflow-y: auto !important;
        min-height: 650px !important;
        max-height: 850px !important;
        height: 650px !important;
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
# ── Sélecteur langue — 2 boutons pill centrés ────────────────
if "langue_choisie" not in st.session_state:
    st.session_state["langue_choisie"] = "Français"

# Caché si session active
_lang_visible = not st.session_state.get("chat_actif", False)
_lc = st.session_state["langue_choisie"]

if _lang_visible:
    _c1, _c2, _c3, _c4, _c5 = st.columns([2, 1, 0.2, 1, 2])
    with _c2:
        if st.button("🇫🇷 Français", key="btn_lang_fr",
                     use_container_width=True):
            st.session_state["langue_choisie"] = "Français"
            st.rerun()
    with _c3:
        st.markdown(
            "<div style='text-align:center;color:#888;"
            "font-size:1.1rem;padding-top:8px;'>|</div>",
            unsafe_allow_html=True)
    with _c4:
        if st.button("العربية 🇲🇦", key="btn_lang_ar",
                     use_container_width=True):
            st.session_state["langue_choisie"] = "العربية"
            st.rerun()

    # JS : pilule jaune actif / blanc inactif + centrage
    _fr_active = "true" if _lc == "Français" else "false"
    _ar_active = "true" if _lc == "العربية"  else "false"
    st.components.v1.html(f"""
<script>
(function() {{
    function injectStyle() {{
        const doc = window.parent.document;
        doc.querySelectorAll('button').forEach(btn => {{
            const txt = (btn.innerText || btn.textContent || '').trim();
            const isFr = txt.includes('Fran');
            const isAr = txt.includes('\u0627\u0644\u0639\u0631\u0628\u064a\u0629');
            if (!isFr && !isAr) return;
            const active = (isFr && {_fr_active}) || (isAr && {_ar_active});
            const color = active ? '#333' : '#999';
            btn.setAttribute('style',
                'background:' + (active ? '#FFD93D' : 'white') + ' !important;' +
                'color:' + color + ' !important;' +
                'border:2px solid #FFD93D !important;' +
                'border-radius:50px !important;' +
                'font-family:Fredoka One,cursive !important;' +
                'font-size:0.95rem !important;' +
                'box-shadow:none !important;' +
                'background-image:none !important;' +
                'display:flex !important;' +
                'align-items:center !important;' +
                'justify-content:center !important;' +
                'text-align:center !important;' +
                'padding:8px 12px !important;' +
                'white-space:nowrap !important;' +
                'width:100% !important;'
            );
            // Centrer aussi le p interne
            btn.querySelectorAll('p, span, div').forEach(el => {{
                el.style.cssText = 'margin:0 !important;padding:0 !important;' +
                    'text-align:center !important;' +
                    'width:100% !important;' +
                    'color:' + color + ' !important;';
            }});
        }});
    }}
    // ── Selectbox niveau : italic off + gris→foncé + sans X ──
    function styleNiveau() {{
        const doc = window.parent.document;
        doc.querySelectorAll('[data-baseweb="select"]').forEach(sel => {{
            const val = sel.querySelector('[class*="singleValue"],[class*="placeholder"]');
            if (!val) return;
            const txt = (val.innerText || val.textContent || '').trim();
            const isEmpty = !txt || txt.includes('Choisis') || txt.includes('\u0627\u062e\u062a\u0631');
            val.style.fontStyle  = 'normal';
            val.style.color      = isEmpty ? '#9ca3af' : '#1a1a2e';
            val.style.fontWeight = isEmpty ? 'normal'  : '600';
            // Masquer bouton X
            sel.querySelectorAll('[aria-label*="lear"],[title*="lear"]').forEach(x => {{
                x.style.display = 'none';
            }});
        }});
    }}
    setTimeout(styleNiveau, 80);
    setTimeout(styleNiveau, 400);
    setTimeout(styleNiveau, 1000);

    setTimeout(injectStyle, 80);
    setTimeout(injectStyle, 400);
    setTimeout(injectStyle, 1000);
    new MutationObserver(function(m) {{
        injectStyle();
        styleNiveau();
    }}).observe(
        window.parent.document.body, {{childList:true, subtree:true}}
    );
}})();
</script>
""", height=0)
langue_choisie = st.session_state["langue_choisie"]
t         = UI[langue_choisie]
direction = "rtl" if langue_choisie == "العربية" else "ltr"

# ── JS global — selectbox niveau ─────────────────────────────
st.components.v1.html("""
<script>
(function(){
    function styleNiveau(){
        var doc = window.parent.document;
        doc.querySelectorAll('[data-baseweb="select"]').forEach(function(sel){
            var val = sel.querySelector('[class*="singleValue"]') ||
                      sel.querySelector('[class*="placeholder"]');
            if (!val) return;
            var txt = (val.innerText || val.textContent || '').trim();
            var isEmpty = !txt ||
                          txt.indexOf('Choisis') >= 0 ||
                          txt.indexOf('\u0627\u062e\u062a\u0631') >= 0;
            val.style.fontStyle  = 'normal';
            val.style.color      = isEmpty ? '#9ca3af' : '#1a1a2e';
            val.style.fontWeight = isEmpty ? '400' : '600';
            // Masquer le X
            sel.querySelectorAll('[aria-label],[title]').forEach(function(el){
                var lb = (el.getAttribute('aria-label')||'') +
                         (el.getAttribute('title')||'');
                if(lb.toLowerCase().indexOf('clear') >= 0){
                    el.style.display = 'none';
                }
            });
        });
    }
    styleNiveau();
    setTimeout(styleNiveau, 300);
    setTimeout(styleNiveau, 800);
    setTimeout(styleNiveau, 2000);
    new MutationObserver(styleNiveau).observe(
        window.parent.document.body,
        {childList: true, subtree: true}
    );
})();
</script>
""", height=0)

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
    """
    ChromaDB optionnel — silencieux si indisponible.
    Sur Streamlit Cloud sans chroma_db → None, GPT répond sans RAG.
    """
    if not os.path.exists(CHROMA_DIR):
        return None
    try:
        from langchain_community.vectorstores import Chroma
        embeddings = OpenAIEmbeddings(api_key=api_key)
        vs = Chroma(persist_directory=CHROMA_DIR,
                    embedding_function=embeddings)
        _ = len(vs)  # Test connexion
        return vs
    except Exception:
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
    Prend le DERNIER calcul dans le dernier message assistant (après ✏️ ou 🎯).
    Gère le cas où un message de correction contient plusieurs calculs
    (ex: correction de 16-7 puis nouvelle question 12-4).
    """
    for msg in reversed(historique):
        if isinstance(msg, AIMessage):
            texte = msg.content

            # Trouver la position du DERNIER emoji exercice
            pos = -1
            if "🎯" in texte:
                pos = texte.rindex("🎯")
            elif "✏️" in texte:
                pos = texte.rindex("✏️")

            if pos >= 0:
                texte_exercice = texte[pos:]
                # Trouver TOUS les calculs après le dernier emoji
                # et prendre le DERNIER (cas où correction + nouvelle question)
                matches = list(re.finditer(
                    r'(\d+(?:[,\.]\d+)?(?:\s*[+\-×*x÷/]\s*\d+(?:[,\.]\d+)?)+)',
                    texte_exercice
                ))
                if matches:
                    # Prendre le DERNIER match (le plus proche de la fin)
                    expression_brute = matches[-1].group(1).strip()
                    calcul_python = (expression_brute
                                     .replace('×', '*').replace('x', '*')
                                     .replace('÷', '/').replace(',', '.')
                                     .replace(' ', ''))
                    try:
                        resultat = eval(calcul_python)
                        if isinstance(resultat, float) and resultat == int(resultat):
                            resultat = int(resultat)
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
    """Supprime LaTeX, noms d'étapes et TOUT le markdown interdit (D9)."""
    # ── Étiquettes pédagogiques internes ──
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

    # ── LaTeX ──
    reply = re.sub(r'\\\((.+?)\\\)', r'\1', reply)
    reply = re.sub(r'\\\[(.+?)\\\]', r'\1', reply)

    # ── Blocs de code (``` ... ``` ou ` ... `) ──
    # Blocs multi-lignes : remplacer par le contenu sans backticks
    reply = re.sub(r'```[a-zA-Z]*\n(.*?)\n```', r'\1', reply, flags=re.DOTALL)
    reply = re.sub(r'```(.*?)```', r'\1', reply, flags=re.DOTALL)
    # Code inline
    reply = re.sub(r'`([^`]+)`', r'\1', reply)

    # ── Titres markdown (# ## ###) ──
    reply = re.sub(r'^#{1,6}\s+', '', reply, flags=re.MULTILINE)

    # ── Listes numérotées (1. 2. 3.) → retirer le numéro et le point ──
    reply = re.sub(r'^\s*\d+\.\s+', '', reply, flags=re.MULTILINE)

    # ── Listes à puces (* - •) en début de ligne ──
    reply = re.sub(r'^\s*[\*\-•]\s+', '', reply, flags=re.MULTILINE)
    # ── Astérisques isolés utilisés comme séparateurs dans le texte ──
    # Ex: "27 * 35" ou "+ * 35" → remplacer par espace
    reply = re.sub(r'\s\*\s', ' ', reply)
    # Astérisque en début de mot sans markdown (ex: "*35" seul)
    reply = re.sub(r'(?<!\*)\*(?!\*)', ' ', reply)

    # ── Gras / Italique ──
    reply = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', reply)   # bold+italic
    reply = re.sub(r'\*\*(.+?)\*\*', r'\1', reply)         # bold
    reply = re.sub(r'\*([^\s*][^*]*)\*', r'\1', reply)     # italic (évite * isolé)
    reply = re.sub(r'__(.+?)__', r'\1', reply)
    reply = re.sub(r'_([^_]+)_', r'\1', reply)

    # ── Liens markdown [texte](url) → texte ──
    reply = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', reply)

    # ── Caractères superscripts utilisés comme notation (²4, ¹7, ⁷) ──
    # Remplacer par des espaces pour éviter la confusion
    superscripts = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789')
    reply = reply.translate(superscripts)

    # ── Lignes horizontales (--- ou ===) ──
    reply = re.sub(r'^\s*[-=]{3,}\s*$', '', reply, flags=re.MULTILINE)

    # ── Nettoyer les lignes vides multiples → max 1 ligne vide ──
    reply = re.sub(r'\n{3,}', '\n\n', reply)

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
            f"En primaire, on retire toujours un petit nombre d'un plus grand. Les nombres négatifs, c'est une autre aventure ! 🚀\n\n"
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
# 9ter. IMAGES PÉDAGOGIQUES — Approche hybride d'étayage
# ============================================================
# Chemins absolus pour fonctionner sur Streamlit Cloud
_IMG_FR = os.path.join(ABS_PATH, "images", "fr")
_IMG_AR = os.path.join(ABS_PATH, "images", "ar")

def _fr(f): return os.path.join(_IMG_FR, f)
def _ar(f): return os.path.join(_IMG_AR, f)

IMAGES_MAP = {
    "Français": {
        # Addition
        "addition_simple":       _fr("26_addition_simple_visuelle.png"),
        "addition_sans_retenue": _fr("01_addition_sans_retenue.png"),
        "addition_avec_retenue": _fr("02_addition_avec_retenue.png"),
        "addition_3_chiffres":   _fr("11_addition_3_chiffres.png"),
        "addition_decimaux":     _fr("21_addition_decimaux.png"),
        # Soustraction
        "soustraction_simple":           _fr("27_soustraction_simple_visuelle.png"),
        "soustraction_sans_retenue":     _fr("03_soustraction_sans_retenue.png"),
        "soustraction_2ch_1ch_emprunt":  _fr("04b_soustraction_2ch_1ch_emprunt.png"),
        "soustraction_avec_retenue":     _fr("04_soustraction_avec_retenue.png"),
        "soustraction_3ch_1ch_emprunt":  _fr("04d_soustraction_3ch_1ch_emprunt.png"),
        "soustraction_3ch_2ch_emprunt":  _fr("04c_soustraction_3ch_2ch_emprunt.png"),
        "soustraction_3_chiffres":       _fr("12_soustraction_3_chiffres.png"),
        "soustraction_double_emprunt":   _fr("38_soustraction_double_emprunt.png"),
        "soustraction_decimaux":         _fr("22_soustraction_decimaux.png"),
        # Multiplication
        "multiplication_simple":       _fr("05_multiplication_simple.png"),
        "multiplication_2_chiffres":   _fr("06_multiplication_deux_chiffres.png"),
        "multiplication_3_chiffres":   _fr("29_multiplication_3_chiffres.png"),
        "multiplication_10_100_1000":  _fr("13_multiplication_10_100_1000.png"),
        "multiplication_decimaux":     _fr("23_multiplication_decimaux.png"),
        "tables_multiplication":       _fr("39_tables_multiplication.png"),
        # Division
        "division_simple":           _fr("07_division_simple.png"),
        "division_avec_reste":       _fr("08_division_avec_reste.png"),
        "division_2_chiffres":       _fr("14_division_2_chiffres.png"),
        "division_decimale":         _fr("24_division_decimale.png"),
        "division_diviseur_decimal": _fr("36_division_diviseur_decimal.png"),
        # Fractions
        "fractions_introduction":    _fr("15_fractions_introduction.png"),
        "fractions_equivalentes":    _fr("16_fractions_equivalentes.png"),
        "simplification_fractions":  _fr("35_simplification_fractions.png"),
        "addition_fractions":        _fr("17_addition_fractions.png"),
        "soustraction_fractions":    _fr("18_soustraction_fractions.png"),
        "comparaison_fractions":     _fr("19_comparaison_fractions.png"),
        "multiplication_fractions":  _fr("33_multiplication_fractions.png"),
        "division_fractions":        _fr("34_division_fractions.png"),
        "fractions_denom_diff":      _fr("32_addition_fractions_denom_diff.png"),
        "fraction_d_un_nombre":      _fr("31_fraction_d_un_nombre.png"),
        "fractions_decimales":       _fr("37_fractions_decimales.png"),
        # Concepts
        "numeration":           _fr("10_numeration.png"),
        "double_moitie":        _fr("28_double_et_moitie.png"),
        "priorite_operations":  _fr("20_priorite_operations.png"),
        "operations_mixtes":    _fr("25_operations_mixtes.png"),
        "multiples_diviseurs":  _fr("30_multiples_diviseurs.png"),
    },
    "العربية": {
        # Addition
        "addition_simple":       _ar("26_ar_addition_simple_visuelle.png"),
        "addition_sans_retenue": _ar("01_ar_addition_sans_retenue.png"),
        "addition_avec_retenue": _ar("02_ar_addition_avec_retenue.png"),
        "addition_3_chiffres":   _ar("11_ar_addition_3_chiffres.png"),
        "addition_decimaux":     _ar("21_ar_addition_decimaux.png"),
        # Soustraction
        "soustraction_simple":           _ar("27_ar_soustraction_simple_visuelle.png"),
        "soustraction_sans_retenue":     _ar("03_ar_soustraction_sans_retenue.png"),
        "soustraction_2ch_1ch_emprunt":  _ar("04b_ar_soustraction_2ch_1ch_emprunt.png"),
        "soustraction_avec_retenue":     _ar("04_ar_soustraction_avec_retenue.png"),
        "soustraction_3ch_1ch_emprunt":  _ar("04d_ar_soustraction_3ch_1ch_emprunt.png"),
        "soustraction_3ch_2ch_emprunt":  _ar("04c_ar_soustraction_3ch_2ch_emprunt.png"),
        "soustraction_3_chiffres":       _ar("12_ar_soustraction_3_chiffres.png"),
        "soustraction_double_emprunt":   _ar("38_ar_soustraction_double_emprunt.png"),
        "soustraction_decimaux":         _ar("22_ar_soustraction_decimaux.png"),
        # Multiplication
        "multiplication_simple":       _ar("05_ar_multiplication_simple.png"),
        "multiplication_2_chiffres":   _ar("06_ar_multiplication_deux_chiffres.png"),
        "multiplication_3_chiffres":   _ar("29_ar_multiplication_3_chiffres.png"),
        "multiplication_10_100_1000":  _ar("13_ar_multiplication_10_100_1000.png"),
        "multiplication_decimaux":     _ar("23_ar_multiplication_decimaux.png"),
        "tables_multiplication":       _ar("39_ar_tables_multiplication.png"),
        # Division
        "division_simple":           _ar("07_ar_division_simple.png"),
        "division_avec_reste":       _ar("08_ar_division_avec_reste.png"),
        "division_2_chiffres":       _ar("14_ar_division_2_chiffres.png"),
        "division_decimale":         _ar("24_ar_division_decimale.png"),
        "division_diviseur_decimal": _ar("36_ar_division_diviseur_decimal.png"),
        # Concepts
        "numeration":           _ar("10_ar_numeration.png"),
        "double_moitie":        _ar("28_ar_double_et_moitie.png"),
        "priorite_operations":  _ar("20_ar_priorite_operations.png"),
        "operations_mixtes":    _ar("25_ar_operations_mixtes.png"),
        "multiples_diviseurs":  _ar("30_ar_multiples_diviseurs.png"),
    }
}
# Fallback : si image AR manquante → utiliser l'image FR
for k, v in IMAGES_MAP["Français"].items():
    if k not in IMAGES_MAP["العربية"]:
        IMAGES_MAP["العربية"][k] = v


# ============================================================
# MENU DE CHOIX PAR OPÉRATION ET NIVEAU
# ============================================================
# Quand l'élève dit "l'addition", le tuteur propose un menu
# filtré par niveau. L'élève tape le numéro → image + exercice cohérents.

CHOIX_OPERATIONS = {
    "addition": {
        1: [
            {"label_fr": "Addition simple (5 + 3)", "label_ar": "جمع بسيط (5 + 3)", "image": "addition_simple",
             "consigne": "addition simple à 1 chiffre, nombres inférieurs à 10"},
        ],
        2: [
            {"label_fr": "Addition sans retenue (23 + 14)", "label_ar": "جمع بدون احتفاظ (23 + 14)", "image": "addition_sans_retenue",
             "consigne": "addition à 2 chiffres SANS retenue"},
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue"},
        ],
        3: [
            {"label_fr": "Addition sans retenue (23 + 14)", "label_ar": "جمع بدون احتفاظ (23 + 14)", "image": "addition_sans_retenue",
             "consigne": "addition à 2 chiffres SANS retenue"},
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue"},
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues, nombres entre 100 et 999"},
        ],
        4: [
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue"},
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues"},
            {"label_fr": "Addition de décimaux (12,5 + 3,45)", "label_ar": "جمع الأعداد العشرية (12,5 + 3,45)", "image": "addition_decimaux",
             "consigne": "addition de nombres décimaux, aligner les virgules"},
        ],
        5: [
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues"},
            {"label_fr": "Addition de décimaux (12,5 + 3,45)", "label_ar": "جمع الأعداد العشرية (12,5 + 3,45)", "image": "addition_decimaux",
             "consigne": "addition de nombres décimaux"},
            {"label_fr": "Addition de fractions (1/4 + 2/4)", "label_ar": "جمع الكسور (1/4 + 2/4)", "image": "addition_fractions",
             "consigne": "addition de fractions avec MÊME dénominateur"},
        ],
        6: [
            {"label_fr": "Addition de décimaux (12,5 + 3,45)", "label_ar": "جمع الأعداد العشرية (12,5 + 3,45)", "image": "addition_decimaux",
             "consigne": "addition de nombres décimaux"},
            {"label_fr": "Addition de fractions (1/4 + 2/4)", "label_ar": "جمع الكسور (1/4 + 2/4)", "image": "addition_fractions",
             "consigne": "addition de fractions même dénominateur"},
            {"label_fr": "Fractions dénominateurs différents (1/2 + 1/3)", "label_ar": "كسور بمقامات مختلفة (1/2 + 1/3)", "image": "fractions_denom_diff",
             "consigne": "addition de fractions avec dénominateurs DIFFÉRENTS, trouver le PPCM"},
        ],
    },
    "soustraction": {
        1: [
            {"label_fr": "Soustraction simple (7 - 3)", "label_ar": "طرح بسيط (7 - 3)", "image": "soustraction_simple",
             "consigne": "soustraction simple à 1 chiffre, nombres inférieurs à 10"},
        ],
        2: [
            {"label_fr": "Soustraction sans emprunt (48 - 23)", "label_ar": "طرح بدون استلاف (48 - 23)", "image": "soustraction_sans_retenue",
             "consigne": "soustraction à 2 chiffres SANS emprunt"},
            {"label_fr": "Soustraction avec emprunt (43 - 17)", "label_ar": "طرح مع الاستلاف (43 - 17)", "image": "soustraction_avec_retenue",
             "consigne": "soustraction à 2 chiffres AVEC emprunt"},
        ],
        3: [
            {"label_fr": "Soustraction avec emprunt (43 - 17)", "label_ar": "طرح مع الاستلاف (43 - 17)", "image": "soustraction_avec_retenue",
             "consigne": "soustraction à 2 chiffres avec emprunt"},
            {"label_fr": "Soustraction à 3 chiffres (834 - 567)", "label_ar": "طرح بثلاثة أرقام (834 - 567)", "image": "soustraction_double_emprunt",
             "consigne": "soustraction à 3 chiffres avec double emprunt, nombres entre 100 et 999"},
        ],
        4: [
            {"label_fr": "Soustraction à 3 chiffres (503 - 247)", "label_ar": "طرح بثلاثة أرقام (503 - 247)", "image": "soustraction_3_chiffres",
             "consigne": "soustraction à 3 chiffres avec emprunts"},
            {"label_fr": "Soustraction de décimaux (15,3 - 8,7)", "label_ar": "طرح الأعداد العشرية (15,3 - 8,7)", "image": "soustraction_decimaux",
             "consigne": "soustraction de nombres décimaux"},
        ],
        5: [
            {"label_fr": "Soustraction de décimaux (15,3 - 8,7)", "label_ar": "طرح الأعداد العشرية (15,3 - 8,7)", "image": "soustraction_decimaux",
             "consigne": "soustraction de nombres décimaux"},
            {"label_fr": "Soustraction de fractions (5/7 - 2/7)", "label_ar": "طرح الكسور (5/7 - 2/7)", "image": "soustraction_fractions",
             "consigne": "soustraction de fractions même dénominateur"},
        ],
        6: [
            {"label_fr": "Soustraction de décimaux (15,3 - 8,7)", "label_ar": "طرح الأعداد العشرية (15,3 - 8,7)", "image": "soustraction_decimaux",
             "consigne": "soustraction de nombres décimaux"},
            {"label_fr": "Soustraction de fractions (5/7 - 2/7)", "label_ar": "طرح الكسور (5/7 - 2/7)", "image": "soustraction_fractions",
             "consigne": "soustraction de fractions même dénominateur"},
        ],
    },
    "multiplication": {
        2: [
            {"label_fr": "Les 9 tables de multiplication (1 à 9)", "label_ar": "جداول الضرب التسعة (1 إلى 9)", "image": "tables_multiplication",
             "consigne": "tables de multiplication de 1 à 9, produit simple entre 1×1 et 9×10"},
            {"label_fr": "Multiplication simple (3 × 4)", "label_ar": "الضرب البسيط (3 × 4)", "image": "addition_simple",
             "consigne": "multiplication simple 1 chiffre × 1 chiffre, résultat ≤ 50"},
        ],
        3: [
            {"label_fr": "Les 9 tables de multiplication", "label_ar": "جداول الضرب التسعة", "image": "tables_multiplication",
             "consigne": "tables de multiplication de 1 à 9"},
            {"label_fr": "Multiplication par un chiffre (34 × 6)", "label_ar": "الضرب بعدد واحد (34 × 6)", "image": "multiplication_simple",
             "consigne": "multiplication 2 chiffres × 1 chiffre avec retenue"},
            {"label_fr": "Multiplier par 10, 100, 1000", "label_ar": "الضرب في 10, 100, 1000", "image": "multiplication_10_100_1000",
             "consigne": "multiplication par 10, 100 ou 1000"},
        ],
        4: [
            {"label_fr": "Multiplication par un chiffre (34 × 6)", "label_ar": "الضرب بعدد واحد (34 × 6)", "image": "multiplication_simple",
             "consigne": "multiplication 2 chiffres × 1 chiffre"},
            {"label_fr": "Multiplication à 2 chiffres (24 × 13)", "label_ar": "الضرب بعددين (24 × 13)", "image": "multiplication_2_chiffres",
             "consigne": "multiplication 2 chiffres × 2 chiffres, deux lignes + addition"},
        ],
        5: [
            {"label_fr": "Multiplication à 2 chiffres (24 × 13)", "label_ar": "الضرب بعددين (24 × 13)", "image": "multiplication_2_chiffres",
             "consigne": "multiplication 2 chiffres × 2 chiffres"},
            {"label_fr": "Multiplication de décimaux (2,5 × 3)", "label_ar": "ضرب الأعداد العشرية (2,5 × 3)", "image": "multiplication_decimaux",
             "consigne": "multiplication de nombres décimaux"},
            {"label_fr": "Multiplication de fractions (2/3 × 3/4)", "label_ar": "ضرب الكسور (2/3 × 3/4)", "image": "multiplication_fractions",
             "consigne": "multiplication de fractions"},
        ],
        6: [
            {"label_fr": "Multiplication de décimaux (2,5 × 3)", "label_ar": "ضرب الأعداد العشرية (2,5 × 3)", "image": "multiplication_decimaux",
             "consigne": "multiplication de nombres décimaux"},
            {"label_fr": "Multiplication de fractions (2/3 × 3/4)", "label_ar": "ضرب الكسور (2/3 × 3/4)", "image": "multiplication_fractions",
             "consigne": "multiplication de fractions"},
            {"label_fr": "Priorité des opérations (2 + 3 × 4)", "label_ar": "أولوية العمليات (2 + 3 × 4)", "image": "priorite_operations",
             "consigne": "priorité des opérations, × et ÷ avant + et -"},
        ],
    },
    "division": {
        3: [
            {"label_fr": "Division simple (84 ÷ 4)", "label_ar": "قسمة بسيطة (84 ÷ 4)", "image": "division_simple",
             "consigne": "division posée, diviseur 1 chiffre, reste = 0"},
            {"label_fr": "Division avec reste (47 ÷ 5)", "label_ar": "قسمة مع الباقي (47 ÷ 5)", "image": "division_avec_reste",
             "consigne": "division posée avec reste, diviseur 1 chiffre"},
        ],
        4: [
            {"label_fr": "Division avec reste (47 ÷ 5)", "label_ar": "قسمة مع الباقي (47 ÷ 5)", "image": "division_avec_reste",
             "consigne": "division avec reste"},
            {"label_fr": "Division par 2 chiffres (156 ÷ 12)", "label_ar": "قسمة بعددين (156 ÷ 12)", "image": "division_2_chiffres",
             "consigne": "division posée, diviseur à 2 chiffres"},
        ],
        5: [
            {"label_fr": "Division par 2 chiffres (156 ÷ 12)", "label_ar": "قسمة بعددين (156 ÷ 12)", "image": "division_2_chiffres",
             "consigne": "division diviseur 2 chiffres"},
            {"label_fr": "Division décimale (17 ÷ 4 = 4,25)", "label_ar": "القسمة العشرية (17 ÷ 4 = 4,25)", "image": "division_decimale",
             "consigne": "division avec quotient décimal"},
        ],
        6: [
            {"label_fr": "Division décimale (17 ÷ 4 = 4,25)", "label_ar": "القسمة العشرية (17 ÷ 4 = 4,25)", "image": "division_decimale",
             "consigne": "division décimale"},
            {"label_fr": "Diviseur décimal (8,4 ÷ 1,2)", "label_ar": "المقسوم عليه عشري (8,4 ÷ 1,2)", "image": "division_diviseur_decimal",
             "consigne": "division avec diviseur décimal, multiplier les deux par 10"},
            {"label_fr": "Division de fractions (1/2 ÷ 1/4)", "label_ar": "قسمة الكسور (1/2 ÷ 1/4)", "image": "division_fractions",
             "consigne": "division de fractions, inverser et multiplier"},
        ],
    },
    "fractions": {
        3: [
            {"label_fr": "Découverte des fractions (1/2, 1/4, 3/4)", "label_ar": "اكتشاف الكسور (1/2, 1/4, 3/4)", "image": "fractions_introduction",
             "consigne": "lecture de fractions, numérateur et dénominateur"},
        ],
        4: [
            {"label_fr": "Découverte des fractions", "label_ar": "اكتشاف الكسور", "image": "fractions_introduction",
             "consigne": "lecture de fractions"},
            {"label_fr": "Fractions équivalentes (1/2 = 2/4)", "label_ar": "الكسور المتكافئة (1/2 = 2/4)", "image": "fractions_equivalentes",
             "consigne": "fractions équivalentes, multiplier haut et bas par le même nombre"},
            {"label_fr": "Simplifier une fraction (6/8 = 3/4)", "label_ar": "تبسيط كسر (6/8 = 3/4)", "image": "simplification_fractions",
             "consigne": "simplification de fractions avec le PGCD"},
            {"label_fr": "Comparer des fractions", "label_ar": "مقارنة الكسور", "image": "comparaison_fractions",
             "consigne": "comparaison de fractions"},
        ],
        5: [
            {"label_fr": "Fractions équivalentes (1/2 = 2/4)", "label_ar": "الكسور المتكافئة (1/2 = 2/4)", "image": "fractions_equivalentes",
             "consigne": "fractions équivalentes"},
            {"label_fr": "Addition de fractions (1/5 + 2/5)", "label_ar": "جمع الكسور (1/5 + 2/5)", "image": "addition_fractions",
             "consigne": "addition de fractions même dénominateur"},
            {"label_fr": "Soustraction de fractions (5/7 - 2/7)", "label_ar": "طرح الكسور (5/7 - 2/7)", "image": "soustraction_fractions",
             "consigne": "soustraction de fractions même dénominateur"},
            {"label_fr": "Fractions décimales (1/4 = 0,25)", "label_ar": "الكسور العشرية (1/4 = 0,25)", "image": "fractions_decimales",
             "consigne": "conversion fraction ↔ décimal"},
        ],
        6: [
            {"label_fr": "Addition fractions dénominateurs différents (1/2 + 1/3)", "label_ar": "جمع كسور بمقامات مختلفة (1/2 + 1/3)", "image": "fractions_denom_diff",
             "consigne": "addition fractions dénominateurs différents, PPCM"},
            {"label_fr": "Multiplication de fractions (2/3 × 3/4)", "label_ar": "ضرب الكسور (2/3 × 3/4)", "image": "multiplication_fractions",
             "consigne": "multiplication de fractions"},
            {"label_fr": "Division de fractions (1/2 ÷ 1/4)", "label_ar": "قسمة الكسور (1/2 ÷ 1/4)", "image": "division_fractions",
             "consigne": "division de fractions, inverser et multiplier"},
            {"label_fr": "Fraction d'un nombre (1/4 de 20)", "label_ar": "كسر من عدد (1/4 من 20)", "image": "fraction_d_un_nombre",
             "consigne": "prendre une fraction d'un nombre entier"},
        ],
    },
}


def detecter_operation_demandee(message):
    """
    Détecte quelle opération l'élève demande via GPT (few-shot).
    GPT comprend le langage naturel, les fautes, les synonymes, l'arabe.
    Fallback rapide par mots-clés si GPT échoue.
    """
    msg = (message or "").strip()
    if not msg or len(msg) < 3:
        return None

    # ── Appel GPT classifier avec exemples (few-shot) ──
    try:
        classification_prompt = (
            "Tu dois identifier l'opération mathématique dans le message d'un élève de primaire.\n\n"
            "Exemples :\n"
            '"partager 45 bonbons entre 7 enfants" → division\n'
            '"59 cahiers pour 8 professeurs équitablement" → division\n'
            '"répartir 30 stylos entre 5 élèves" → division\n'
            '"3 groupes de 4 pommes, combien en tout" → multiplication\n'
            '"chaque élève a 6 livres et il y a 9 élèves" → multiplication\n'
            '"j ai 15 billes, j en perds 7, combien il reste" → soustraction\n'
            '"on avait 23 filles et 7 sont parties" → soustraction\n'
            '"j ai 5 billes, j en gagne 8, combien en tout" → addition\n'
            '"mettre 12 pommes avec 8 autres" → addition\n'
            '"c est quoi une fraction" → fractions\n'
            '"la géographie du maroc" → autre\n'
            '"le foot c est cool" → autre\n\n'
            f'Message de l\'élève : "{msg}"\n\n'
            "Réponds avec UN seul mot parmi : "
            "addition, soustraction, multiplication, division, fractions, autre"
        )
        result = llm_classifier.invoke([HumanMessage(content=classification_prompt)])
        op = result.content.strip().lower().split()[0].rstrip('.,!?')
        if op in ["addition", "soustraction", "multiplication", "division", "fractions"]:
            return op
        if op == "autre":
            return None
    except Exception:
        pass

    # ── Fallback mots-clés (si GPT indisponible) ──
    m = msg.lower()
    if any(x in m for x in ["addition","ajouter","additionner","الجمع"]):
        return "addition"
    if any(x in m for x in ["soustraction","soustraire","enlever","الطرح"]):
        return "soustraction"
    if any(x in m for x in ["multiplication","multiplie","fois","table","الضرب"]):
        return "multiplication"
    if any(x in m for x in ["division","divise","diviser","partage","partitionner",
                              "répartir","distribuer","entre","القسمة"]):
        return "division"
    if any(x in m for x in ["fraction","moitié","quart","كسر"]):
        return "fractions"
    return None


def detecter_calcul_direct(message):
    """
    Détecte si l'élève a écrit un calcul direct.
    Règle pour "/" :
      - numérateur < dénominateur (ex: 1/2, 3/4) → fraction → retourne None (pas traité comme calcul)
      - numérateur ≥ dénominateur (ex: 13/8, 15/3) → division → traité comme ÷
    """
    m = (message or "").strip()
    m_norm = m.replace('×','*').replace('÷','/').replace('−','-')

    match = re.fullmatch(
        r'(\d+(?:[,\.]\d+)?)\s*([+\-×*x÷/])\s*(\d+(?:[,\.]\d+)?)', m
    )
    if not match:
        match = re.fullmatch(
            r'(\d+(?:[,\.]\d+)?)\s*([+\-*/])\s*(\d+(?:[,\.]\d+)?)', m_norm
        )
    if not match:
        return None

    a   = match.group(1).replace(',', '.')
    op  = match.group(2)
    b   = match.group(3).replace(',', '.')

    # Règle fraction vs division pour "/"
    if op == '/':
        try:
            fa, fb = float(a), float(b)
            if fa < fb:
                # numérateur < dénominateur → c'est une fraction → ne pas traiter
                return None
        except Exception:
            pass

    # Normaliser l'affichage et l'opérateur
    expr_display = m.replace('/', ' ÷ ').replace('*', ' × ')
    op_norm = '÷' if op == '/' else ('×' if op in ['*','x'] else op)

    return (expr_display.strip(), float(a), op_norm, float(b))


def extraire_calcul_dans_phrase(message):
    """
    Détecte si le message est une demande d'explication pour un calcul embarqué.
    LLM gère toutes les formulations : "montre moi", "fais moi", "résoudre moi",
    "je comprends pas", "aide moi à faire 24-17", etc.
    """
    # Étape 1 : vérifier qu'il y a un calcul dans le message
    match = re.search(
        r'(\d+(?:[,\.]\d+)?)\s*([+\-−×*x÷/])\s*(\d+(?:[,\.]\d+)?)',
        message
    )
    if not match:
        return None  # pas de calcul → rien à faire

    # Étape 2 : LLM vérifie si c'est une demande d'explication
    try:
        prompt = (
            f'Un élève de primaire a écrit : "{message}"\n'
            f'Est-ce qu\'il demande de l\'aide pour comprendre ou résoudre un calcul ?\n'
            f'Réponds UNIQUEMENT par : oui / non'
        )
        result = llm_classifier.invoke([HumanMessage(content=prompt)])
        if "oui" not in result.content.strip().lower():
            return None
    except Exception:
        # Fallback mots-clés si LLM indisponible
        mots = ["montre","affiche","comment","explique","aide","fais","résoudre",
                "résous","calcule","ارني","كيف","أرني","وضّح","افعل","حل","ساعد"]
        if not any(m in message.lower() for m in mots):
            return None

    # Étape 3 : extraire et normaliser le calcul
    a  = match.group(1).replace(',', '.')
    op = match.group(2)
    b  = match.group(3).replace(',', '.')

    if op == '/':
        try:
            if float(a) < float(b):
                return None
        except Exception:
            pass

    expr_display = f"{match.group(1)} {op} {match.group(3)}"
    op_norm = (
        '÷' if op in ['/', '÷'] else
        '×' if op in ['*', 'x', '×'] else
        '-' if op == '−' else op
    )
    return (expr_display.strip(), float(a), op_norm, float(b))


def get_image_for_calcul(a, op, b, niveau):
    """
    Détermine l'image + consigne pour un calcul direct a op b.
    La consigne inclut l'exemple RÉEL de l'image pour que GPT
    explique avec les mêmes chiffres que l'image.
    """
    imgs = IMAGES_MAP.get("Français")
    ia, ib = int(a), int(b)
    nb_ch_a = len(str(ia))
    nb_ch_b = len(str(ib))
    is_decimal = (a != int(a)) or (b != int(b))

    # ── ADDITION ──
    if op in ['+']:
        u_a = ia % 10; u_b = ib % 10
        has_carry = (u_a + u_b) >= 10
        if is_decimal:
            return imgs.get("addition_decimaux"),    "addition décimaux, exemple image : 3,5 + 2,7 = 6,2"
        if nb_ch_a >= 3 or nb_ch_b >= 3:
            return imgs.get("addition_3_chiffres"),  "addition 3 chiffres, exemple image : 357 + 286 = 643"
        if nb_ch_a <= 1 and nb_ch_b <= 1:
            return imgs.get("addition_simple"),      "addition simple, exemple image : 5 + 3 = 8"
        if has_carry:
            return imgs.get("addition_avec_retenue"),"addition avec retenue, exemple image : 27 + 15 = 42"
        return     imgs.get("addition_sans_retenue"),"addition sans retenue, exemple image : 23 + 14 = 37"

    # ── SOUSTRACTION ──
    if op in ['-', '−']:
        if is_decimal:
            return imgs.get("soustraction_decimaux"),         "soustraction décimaux, exemple image : 15,3 − 8,7 = 6,6"
        u_a = ia % 10; u_b = ib % 10
        needs_borrow = u_a < u_b
        if nb_ch_a >= 3 and nb_ch_b >= 3:
            return imgs.get("soustraction_3_chiffres"),       "soustraction 3ch−3ch, exemple image : 503 − 247 = 256"
        if nb_ch_a >= 3 and nb_ch_b == 2:
            if needs_borrow:
                return imgs.get("soustraction_3ch_2ch_emprunt"),"soustraction 3ch−2ch avec emprunt, exemple image : 132 − 47 = 85"
            return imgs.get("soustraction_3_chiffres"),       "soustraction 3ch, exemple image : 503 − 247 = 256"
        if nb_ch_a >= 3 and nb_ch_b == 1:
            if needs_borrow:
                return imgs.get("soustraction_3ch_1ch_emprunt"),"soustraction 3ch−1ch avec emprunt, exemple image : 124 − 8 = 116"
            return imgs.get("soustraction_sans_retenue"),     "soustraction sans emprunt, exemple image : 48 − 23 = 25"
        if nb_ch_a == 2 and nb_ch_b == 2:
            if needs_borrow:
                return imgs.get("soustraction_avec_retenue"), "soustraction 2ch avec emprunt, exemple image : 43 − 17 = 26"
            return imgs.get("soustraction_sans_retenue"),     "soustraction sans emprunt, exemple image : 48 − 23 = 25"
        if nb_ch_a == 2 and nb_ch_b == 1:
            if needs_borrow:
                return imgs.get("soustraction_2ch_1ch_emprunt"),"soustraction 2ch−1ch avec emprunt, exemple image : 13 − 7 = 6"
            return imgs.get("soustraction_simple"),           "soustraction simple, exemple image : 7 − 3 = 4"
        return     imgs.get("soustraction_simple"),           "soustraction simple, exemple image : 7 − 3 = 4"

    # ── MULTIPLICATION ──
    if op in ['×', '*', 'x']:
        if is_decimal:
            return imgs.get("multiplication_decimaux"),    "multiplication décimaux, exemple image : 2,5 × 3 = 7,5"
        if nb_ch_a >= 3 or nb_ch_b >= 3:
            return imgs.get("multiplication_3_chiffres"), "multiplication 3 chiffres, exemple image : 245 × 36 = 8820"
        if nb_ch_a == 2 and nb_ch_b == 2:
            return imgs.get("multiplication_2_chiffres"), "multiplication 2ch×2ch, exemple image : 24 × 13 = 312"
        if nb_ch_a == 2 or nb_ch_b == 2:
            return imgs.get("multiplication_simple"),     "multiplication 2ch×1ch, exemple image : 34 × 6 = 204"
        return     imgs.get("tables_multiplication"),     "tables de multiplication, exemple image : 3 × 4 = 12"

    # ── DIVISION ──
    if op in ['÷', '/']:
        # Convertir niveau en entier (CE2 → 2, CE5 → 5...)
        try:
            nb = int(str(niveau).replace("CE","").strip())
        except Exception:
            nb = 3  # défaut CE3
        # Diviseur décimal (CE6)
        if b != int(b):
            return imgs.get("division_diviseur_decimal"), "division diviseur décimal, exemple image : 8,4 ÷ 1,2 = 7"
        # CE5+ : quotient peut être décimal
        if nb >= 5:
            return imgs.get("division_decimale"),         "division décimale, exemple image : 17 ÷ 4 = 4,25"
        # Diviseur 2 chiffres
        if nb_ch_b == 2:
            return imgs.get("division_2_chiffres"),       "division diviseur 2ch, exemple image : 156 ÷ 12 = 13"
        # CE3-CE4 : quotient entier — vérifier s'il y a un reste
        if ia % ib != 0:
            return imgs.get("division_avec_reste"),       "division avec reste, exemple image : 47 ÷ 5 = 9 reste 2"
        return     imgs.get("division_simple"),           "division simple, exemple image : 84 ÷ 4 = 21"

    return None, None


def extraire_calcul_depuis_probleme(message, operation):
    """
    Extrait le bon calcul d'un problème énoncé via GPT (llm_classifier).
    Ex: "17 pommes pour 9 amis" + "division" → "17 ÷ 9"
    Plus précis que la regex qui prenait les 2 premiers nombres sans comprendre le sens.
    """
    if not message or not operation:
        return None

    symboles = {
        "addition":       "+",
        "soustraction":   "−",
        "multiplication": "×",
        "division":       "÷",
    }
    signe = symboles.get(operation, "?")

    try:
        prompt = (
            f"Dans ce problème de {operation}, quel est le calcul à effectuer ?\n"
            f"Problème : \"{message}\"\n\n"
            f"Réponds UNIQUEMENT avec l'expression mathématique, par exemple : '17 {signe} 9'\n"
            f"Rien d'autre que l'expression."
        )
        result = llm_classifier.invoke([HumanMessage(content=prompt)])
        expr = result.content.strip()
        # Nettoyer la réponse
        expr = expr.replace('*', '×').replace('/', '÷').replace('-', '−')
        # Vérifier que c'est une expression valide (contient des chiffres et un opérateur)
        if any(c.isdigit() for c in expr) and any(op in expr for op in ['+','−','×','÷']):
            return expr
    except Exception:
        pass

    # Fallback regex : prendre les nombres les plus pertinents
    import re
    nombres = re.findall(r'\d+(?:[,\.]\d+)?', message)
    if len(nombres) >= 2:
        # Pour division/soustraction : le plus grand divisé par le dernier
        if operation in ["division", "soustraction"]:
            a = max(nombres, key=lambda x: float(x.replace(',', '.')))
            nombres_sans_a = [n for n in nombres if n != a]
            b = nombres_sans_a[-1] if nombres_sans_a else nombres[-1]
        else:
            a, b = nombres[0], nombres[-1]
        signe_map = {
            "addition": "+", "soustraction": "−",
            "multiplication": "×", "division": "÷"
        }
        return f"{a} {signe_map.get(operation, '?')} {b}"
    return None


def detecter_probleme_enonce(message):
    """
    Détecte si le message de l'élève est un problème énoncé à résoudre
    (pas un simple calcul posé).
    Retourne True si c'est un problème, False sinon.
    """
    msg = (message or "").lower()

    # Indicateurs d'un problème énoncé
    mots_probleme_fr = [
        # Prénoms courants
        "ali", "karim", "sara", "fatima", "ahmed", "mounaim", "youssef", "dina",
        # Verbes contextuels
        "il a", "elle a", "il y a", "combien", "quel est", "quelle est",
        "au total", "en tout", "restent", "reste-t-il", "manque",
        "achète", "vend", "donne", "reçoit", "partage", "partager",
        "partitionner", "répartir", "distribuer", "séparer",
        "entre", "chacun", "par personne", "par enfant",
        # Objets et unités
        "paquets", "sacs", "boîtes", "kilos", "kg", "grammes", "litres", "mètres",
        "élèves", "enfants", "pommes", "bonbons", "oranges", "personnes",
        "chaque", "par jour", "par semaine",
        # Demandes
        "problème", "résous", "calcule", "trouve", "comment faire", "comment partager",
        "je veux", "aide-moi", "comment calculer",
    ]
    mots_probleme_ar = [
        "علي", "كريم", "سارة", "فاطمة", "أحمد",
        "لديه", "عنده", "كم يبقى", "كم المجموع", "كم عدد",
        "اشترى", "باع", "أعطى", "استلم", "وزّع",
        "أكياس", "صناديق", "كيلو", "لتر", "متر",
        "تلاميذ", "أطفال", "تفاح", "حلوى", "برتقال",
        "في المجموع", "في الكل", "المتبقي",
        "مسألة", "احسب", "أوجد",
    ]

    # Présence de chiffres ET de mots de contexte = problème énoncé
    has_number = any(c.isdigit() for c in msg)
    has_context = any(mot in msg for mot in mots_probleme_fr + mots_probleme_ar)

    # Si c'est un calcul direct (ex: "3+4", "15×6"), ce n'est pas un problème
    import re
    is_direct_calc = bool(re.search(r'\d+\s*[+\-×÷*/]\s*\d+', msg))

    return has_context and has_number and not is_direct_calc


def generer_menu_choix(operation, niveau, langue):
    """
    Génère le texte du menu de choix pour l'opération et le niveau.
    Retourne (texte_menu, liste_choix, niveau_minimum) :
    - Si choix trouvés pour ce niveau → (texte, liste, None)
    - Si opération au-dessus du niveau → (None, None, niveau_minimum)
    - Si opération inconnue → (None, None, None)
    """
    niv_num = int(str(niveau).replace("CE", "")) if "CE" in str(niveau) else 3
    op_data = CHOIX_OPERATIONS.get(operation)

    if not op_data:
        return None, None, None  # Opération inconnue

    # Chercher les choix pour ce niveau ou inférieur
    choix_list = None
    for n in range(niv_num, 0, -1):
        if op_data.get(n):
            choix_list = op_data[n]
            break

    # Si aucun choix trouvé → opération hors niveau
    if not choix_list:
        # Trouver le niveau minimum de cette opération
        niv_min = min(op_data.keys())
        return None, None, niv_min

    is_ar = (langue == "العربية")
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]

    if len(choix_list) == 1:
        # Un seul choix → pas besoin de menu, on l'utilise directement
        return None, choix_list, None

    if is_ar:
        header = "اختيار رائع ! 😊 إليك أنواع العمليات التي يمكنك تعلمها :"
        footer = "اكتب رقم اختيارك ! 🎯"
    else:
        op_names = {"addition": "d'addition", "soustraction": "de soustraction",
                    "multiplication": "de multiplication", "division": "de division",
                    "fractions": "de fractions"}
        header = f"Super choix ! 😊 Voici les types {op_names.get(operation, '')} que tu peux apprendre :"
        footer = "Tape le numéro de ton choix ! 🎯"

    lines = [header, ""]
    for i, choix in enumerate(choix_list):
        label = choix["label_ar"] if is_ar else choix["label_fr"]
        lines.append(f"{emojis[i]} {label}")
    lines.append("")
    lines.append(footer)

    return "\n".join(lines), choix_list, None


def traiter_choix_numerique(message, choix_list, langue):
    """
    L'élève a tapé un numéro. Retourne le choix correspondant ou None.
    """
    msg = (message or "").strip()
    # Accepter : "1", "1️⃣", "01"
    num = None
    for i, emoji in enumerate(["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]):
        if emoji in msg:
            num = i
            break
    if num is None:
        try:
            num = int(re.sub(r'[^\d]', '', msg)) - 1
        except (ValueError, TypeError):
            return None

    if choix_list and 0 <= num < len(choix_list):
        return choix_list[num]
    return None


def detecter_image_operation(message, reponse_tuteur, niveau, langue):
    """
    Détecte quelle image pédagogique afficher.
    Déclenchée UNIQUEMENT pendant la phase d'explication (Étape 2),
    pas pendant les exercices ni la correction.
    Retourne le chemin de l'image ou None.
    """
    msg = (message or "").lower()
    rep = (reponse_tuteur or "").lower()
    images = IMAGES_MAP.get(langue, IMAGES_MAP["Français"])

    # ── Condition 1 : on affiche l'image quand l'élève demande à apprendre ──
    # Pas besoin de la réponse GPT — on se base sur le message de l'élève
    demande_apprentissage = any(mot in msg for mot in [
        # Demandes explicites
        "apprendre", "expliquer", "comment", "c'est quoi",
        "montre", "aide", "comprends pas", "je veux",
        "تعلم", "اشرح", "كيف", "ساعد", "لم أفهم", "أريد",
        # Noms d'opérations (l'élève dit directement ce qu'il veut)
        "addition", "soustraction", "multiplication", "division",
        "fraction", "table", "double", "moitié", "priorité",
        "numération", "multiple", "diviseur", "décimal",
        "الجمع", "الطرح", "الضرب", "القسمة", "الكسور",
        "جدول", "الضعف", "النصف", "أولوية", "ترقيم",
    ])

    if not demande_apprentissage:
        return None

    # ── Condition 2 : identifier le type d'opération ──
    # IMPORTANT : on se base sur le NIVEAU DE L'ÉLÈVE d'abord,
    # puis sur les mots-clés du MESSAGE DE L'ÉLÈVE (pas la réponse GPT)
    # pour éviter que GPT déclenche la mauvaise image.
    niv = niveau if niveau else "CE3"
    niv_num = int(niv.replace("CE", "")) if "CE" in str(niv) else 3
    # On utilise SEULEMENT le message de l'élève pour le type d'opération

    # --- Addition ---
    if any(mot in msg for mot in ["addition", "additionner", "ajouter", "الجمع", "يجمع"]):
        # Le NIVEAU décide, pas les mots dans la réponse GPT
        if niv_num <= 1:
            return images.get("addition_simple")
        if any(mot in msg for mot in ["décimal", "virgule", "عشري", "فاصلة"]):
            return images.get("addition_decimaux")
        if any(mot in msg for mot in ["3 chiffres", "centaine", "ثلاث", "مئ"]):
            return images.get("addition_3_chiffres")
        if any(mot in msg for mot in ["retenue", "احتفاظ"]):
            return images.get("addition_avec_retenue")
        # Par défaut selon le niveau
        if niv_num == 2:
            return images.get("addition_sans_retenue")
        elif niv_num == 3:
            return images.get("addition_avec_retenue")
        elif niv_num == 4:
            return images.get("addition_3_chiffres")
        elif niv_num >= 5:
            return images.get("addition_decimaux")
        return images.get("addition_sans_retenue")

    # --- Soustraction ---
    if any(mot in msg for mot in ["soustraction", "soustraire", "enlever", "retirer", "الطرح", "يطرح"]):
        if niv_num <= 1:
            return images.get("soustraction_simple")
        if any(mot in msg for mot in ["décimal", "virgule", "عشري", "فاصلة"]):
            return images.get("soustraction_decimaux")
        if any(mot in msg for mot in ["double emprunt", "استلافين"]):
            return images.get("soustraction_double_emprunt")
        if any(mot in msg for mot in ["3 chiffres", "centaine", "مئ"]):
            return images.get("soustraction_3_chiffres")
        if any(mot in msg for mot in ["emprunt", "emprunte", "استلاف"]):
            return images.get("soustraction_avec_retenue")
        # Par défaut selon le niveau
        if niv_num == 2:
            return images.get("soustraction_sans_retenue")
        elif niv_num == 3:
            return images.get("soustraction_avec_retenue")
        elif niv_num == 4:
            return images.get("soustraction_3_chiffres")
        elif niv_num >= 5:
            return images.get("soustraction_decimaux")
        return images.get("soustraction_sans_retenue")

    # --- Multiplication ---
    if any(mot in msg for mot in ["multiplication", "multiplie", "fois", "الضرب", "يضرب", "×"]):
        if any(mot in msg for mot in ["table", "جدول"]):
            return images.get("tables_multiplication")
        if any(mot in msg for mot in ["10", "100", "1000"]):
            return images.get("multiplication_10_100_1000")
        if any(mot in msg for mot in ["décimal", "virgule", "عشري"]):
            return images.get("multiplication_decimaux")
        if any(mot in msg for mot in ["fraction", "كسر"]):
            return images.get("multiplication_fractions")
        # Par défaut selon le niveau
        if niv_num <= 3:
            return images.get("multiplication_simple")
        elif niv_num == 4:
            return images.get("multiplication_2_chiffres")
        elif niv_num >= 5:
            return images.get("multiplication_3_chiffres")
        return images.get("multiplication_simple")

    # --- Division ---
    if any(mot in msg for mot in ["division", "divise", "partage", "القسمة", "يقسم", "÷"]):
        if any(mot in msg for mot in ["décimal", "virgule", "عشري"]):
            if any(mot in msg for mot in ["diviseur", "المقسوم عليه"]):
                return images.get("division_diviseur_decimal")
            return images.get("division_decimale")
        if any(mot in msg for mot in ["fraction", "كسر"]):
            return images.get("division_fractions")
        # Par défaut selon le niveau
        if niv_num <= 3:
            return images.get("division_simple")
        elif niv_num == 4:
            return images.get("division_2_chiffres")
        elif niv_num >= 5:
            return images.get("division_decimale")
        return images.get("division_simple")

    # --- Fractions ---
    if any(mot in msg for mot in ["fraction", "كسر", "كسور", "moitié", "quart", "tiers",
                                        "نصف", "ربع", "ثلث"]):
        if any(mot in msg for mot in ["équival", "متكافئ"]):
            return images.get("fractions_equivalentes")
        if any(mot in msg for mot in ["simplif", "تبسيط", "pgcd"]):
            return images.get("simplification_fractions")
        if any(mot in msg for mot in ["compar", "مقارنة"]):
            return images.get("comparaison_fractions")
        if any(mot in msg for mot in ["décimal", "عشري", "conversion", "تحويل", "0,5", "0,25"]):
            return images.get("fractions_decimales")
        if any(mot in msg for mot in ["multipli", "ضرب"]):
            return images.get("multiplication_fractions")
        if any(mot in msg for mot in ["divis", "قسم"]):
            return images.get("division_fractions")
        if any(mot in msg for mot in ["additionn", "جمع", "ajouter"]):
            if any(mot in msg for mot in ["différent", "مختلف"]):
                return images.get("fractions_denom_diff")
            return images.get("addition_fractions")
        if any(mot in msg for mot in ["soustrai", "طرح"]):
            return images.get("soustraction_fractions")
        if any(mot in msg for mot in ["nombre", "عدد"]):
            return images.get("fraction_d_un_nombre")
        # Par défaut selon le niveau
        if niv_num <= 4:
            return images.get("fractions_introduction")
        elif niv_num == 5:
            return images.get("addition_fractions")
        elif niv_num == 6:
            return images.get("fractions_denom_diff")
        return images.get("fractions_introduction")

    # --- Double / Moitié ---
    if any(mot in msg for mot in ["double", "moitié", "الضعف", "النصف"]):
        return images.get("double_moitie")

    # --- Priorité des opérations ---
    if any(mot in msg for mot in ["priorité", "أولوية", "d'abord", "أولا"]):
        return images.get("priorite_operations")

    # --- Multiples et diviseurs ---
    if any(mot in msg for mot in ["multiple", "diviseur", "مضاعف", "قاسم"]):
        return images.get("multiples_diviseurs")

    # --- Opérations mixtes ---
    if any(mot in msg for mot in ["mixte", "مختلط"]):
        return images.get("operations_mixtes")

    # --- Numération ---
    if any(mot in msg for mot in ["numération", "centaine", "dizaine", "unité",
                                        "ترقيم", "مئة", "عشرة", "وحدة"]):
        return images.get("numeration")

    return None


def detecter_etape(reply, user_input, verdict, etape_actuelle):
    """
    Détecte l'étape actuelle en analysant la réponse du tuteur
    et le verdict Python. Retourne la NOUVELLE étape.
    
    C'est le CŒUR de la machine à états :
    Python décide, pas GPT.
    """
    
    # ── AMORCE → CHOIX_SUJET ou EXPLICATION ──
    # L'élève a posé sa première question ou demandé à apprendre
    if etape_actuelle == "amorce":
        if any(mot in reply.lower() for mot in [
            "comme", "imagine", "billes", "bonbons", "pommes",
            "كأن", "تخيل", "كرات", "حلويات",
            "essaie maintenant", "جرب الآن",
            "✏️", "🎯"
        ]):
            return "explication"
        return "amorce"

    # ── CLARIFICATION → EXPLICATION (géré par Python, pas ici) ──
    if etape_actuelle == "clarification":
        return "clarification"

    # ── EXPLICATION → EXERCICE 1 ──
    if etape_actuelle == "explication":
        if "✏️" in reply:
            return "exercice1"
        return "explication"
    
    # ── EXERCICE 1 → CORRECTION ou EXERCICE 2 ──
    if etape_actuelle == "exercice1":
        if verdict is None:
            return "exercice1"  # Pas encore de réponse
        if verdict == "correct":
            # Correct → passe à exercice 2
            if "✏️" in reply:
                return "exercice2"
            return "exercice1"
        else:
            # Incorrect → boucle d'étayage
            return "correction1"
    
    # ── CORRECTION 1 → retour EXERCICE 1 ──
    if etape_actuelle == "correction1":
        if verdict and verdict == "correct":
            if "✏️" in reply:
                return "exercice2"
            return "correction1"
        if "✏️" in reply or "🤔" in reply:
            return "exercice1"  # Re-pose l'exercice après guidage
        return "correction1"
    
    # ── EXERCICE 2 → QUIZ ou CORRECTION ──
    if etape_actuelle == "exercice2":
        if verdict is None:
            return "exercice2"
        if verdict == "correct":
            if "🎯" in reply:
                return "quiz"
            return "exercice2"
        else:
            return "correction2"
    
    if etape_actuelle == "correction2":
        if verdict and verdict == "correct":
            if "🎯" in reply:
                return "quiz"
            return "correction2"
        return "correction2"
    
    # ── QUIZ → FÉLICITATIONS ──
    if etape_actuelle == "quiz":
        if verdict is None:
            return "quiz"
        if verdict == "correct":
            return "felicitations"
        else:
            return "correction_quiz"
    
    if etape_actuelle == "correction_quiz":
        if verdict and verdict == "correct":
            return "felicitations"
        return "correction_quiz"
    
    # ── FÉLICITATIONS → retour AMORCE (nouveau sujet) ──
    if etape_actuelle == "felicitations":
        if any(mot in user_input.lower() for mot in [
            "encore", "autre", "1️⃣", "2️⃣", "oui",
            "نعم", "آخر", "أكثر"
        ]):
            return "amorce"
        return "felicitations"
    
    return etape_actuelle


def injecter_consigne_etape(message, etape, langue):
    """
    Injecte une CONSIGNE CACHÉE dans le message envoyé à GPT
    pour FORCER le comportement de la bonne étape.
    
    C'est ce qui rend la séquence IMPOSÉE et non suggérée.
    """
    
    consignes = {
        "amorce": {
            "Français": "[CONSIGNE SYSTÈME : L'élève vient d'arriver. Accueille-le et demande ce qu'il veut apprendre. Ne pose PAS d'exercice encore.]",
            "العربية": "[تعليمات النظام : التلميذ وصل للتو. رحب به واسأله ماذا يريد أن يتعلم. لا تعطِ تمريناً بعد.]"
        },
        "choix_sujet": {
            "Français": "[CONSIGNE SYSTÈME : Un menu de choix a été affiché. ATTENDS que l'élève tape un numéro. Ne fais RIEN d'autre.]",
            "العربية": "[تعليمات النظام : تم عرض قائمة اختيارات. انتظر أن يكتب التلميذ رقماً. لا تفعل شيئاً آخر.]"
        },
        "clarification": {
            "Français": "[CONSIGNE SYSTÈME : L'élève a posé une question générique sur une opération mathématique. "
                        "Pose UNE seule question de clarification courte et naturelle (PAS de menu numéroté !). "
                        "Exemples : "
                        "Pour addition → 'Tu veux l'addition simple (23+14) ou avec retenues (47+35) ? 😊' "
                        "Pour multiplication → 'Tu veux les tables de multiplication ou comment poser un calcul comme 34×6 ? 😊' "
                        "Pour soustraction → 'Tu veux la soustraction simple ou avec emprunt comme 52-27 ? 😊' "
                        "Pour fractions → 'Tu veux découvrir les fractions (1/2, 1/4) ou les opérations avec fractions ? 😊' "
                        "Adapte la question au niveau de l'élève. Réponse TRÈS courte, 1-2 lignes max.]",
            "العربية": "[تعليمات النظام : التلميذ طرح سؤالاً عاماً عن عملية حسابية. "
                       "اطرح سؤالاً واحداً قصيراً وطبيعياً للتوضيح (بدون قائمة مرقمة !). "
                       "أمثلة : "
                       "للجمع : 'تريد الجمع البسيط (23+14) أم مع الاحتفاظ (47+35) ؟ 😊' "
                       "للضرب : 'تريد جداول الضرب أم كيف تحسب مثل 34×6 ؟ 😊' "
                       "للطرح : 'تريد الطرح البسيط أم مع الاستلاف مثل 52-27 ؟ 😊' "
                       "إجابتك قصيرة جداً، سطر أو سطرين.]"
        },
        "explication": {
            "Français": "[CONSIGNE SYSTÈME : Tu es en phase EXPLICATION. "
                        "RÈGLES ABSOLUES (violations = réponse invalide) : "
                        "❌ INTERDIT : listes numérotées, tirets, astérisques *, blocs ``` "
                        "❌ INTERDIT : décomposition verticale en texte (l'image le fait déjà) "
                        "❌ INTERDIT : dire 'Regarde l'image' si aucune image n'est affichée "
                        "✅ FORMAT : texte continu, 4-5 lignes MAX "
                        "Structure : 1) phrase d'accroche avec objet concret du quotidien "
                        "2) UNE stratégie mentale simple "
                        "3) '✏️ À toi !' + UN exercice adapté au niveau. "
                        "Si une image est affichée au-dessus : dis 'Regarde bien l'image ! 😊' et ne réexplique PAS la méthode.]",
            "العربية": "[تعليمات النظام : أنت في مرحلة الشرح. "
                       "قواعد مطلقة : "
                       "❌ ممنوع : القوائم المرقمة، النقاط، النجوم *، مربعات ``` "
                       "❌ ممنوع : التفكيك العمودي في النص "
                       "❌ ممنوع : قول 'انظر للصورة' إذا لم تكن هناك صورة "
                       "✅ الشكل : نص متواصل، 4-5 أسطر كحد أقصى "
                       "الهيكل : 1) جملة ربط بشيء ملموس من الحياة اليومية "
                       "2) استراتيجية ذهنية واحدة بسيطة "
                       "3) '✏️ دورك !' + تمرين واحد مناسب للمستوى. "
                       "إذا كانت هناك صورة : قل 'انظر للصورة ! 😊' ولا تشرح الطريقة مجدداً.]"
        },
        "exercice1": {
            "Français": "[CONSIGNE SYSTÈME : Un exercice a été posé (✏️). ATTENDS la réponse. Ne donne PAS la solution.]",
            "العربية": "[تعليمات النظام : تم طرح تمرين (✏️). انتظر الإجابة. لا تعطِ الحل.]"
        },
        "correction1": {
            "Français": "[CONSIGNE SYSTÈME : La réponse est INCORRECTE. "
                        "RÈGLES ABSOLUES : "
                        "❌ NE DONNE JAMAIS la bonne réponse directement. "
                        "❌ PAS de markdown gras **réponse**. "
                        "❌ NE POSE PAS de nouvel exercice (✏️) — attends que l'élève retente. "
                        "✅ Applique les 4 TEMPS dans cet ordre STRICT : "
                        "TEMPS 1 : Encouragement chaleureux ('👏 C'est courageux !') "
                        "TEMPS 2 : Diagnostic (explique POURQUOI c'est faux, avec la méthode) "
                        "TEMPS 3 : Guidage socratique (pose UNE question pour guider SANS donner la réponse) "
                        "TEMPS 4 : ARRÊTE-TOI. N'écris plus rien. Attends que l'élève réponde à ta question.]",
            "العربية": "[تعليمات النظام : الإجابة خاطئة. "
                       "قواعد مطلقة : "
                       "❌ لا تعطِ الإجابة الصحيحة مباشرة أبداً. "
                       "❌ لا تستخدم الخط العريض **إجابة**. "
                       "❌ لا تطرح تمريناً جديداً (✏️) — انتظر أن يحاول التلميذ مجدداً. "
                       "✅ طبق المراحل الأربع بهذا الترتيب الصارم : "
                       "المرحلة 1 : تشجيع حار ('👏 شجاع أنك حاولت !') "
                       "المرحلة 2 : تشخيص (اشرح لماذا الإجابة خاطئة مع الطريقة) "
                       "المرحلة 3 : توجيه سقراطي (اطرح سؤالاً واحداً للتوجيه بدون إعطاء الإجابة) "
                       "المرحلة 4 : توقف. لا تكتب شيئاً آخر. انتظر رد التلميذ.]"
        },
        "exercice2": {
            "Français": "[CONSIGNE SYSTÈME : Pose l'exercice 2 (✏️) avec des nombres DIFFÉRENTS. ATTENDS la réponse.]",
            "العربية": "[تعليمات النظام : اطرح التمرين 2 (✏️) بأرقام مختلفة. انتظر الإجابة.]"
        },
        "quiz": {
            "Français": "[CONSIGNE SYSTÈME : Pose le QUIZ (🎯) — 1 seule question. ATTENDS la réponse.]",
            "العربية": "[تعليمات النظام : اطرح الاختبار (🎯) — سؤال واحد فقط. انتظر الإجابة.]"
        },
        "felicitations": {
            "Français": "[CONSIGNE SYSTÈME : L'élève a RÉUSSI ! Félicite-le avec 🏆, rappelle la stratégie apprise, et propose : 1️⃣ Encore des exercices 2️⃣ Autre sujet]",
            "العربية": "[تعليمات النظام : التلميذ نجح ! هنئه بـ 🏆، ذكّره بالاستراتيجية، واقترح : 1️⃣ تمارين أخرى 2️⃣ موضوع آخر]"
        }
    }
    
    # Corrections partagent la même consigne
    for c in ["correction2", "correction_quiz"]:
        consignes[c] = consignes["correction1"]
    
    consigne = consignes.get(etape, {}).get(langue, "")
    
    if consigne:
        return f"{message}\n{consigne}"
    return message
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
        r7_niv  = '"C\'est une question de géant ! 🌟 Moi je connais les nombres entiers. Restons sur ça pour l\'instant ! 💪"'

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
PRIORITÉ ABSOLUE
════════════════════════════════
Si le message contient [CONSIGNE] ou [تعليمات النظام], ces instructions
ont la priorité sur TOUTES les règles ci-dessous. Suis-les à la lettre.

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
8. Ne mentionne JAMAIS le mauvais nombre de l'élève dans ta réponse. Donne uniquement le résultat correct.
9. JAMAIS de markdown : INTERDIT d'utiliser **gras**, *italique*, # titres, listes -, listes 1. ou tout autre formatage. Texte brut uniquement.
10. JAMAIS de décomposition verticale en texte si une image est déjà affichée — l'image le montre.

════════════════════════════════
CHAPITRES COUVERTS (CE1 → CE6)
════════════════════════════════
Tu enseignes ces opérations du primaire :
✅ Addition (+)
✅ Soustraction (-)  → résultat toujours positif en primaire
✅ Multiplication (×)
✅ Division (÷)  → inclut la division posée, division avec reste, division décimale
✅ Fractions      → introduction, opérations sur fractions (CE3 → CE6)

✅ INCLUS dans la division et les opérations :
   Les problèmes énoncés (partage, distribution, contextuels) FONT PARTIE des 4 opérations.
   "45 bonbons partagés entre 7 enfants" = division : 45 ÷ 7 → aide toujours l'élève.
   "Ali a 3 sacs de 4 bonbons" = multiplication → aide toujours l'élève.
   Ces problèmes NE sont PAS hors de ton domaine.

❌ HORS DOMAINE (seulement ces sujets) :
   Géométrie, histoire, science, sport, cuisine, géographie, langues,
   mesures, algèbre, physique-chimie, tout ce qui n'est PAS arithmétique.

   Pour ces sujets seulement, réponds :
   FR : "Hihi, bonne question ! 🌟 Mais je suis spécialisé dans les opérations : addition ➕, soustraction ➖, multiplication ✖️ et division ➗. Pour tout le reste, ton professeur est là pour toi ! 😊 Que veux-tu apprendre avec moi ?"
   AR : "هيهي، سؤال جميل ! 🌟 لكنني متخصص فقط في العمليات : الجمع ➕ والطرح ➖ والضرب ✖️ والقسمة ➗. لكل شيء آخر، أستاذك هو من يساعدك ! 😊 ماذا تريد أن تتعلم معي ؟"

════════════════════════════════
SÉQUENCE PÉDAGOGIQUE (ordre strict)
════════════════════════════════

📖 EXPLICATION (Apprentissage actif — OBLIGATOIRE avant tout exercice) :
Tu dois TOUJOURS expliquer AVANT de poser un exercice. L'explication suit ces règles :

1. ANCRAGE CONCRET : Relie l'opération à un objet du quotidien de l'enfant.
   EXCEPTION : Si une [CONSIGNE] précise les chiffres à utiliser, utilise CES chiffres uniquement.
   Exemples d'objets : bonbons 🍬, billes 🔵, pommes 🍎, doigts 🤚, étoiles ⭐
   ✅ "L'addition, c'est comme mettre des billes dans un sac."
   ❌ "L'addition est une opération qui consiste à..."

2. DÉCOMPOSITION VISUELLE VERTICALE : Montre le calcul POSÉ VERTICALEMENT avec les retenues visibles.
   EXCEPTION ABSOLUE : Si une image pédagogique est affichée, NE fais PAS de décomposition en texte.
   L'image montre déjà la méthode — dis juste "Regarde bien l'image ! 😊"
   RÈGLE : Toujours poser les calculs verticalement, jamais horizontalement.
   Utilise 🔴 pour les retenues et 🟢 pour le résultat final.

   - Addition avec retenue (ex: 27+35) :
     "  2 7
     + 3 5
     -----
     🔴 1    (7+5=12, j'écris 2 je retiens 🔴1)
       6 2  🟢
     → Unités : 7+5=12 → j'écris 2, je retiens 🔴1
     → Dizaines : 2+3+🔴1=6
     → Résultat : 🟢 62 !"

   - Soustraction avec emprunt (ex: 52-27) :
     " ⁴5 ¹²2
     -  2  7
     -------
          2 5  🟢
     → Unités : 2<7 → j'emprunte 🔴1 dizaine → 12-7=5
     → Dizaines : 5-🔴1-2=2
     → Résultat : 🟢 25 !"

   - Multiplication avec retenue (ex: 23×4) :
     "  2 3
     ×   4
     -----
     🔴 1    (3×4=12, j'écris 2 je retiens 🔴1)
       9 2  🟢
     → Unités : 3×4=12 → j'écris 2, je retiens 🔴1
     → Dizaines : 2×4+🔴1=9
     → Résultat : 🟢 92 !"

   - Division euclidienne (ex: 95÷4) :
     " 9 5 | 4
       8   |----
       --  | 2 3  🟢
       1 5
       1 2
       ---
         3  (reste)
     → Vérification : 4×23+3=95 ✅"

   - Fractions 1/2 :
     "   1
      ─── = une moitié 🍕
       2
     → Pizza coupée en 2 parts égales, tu prends 1 !"

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

🎯 QUIZ (Validation des acquis — 1 question) :
→ "🎯 Question : Combien font [a] [op] [b] ?"
→ ATTENDS la réponse.
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

# LLM léger pour la classification d'intention (rapide + économique)
@st.cache_resource
def get_llm_classifier(_api_key):
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=_api_key,
        max_tokens=10   # 1 mot suffit
    )

llm_classifier = get_llm_classifier(api_key)

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
if "choix_list"    not in st.session_state: st.session_state["choix_list"]    = None
if "choix_image"   not in st.session_state: st.session_state["choix_image"]   = None
if "choix_consigne" not in st.session_state: st.session_state["choix_consigne"] = None
if "choix_list"     not in st.session_state: st.session_state["choix_list"]     = None
if "hors_niveau_operation" not in st.session_state: st.session_state["hors_niveau_operation"] = None
if "hors_niveau_niv_min"   not in st.session_state: st.session_state["hors_niveau_niv_min"]   = None
# ── Persistance des images dans l'historique ──────────────────
if "images_history" not in st.session_state: st.session_state["images_history"] = {}
# ── Compteur de bonnes réponses consécutives (Python contrôle) ──
if "bonnes_consec"  not in st.session_state: st.session_state["bonnes_consec"]  = 0
# ── Calcul direct posé par l'élève (ex: "13-7") ────────────────
if "calcul_direct"  not in st.session_state: st.session_state["calcul_direct"]  = None
if "operation_detectee" not in st.session_state: st.session_state["operation_detectee"] = None

chat_history   = st.session_state[session_key]
etape_actuelle = st.session_state[etape_key]
score          = st.session_state[score_key]
eleve_info     = st.session_state[eleve_key]
chat_actif     = st.session_state[chat_actif_key]

# Score affiché dans la sidebar

# ============================================================
# 13. FORMULAIRE DÉMARRAGE ou BARRE INFO ÉLÈVE
# ============================================================
NIVEAUX_FR = ["CE1 — 1ère année", "CE2 — 2ème année", "CE3 — 3ème année",
               "CE4 — 4ème année", "CE5 — 5ème année", "CE6 — 6ème année"]
NIVEAUX_AR = ["السنة الأولى — CE1", "السنة الثانية — CE2", "السنة الثالثة — CE3",
               "السنة الرابعة — CE4", "السنة الخامسة — CE5", "السنة السادسة — CE6"]
NIVEAUX_LIST = NIVEAUX_AR if langue_choisie == "العربية" else NIVEAUX_FR
# Clé unique par langue → liste se réinitialise automatiquement
_niv_key = "niveau_input_ar" if langue_choisie == "العربية" else "niveau_input_fr"

if not chat_actif:
    # ── Formulaire prénom + niveau ──────────────────────────
    lbl_prenom = "👦 Ton prénom" if langue_choisie == "Français" else "👦 اسمك"
    lbl_niveau = "📚 Ton niveau" if langue_choisie == "Français" else "📚 مستواك"
    lbl_start  = "🚀 Commencer" if langue_choisie == "Français" else "🚀 ابدأ"

    # Bandeau compact animé
    if langue_choisie == "Français":
        titre_html = (
            "<span style=\"font-size:1.05rem; font-weight:400; color:white;\">🧮 Bienvenue ! "
            "Je suis ton tuteur IA en mathématiques.</span><br>"
            "<span style=\"font-size:0.87rem; font-weight:400; color:white; opacity:0.9;\">"
            "Veuillez écrire ton prénom, sélectionner un niveau et cliquer sur Commencer."
            "</span>"
        )
    else:
        titre_html = (
            "<span style=\"font-size:1.05rem; font-weight:400; color:white;\">🧮 مرحباً ! "
            "أنا معلمك الذكي في الرياضيات.</span><br>"
            "<span style=\"font-size:0.87rem; font-weight:400; color:white; opacity:0.9;\">"
            "يرجى كتابة اسمك واختيار مستواك والنقر على ابدأ."
            "</span>"
        )
    st.markdown(f'''<div class="start-form" dir="{direction}"><h3>{titre_html}</h3></div>''', unsafe_allow_html=True)

    col_p, col_n = st.columns(2)
    with col_p:
        prenom_input = st.text_input(lbl_prenom, key="prenom_input",
                                     placeholder="Écris ton prénom ici..." if langue_choisie=="Français" else "اكتب اسمك هنا...")
    with col_n:
        _ph = "Choisis ton niveau ici" if langue_choisie == "Français" else "اختر مستواك هنا"
        niveau_input = st.selectbox(lbl_niveau, [""] + NIVEAUX_LIST, key=_niv_key,
                                    format_func=lambda x: _ph if x == "" else x)



    btn_disabled = not (prenom_input.strip() and niveau_input)
    col_g1, col_g2, col_g3 = st.columns([2, 2, 2])
    with col_g2:
        btn_clicked = st.button(lbl_start,
                 disabled=btn_disabled, key="btn_start",
                 use_container_width=True)
    if btn_clicked:
        # Ouvrir la session
        prenom = prenom_input.strip()
        # Extraire CE1..CE6 peu importe la langue
        import re as _re
        _m = _re.search(r'CE\d', niveau_input)
        niveau = _m.group(0) if _m else niveau_input.split("—")[0].strip()
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
    st.stop()

else:
    # ============================================================
    # ── BOUTONS D'ACTION (RECOMMENCER & TÉLÉCHARGER) ──
    # ============================================================
    lbl_new   = "🔄 Recommencer" if langue_choisie == "Français" else "🔄 من جديد"
    lbl_print = "⬇️ Télécharger" if langue_choisie == "Français" else "⬇️ تحميل"

    st.components.v1.html(f"""
    <script>
    (function() {{
        function styleActionBtns() {{
            var doc = window.parent.document;
            var actionRow = null;
            
            doc.querySelectorAll('button').forEach(function(btn) {{
                var txt = (btn.innerText || btn.textContent || '').trim();
                
                // Cible UNIQUEMENT ces deux boutons pour protéger les langues
                var isNew = txt.includes('Recommencer') || txt.includes('\u0645\u0646 \u062c\u062f\u064a\u062f');
                var isDl  = txt.includes('charger') || txt.includes('\u062a\u062d\u0645\u064a\u0644');
                
                if (!isNew && !isDl) return; // Ignore tout le reste (Langues, Envoyer, etc.)
                
                var wrapper = btn.closest('div[data-testid="stButton"], div[data-testid="stDownloadButton"]');
                if (wrapper) {{
                    wrapper.style.setProperty('width', '100%', 'important');
                    wrapper.style.setProperty('display', 'flex', 'important');
                    wrapper.style.setProperty('justify-content', 'center', 'important');
                    wrapper.style.setProperty('margin', '0', 'important');
                }}

                btn.setAttribute('style',
                    'background: linear-gradient(135deg, #FF6B6B, #FFE66D) !important;' + 
                    'color: #333 !important;' +
                    'border: none !important;' +
                    'border-radius: 50px !important;' + 
                    'font-family: Fredoka One, cursive !important;' +
                    'font-size: 0.9rem !important;' + 
                    'display: flex !important;' +
                    'align-items: center !important;' +
                    'justify-content: center !important;' +
                    'padding: 8px 4px !important;' + 
                    'width: 100% !important;' + 
                    'max-width: 100% !important;' +
                    'margin: 0 !important;' +
                    'white-space: nowrap !important;' +
                    'box-shadow: 0 2px 6px rgba(255,107,107,0.3) !important;'
                );
                
                btn.querySelectorAll('p, span, div').forEach(function(el) {{
                    el.style.cssText = 'margin:0 !important;padding:0 !important;text-align:center !important;color:#333 !important;font-size:inherit !important;white-space:nowrap !important;';
                }});

                var block = btn.closest('div[data-testid="stHorizontalBlock"]');
                if (block) actionRow = block;
            }});

            if (actionRow) {{
                actionRow.style.setProperty('display', 'flex', 'important');
                actionRow.style.setProperty('flex-direction', 'row', 'important');
                actionRow.style.setProperty('flex-wrap', 'wrap', 'important'); 
                actionRow.style.setProperty('justify-content', 'center', 'important'); 
                actionRow.style.setProperty('gap', '15px', 'important'); 
                actionRow.style.setProperty('width', '100%', 'important');
                actionRow.style.setProperty('margin-bottom', '15px', 'important'); 
                
                var cols = actionRow.querySelectorAll('div[data-testid="column"]');
                cols.forEach(function(c) {{
                    // TAILLE IDENTIQUE ET RÉDUITE : 135px pour les deux !
                    c.style.setProperty('width', '135px', 'important'); 
                    c.style.setProperty('max-width', '135px', 'important'); 
                    c.style.setProperty('flex', '0 1 135px', 'important'); 
                    c.style.setProperty('min-width', '0', 'important'); 
                    c.style.setProperty('padding', '0', 'important');
                    c.style.setProperty('margin', '0', 'important');
                }});
            }}
        }}
        setInterval(styleActionBtns, 300); 
    }})();
    </script>
    """, height=0)

    _bn2, _bn4 = st.columns(2)
    with _bn2:
        if st.button(lbl_new, use_container_width=True, key="btn_new"):
            sc  = st.session_state[score_key]
            inf = st.session_state[eleve_key]
            import datetime as _dt
            debut = st.session_state.get("debut_session")
            duree = int((_dt.datetime.now() - debut).total_seconds()) if debut else 0
            db_maj_session(
                session_id    = inf.get("session_db_id"),
                bonnes        = sc["bonnes"],
                total         = sc["total"],
                nb_messages   = len(st.session_state[session_key]),
                etape_finale  = st.session_state.get(etape_key, "amorce"),
                duree_minutes = duree,
            )
            st.session_state[session_key]    = []
            st.session_state[etape_key]      = "amorce"
            st.session_state[score_key]      = {"bonnes": 0, "total": 0}
            st.session_state["bonnes_consec"]  = 0
            st.session_state["images_history"] = {}
            st.session_state["choix_image"]    = None
            st.session_state["choix_consigne"] = None
            st.session_state["choix_list"]     = None
            st.session_state[eleve_key]      = {"prenom": "", "niveau": "", "session_db_id": None}
            st.session_state[chat_actif_key] = False
            st.session_state["debut_session"]  = None
            st.session_state["taux_max"]       = 0
            st.rerun()
            
    with _bn4:
        if st.button(lbl_print, use_container_width=True, key="btn_download_conv"):
            import datetime as _dt
            from fpdf import FPDF
            import re as _re
            prenom_d = st.session_state[eleve_key].get("prenom", "Élève")
            niveau_d = st.session_state[eleve_key].get("niveau", "")
            sc_d     = st.session_state[score_key]
            debut_d  = st.session_state.get("debut_session")
            duree_d  = int((_dt.datetime.now() - debut_d).total_seconds()) if debut_d else 0
            taux_d   = round(sc_d["bonnes"]/sc_d["total"]*100) if sc_d["total"]>0 else 0
            inf_dl   = st.session_state[eleve_key]
            db_maj_session(
                session_id=inf_dl.get("session_db_id"), bonnes=sc_d["bonnes"],
                total=sc_d["total"], nb_messages=len(st.session_state[session_key]),
                etape_finale=st.session_state.get(etape_key,"amorce"), duree_minutes=duree_d)
            
            def _clean(txt):
                import unicodedata
                txt = _re.sub(r'[\U00010000-\U0010ffff]', '', txt)
                txt = _re.sub(r'[\u2600-\u27ff]', '', txt)
                txt = _re.sub(r'[\u2000-\u206f]', '', txt)
                txt = _re.sub(r'[\u0600-\u06ff]', '', txt)
                txt = txt.replace('**','').replace('*','')
                txt = txt.replace('\u2019',"'").replace('\u2018',"'")
                txt = txt.replace('\u201c','"').replace('\u201d','"')
                txt = txt.replace('\u2013','-').replace('\u2014','-')
                result = ''
                for c in txt:
                    try:
                        c.encode('latin-1')
                        result += c
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        result += '?'
                return result.strip()

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
            nom_clean = _clean(f"Discussion - {prenom_d} ({niveau_d})")
            pdf.cell(0,8,nom_clean,align="C",ln=True)
            pdf.set_y(42); pdf.set_text_color(100,100,120); pdf.set_font("Helvetica","",10)
            pdf.set_x(15)
            date_str = _dt.datetime.now().strftime('%d/%m/%Y %H:%M')
            pdf.cell(60,7,f"Date : {date_str}",ln=False)
            pdf.cell(60,7,_clean(f"Niveau : {niveau_d}"),ln=False)
            pdf.cell(60,7,f"Duree : {duree_d} secondes",ln=True)
            pdf.set_y(55); pdf.set_fill_color(240,255,254); pdf.set_text_color(15,110,86)
            pdf.set_font("Helvetica","B",12); pdf.set_x(15)
            pdf.cell(180,10,f"Score : {sc_d['bonnes']}/{sc_d['total']} - Taux : {taux_d}%",
                     border=1,align="C",fill=True,ln=True)
            pdf.ln(3)
            pdf.set_draw_color(229,231,235)
            pdf.line(15,pdf.get_y(),195,pdf.get_y())
            pdf.ln(3)
            pdf.set_text_color(26,26,46)
            for msg in st.session_state[session_key]:
                is_eleve = isinstance(msg, HumanMessage)
                texte    = _clean(msg.content)
                if not texte: continue
                if is_eleve:
                    pdf.set_fill_color(238,237,254)
                    pdf.set_font("Helvetica","B",9)
                    pdf.set_x(100); pdf.cell(95,6,"Eleve",ln=True,align="R")
                    pdf.set_font("Helvetica","",9)
                    for l in texte.split("\n"):
                        if l.strip():
                            pdf.set_x(100)
                            pdf.multi_cell(95,5,l.strip(),fill=True,align="R")
                else:
                    pdf.set_fill_color(225,245,238)
                    pdf.set_font("Helvetica","B",9)
                    pdf.set_x(15); pdf.cell(95,6,"Tuteur IA",ln=True)
                    pdf.set_font("Helvetica","",9)
                    for l in texte.split("\n"):
                        if l.strip():
                            pdf.set_x(15)
                            pdf.multi_cell(95,5,l.strip(),fill=True)
                pdf.ln(2)
            pdf.set_y(-20)
            pdf.set_draw_color(229,231,235)
            pdf.line(15,pdf.get_y(),195,pdf.get_y())
            pdf.set_font("Helvetica","I",8); pdf.set_text_color(150,150,170)
            pdf.cell(0,8,"PFE - Tuteur IA Mathematiques - FSE Rabat 2025-2026",align="C")
            fname = f"discussion_{_clean(prenom_d)}_{_dt.datetime.now().strftime('%d%m%Y_%H%M')}.pdf"
            st.download_button(
                label="📥 Telecharger PDF" if langue_choisie=="Français" else "📥 تحميل PDF",
                data=bytes(pdf.output()),
                file_name=fname,
                mime="application/pdf", key="btn_dl_pdf", use_container_width=True)

    # ── Barre info élève (visible pendant la session) ────────
    prenom_disp = eleve_info.get("prenom","")
    niveau_disp = eleve_info.get("niveau","")
    st.markdown(
        f'<div class="eleve-info-wrap"><div class="eleve-info-bar" dir="{direction}">'
        f'👦 <strong>{prenom_disp}</strong> &nbsp;|&nbsp; 📚 {niveau_disp}</div></div>',
        unsafe_allow_html=True
    )
        # ── Badge félicitations ────────────────────────────────────
    if etape_actuelle == "felicitations":
        sc_final = st.session_state[score_key]
        taux_final = round(sc_final["bonnes"] / sc_final["total"] * 100) if sc_final["total"] > 0 else 0
        if taux_final >= 80:
            badge_emoji, badge_color = "🏆", "#FFD700"
            badge_msg = "Excellent travail !" if langue_choisie == "Français" else "عمل ممتاز !"
        elif taux_final >= 50:
            badge_emoji, badge_color = "⭐", "#4ECDC4"
            badge_msg = "Bon travail !" if langue_choisie == "Français" else "عمل جيد !"
        else:
            badge_emoji, badge_color = "💪", "#FF9A3C"
            badge_msg = "Continue d'essayer !" if langue_choisie == "Français" else "استمر في المحاولة !"

        st.markdown(f"""
        <div style="text-align:center; padding:10px; margin:6px 0;
                    background:linear-gradient(135deg,{badge_color}22,{badge_color}44);
                    border-radius:14px; border:2px solid {badge_color};">
            <div style="font-size:30px;">{badge_emoji}</div>
            <div style="font-size:13px; font-weight:700; color:#333;">{badge_msg}</div>
            <div style="font-size:12px; color:#555;">{"Score" if langue_choisie == "Français" else "النقاط"} : {taux_final}%</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# 14. AFFICHAGE HISTORIQUE + AUTO-SCROLL
# ============================================================
# Les images sont stockées dans images_history {index → path}
# et réaffichées à chaque rerun pour qu'elles persistent.
_img_hist = st.session_state.get("images_history", {})
for i, msg in enumerate(chat_history):
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        if role == "assistant":
            _img_stored = _img_hist.get(i)
            contenu = msg.content
            # Reconstituer l'affichage intro → image → suite si image stockée
            if _img_stored and os.path.exists(_img_stored):
                st.image(_img_stored, use_container_width=True)
            st.markdown(f'<div dir="{direction}">{contenu}</div>', unsafe_allow_html=True)
        else:
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
# 16. CONVERSATION PRINCIPALE
# ============================================================
# ── Barre taux de réussite en bas ──────────────────────────
_bonnes = st.session_state[score_key]["bonnes"]
_total  = st.session_state[score_key]["total"]

# Taux réel recalculé à chaque fois
_taux_aff = round(_bonnes / _total * 100) if _total > 0 else 0

if _taux_aff >= 80:
    _bar_col = "#4ECDC4, #00b894"
    _star = "🌟"
elif _taux_aff >= 50:
    _bar_col = "#FF9A3C, #FFD93D"
    _star = "⭐"
else:
    _bar_col = "#FF6B6B, #FF9A3C"
    _star = "💪"

_titre = f"🏅 {_bonnes}/{_total} — {_taux_aff}% {_star}" if langue_choisie == "Français" else f"🏅 {_bonnes}/{_total} — {_taux_aff}% {_star}"

_, _col_bar, _ = st.columns([2, 2, 2])
with _col_bar:
    st.markdown(f"""
    <div style="margin:4px auto; padding:5px 12px;
                background:white; border-radius:14px;
                border:1.5px solid #4ECDC4;
                box-shadow:0 2px 8px rgba(78,205,196,0.15);
                font-family:'Fredoka One',cursive;">
        <div style="font-size:11px; color:#0F6E56; font-weight:700;
                    text-align:center; margin-bottom:4px;">
            {_titre} — {_taux_aff}%
        </div>
        <div style="background:#f0f0f0; border-radius:20px;
                    height:10px; overflow:hidden;">
            <div style="background:linear-gradient(90deg,{_bar_col});
                        width:{_taux_aff}%; height:100%;
                        border-radius:20px;"></div>
        </div>
        <div style="font-size:9px; color:#aaa; text-align:center; margin-top:2px;">
            {_bonnes}/{_total}
        </div>
    </div>
    """, unsafe_allow_html=True)


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

    # ── APPROCHE HYBRIDE : spécifique → image auto / générique → clarification ──
    etape_actuelle = st.session_state[etape_key]
    niveau_eleve   = st.session_state[eleve_key].get("niveau", "CE3")

    # ── Helpers locaux ──────────────────────────────────────────
    def _niv_num(niv):
        try: return int(str(niv).replace("CE",""))
        except: return 3

    def est_question_generique(msg):
        """True si l'élève nomme une opération sans préciser le type."""
        m = (msg or "").lower().strip()
        mots_generiques = [
            "addition","soustraction","multiplication","division",
            "fractions","fraction","tables","table","décimaux","décimal",
            "الجمع","الطرح","الضرب","القسمة","الكسور","جداول","جدول",
        ]
        mots_specifiques = [
            "retenue","emprunt","sans","avec","simple","deux chiffres","trois chiffres",
            "virgule","décimale","dénominateur","fractions équivalentes",
            "احتفاظ","استلاف","بدون","بعدد","أرقام","عشري",
        ]
        has_generic  = any(mot in m for mot in mots_generiques)
        has_specific = any(mot in m for mot in mots_specifiques)
        has_number   = any(c.isdigit() for c in m)
        # Générique = opération nommée sans précision et sans chiffres
        return has_generic and not has_specific and not has_number

    def get_image_for_question(msg, niv):
        """Détecte l'image directement depuis la question de l'élève + niveau."""
        m   = (msg or "").lower()
        n   = _niv_num(niv)
        imgs = IMAGES_MAP.get(langue_choisie, IMAGES_MAP["Français"])

        # ── Tables ──
        if any(x in m for x in ["table","جدول","جداول"]):
            return imgs.get("tables_multiplication"), "tables de multiplication de 1 à 9"

        # ── Addition ──
        if any(x in m for x in ["addition","additionner","ajouter","الجمع"]):
            if any(x in m for x in ["décim","virgule","عشري","فاصلة"]):
                return imgs.get("addition_decimaux"), "addition de nombres décimaux"
            if any(x in m for x in ["3 chiffres","trois chiffres","ثلاث","مئ"]):
                return imgs.get("addition_3_chiffres"), "addition à 3 chiffres avec retenues"
            if any(x in m for x in ["retenue","retenu","احتفاظ"]):
                return imgs.get("addition_avec_retenue"), "addition avec retenue, 2 chiffres"
            if any(x in m for x in ["sans retenue","sans retenu","بدون احتفاظ"]):
                return imgs.get("addition_sans_retenue"), "addition sans retenue, 2 chiffres"
            # Défaut selon niveau
            if n <= 1: return imgs.get("addition_simple"),        "addition simple, 1 chiffre"
            if n == 2: return imgs.get("addition_sans_retenue"),   "addition sans retenue, 2 chiffres"
            if n == 3: return imgs.get("addition_avec_retenue"),   "addition avec retenue, 2-3 chiffres"
            if n == 4: return imgs.get("addition_3_chiffres"),     "addition à 3 chiffres"
            return imgs.get("addition_decimaux"), "addition de nombres décimaux"

        # ── Soustraction ──
        if any(x in m for x in ["soustraction","soustraire","enlever","الطرح"]):
            if any(x in m for x in ["décim","virgule","عشري"]):
                return imgs.get("soustraction_decimaux"), "soustraction de décimaux"
            if any(x in m for x in ["double emprunt","استلافين"]):
                return imgs.get("soustraction_double_emprunt"), "soustraction avec double emprunt, 3 chiffres"
            if any(x in m for x in ["3 chiffres","trois chiffres"]) and any(x in m for x in ["3 chiffres","trois chiffres","mêm"]):
                return imgs.get("soustraction_3_chiffres"), "soustraction à 3 chiffres"
            if any(x in m for x in ["emprunt","استلاف","retenu","retenue"]):
                return imgs.get("soustraction_avec_retenue"), "soustraction avec emprunt, 2 chiffres"
            if n <= 1: return imgs.get("soustraction_simple"),       "soustraction simple"
            if n == 2: return imgs.get("soustraction_sans_retenue"), "soustraction sans emprunt"
            if n == 3: return imgs.get("soustraction_avec_retenue"), "soustraction avec emprunt"
            if n == 4: return imgs.get("soustraction_3_chiffres"),   "soustraction à 3 chiffres"
            return imgs.get("soustraction_decimaux"), "soustraction de décimaux"

        # ── Multiplication ──
        if any(x in m for x in ["multiplication","multiplier","multiplie","الضرب","يضرب","×"]):
            if any(x in m for x in ["table","جدول"]):
                return imgs.get("tables_multiplication"), "tables de multiplication"
            if any(x in m for x in ["10","100","1000"]):
                return imgs.get("multiplication_10_100_1000"), "multiplication par 10, 100, 1000"
            if any(x in m for x in ["décim","virgule","عشري"]):
                return imgs.get("multiplication_decimaux"), "multiplication de décimaux"
            if any(x in m for x in ["fraction","كسر"]):
                return imgs.get("multiplication_fractions"), "multiplication de fractions"
            if any(x in m for x in ["deux chiffres","2 chiffres","بعددين"]):
                return imgs.get("multiplication_2_chiffres"), "multiplication 2 chiffres × 2 chiffres, deux lignes + addition finale"
            if n <= 3: return imgs.get("tables_multiplication"),   "tables de multiplication"
            if n == 4: return imgs.get("multiplication_simple"),   "multiplication 2 chiffres × 1 chiffre"
            if n == 5: return imgs.get("multiplication_2_chiffres"), "multiplication 2 chiffres × 2 chiffres"
            return imgs.get("multiplication_3_chiffres"), "multiplication à 3 chiffres"

        # ── Division ──
        if any(x in m for x in ["division","diviser","divise","القسمة","يقسم","÷"]):
            if any(x in m for x in ["diviseur décimal","مقسوم عليه عشري"]):
                return imgs.get("division_diviseur_decimal"), "division avec diviseur décimal, multiplier les deux par 10"
            if any(x in m for x in ["décim","virgule","عشري"]):
                return imgs.get("division_decimale"), "division avec quotient décimal"
            if any(x in m for x in ["fraction","كسر"]):
                return imgs.get("division_fractions"), "division de fractions"
            if any(x in m for x in ["deux chiffres","2 chiffres","بعددين"]):
                return imgs.get("division_2_chiffres"), "division posée, diviseur à 2 chiffres"
            if any(x in m for x in ["reste","الباقي"]):
                return imgs.get("division_avec_reste"), "division avec reste"
            if n <= 3: return imgs.get("division_simple"),     "division simple, exemple image : 84 ÷ 4 = 21"
            if n == 4: return imgs.get("division_2_chiffres"), "division diviseur 2ch, exemple image : 156 ÷ 12 = 13"
            return imgs.get("division_decimale"), "division décimale, exemple image : 17 ÷ 4 = 4,25"

        # ── Fractions ──
        if any(x in m for x in ["fraction","كسر","كسور","moitié","quart","tiers","نصف","ربع","ثلث"]):
            if any(x in m for x in ["équival","متكافئ"]):
                return imgs.get("fractions_equivalentes"), "fractions équivalentes"
            if any(x in m for x in ["simplif","تبسيط","pgcd"]):
                return imgs.get("simplification_fractions"), "simplification de fractions"
            if any(x in m for x in ["compar","مقارنة"]):
                return imgs.get("comparaison_fractions"), "comparaison de fractions"
            if any(x in m for x in ["décim","0,","عشري","0."]):
                return imgs.get("fractions_decimales"), "conversion fraction ↔ décimal"
            if any(x in m for x in ["multipli","ضرب"]):
                return imgs.get("multiplication_fractions"), "multiplication de fractions"
            if any(x in m for x in ["divis","قسم"]):
                return imgs.get("division_fractions"), "division de fractions"
            if any(x in m for x in ["additionn","جمع","ajouter"]):
                if any(x in m for x in ["différent","مختلف","dénominateurs différents"]):
                    return imgs.get("fractions_denom_diff"), "addition fractions dénominateurs différents, PPCM"
                return imgs.get("addition_fractions"), "addition de fractions même dénominateur"
            if any(x in m for x in ["soustrai","طرح"]):
                return imgs.get("soustraction_fractions"), "soustraction de fractions même dénominateur"
            if any(x in m for x in ["nombre","عدد","de 20","de 12"]):
                return imgs.get("fraction_d_un_nombre"), "prendre une fraction d'un nombre entier"
            if n <= 4: return imgs.get("fractions_introduction"),  "lecture de fractions, numérateur et dénominateur"
            if n == 5: return imgs.get("addition_fractions"),      "addition de fractions même dénominateur"
            return imgs.get("fractions_denom_diff"), "addition fractions dénominateurs différents"

        # ── Autres concepts ──
        if any(x in m for x in ["double","moitié","الضعف","النصف"]):
            return imgs.get("double_moitie"), "double et moitié"
        if any(x in m for x in ["priorité","أولوية"]):
            return imgs.get("priorite_operations"), "priorité des opérations"
        if any(x in m for x in ["multiple","diviseur","مضاعف","قاسم"]):
            return imgs.get("multiples_diviseurs"), "multiples et diviseurs"
        if any(x in m for x in ["numérat","centaine","dizaine","مئة","عشرة"]):
            return imgs.get("numeration"), "numération centaines, dizaines, unités"

        return None, None

    # ══════════════════════════════════════════════════════════════
    # FLUX HYBRIDE — Le niveau sert uniquement aux statistiques Supabase.
    # Le chatbot répond à TOUTE question sans restriction de niveau.
    # L'image est choisie selon la question/calcul, pas le niveau.
    # ══════════════════════════════════════════════════════════════

    # ── Détection calcul dans une demande d'explication (TOUS ÉTATS) ──
    # Ex: "montre moi comment faire 24-17" pendant correction/exercice
    if etape_actuelle not in ("amorce", "clarification", "explication"):
        calcul_phrase = extraire_calcul_dans_phrase(user_input)
        if calcul_phrase:
            expr_p, a_p, op_p, b_p = calcul_phrase
            img_path_p, consigne_p = get_image_for_calcul(a_p, op_p, b_p, niveau_eleve)
            if img_path_p and os.path.exists(img_path_p):
                st.session_state["choix_image"]    = img_path_p
                st.session_state["choix_consigne"] = consigne_p
                st.session_state["calcul_direct"]  = expr_p
                st.session_state[etape_key]        = "explication"
                etape_actuelle                     = "explication"

    # ── Détection changement de sujet EN COURS de séquence ──────
    mots_changement = ["passe à","passe a","change de","autre chose","autre sujet",
                       "maintenant","je veux apprendre","ننتقل","موضوع آخر","الآن أريد"]
    est_changement = (
        etape_actuelle in ("exercice1","exercice2","correction1","correction2","quiz","correction_quiz","explication")
        and any(m in user_input.lower() for m in mots_changement)
        and detecter_operation_demandee(user_input) is not None
    )
    if est_changement:
        st.session_state[etape_key]       = "amorce"
        st.session_state["bonnes_consec"]  = 0
        st.session_state["choix_image"]    = None
        st.session_state["choix_consigne"] = None
        etape_actuelle = "amorce"

    if etape_actuelle == "amorce":
        operation = detecter_operation_demandee(user_input)

        # ── CAS 1 : Calcul direct (ex: "13-7", "27+35", "15/4") ──
        calcul = detecter_calcul_direct(user_input)
        if calcul and not operation:
            expr, a, op, b = calcul
            img_path, consigne = get_image_for_calcul(a, op, b, niveau_eleve)
            # Pour la version arabe, utiliser l'image AR correspondante
            if img_path and langue_choisie == "العربية":
                ar_imgs = IMAGES_MAP.get("العربية", {})
                for key, path in IMAGES_MAP["Français"].items():
                    if path == img_path:
                        ar_path = ar_imgs.get(key, img_path)
                        if os.path.exists(ar_path):
                            img_path = ar_path
                        break
            if consigne:
                st.session_state["choix_consigne"] = consigne
            if img_path and os.path.exists(img_path):
                st.session_state["choix_image"] = img_path
            else:
                # Log de diagnostic pour comprendre pourquoi l'image ne charge pas
                import logging
                logging.warning(f"[IMAGE] Introuvable : {img_path}")
                logging.warning(f"[IMAGE] ABS_PATH = {ABS_PATH}")
                logging.warning(f"[IMAGE] Existe : {os.path.exists(img_path) if img_path else 'None'}")
                st.session_state["choix_image"] = None
            st.session_state["calcul_direct"] = expr
            st.session_state[etape_key] = "explication"

        elif operation:
            # ── CAS 2 : Question générique → clarification ──
            if est_question_generique(user_input):
                st.session_state["hors_niveau_operation"] = operation
                st.session_state[etape_key] = "clarification"

            # ── CAS 3 : Question spécifique → image précise via calcul extrait ──
            else:
                # Extraire le calcul réel via llm_classifier pour choisir la bonne image
                # Ex: "9 pommes sur quatre enfants" → "9 ÷ 4" → 9%4≠0 → division_avec_reste
                calcul_extrait = extraire_calcul_depuis_probleme(user_input, operation)
                img_path, consigne = None, None

                if calcul_extrait:
                    # Parser l'expression extraite pour get_image_for_calcul
                    import re as _re
                    _m = _re.search(
                        r'(\d+(?:[,\.]\d+)?)\s*([+\-−×÷*/])\s*(\d+(?:[,\.]\d+)?)',
                        calcul_extrait
                    )
                    if _m:
                        _a  = float(_m.group(1).replace(',', '.'))
                        _op = ('÷' if _m.group(2) in ['/', '÷'] else
                               '×' if _m.group(2) in ['*', '×'] else
                               '-' if _m.group(2) == '−' else _m.group(2))
                        _b  = float(_m.group(3).replace(',', '.'))
                        img_path, consigne = get_image_for_calcul(_a, _op, _b, niveau_eleve)
                        st.session_state["calcul_direct"] = calcul_extrait

                # Fallback : get_image_for_question si extraction échoue
                if not img_path:
                    msg_avec_op = f"{operation} {user_input}"
                    img_path, consigne = get_image_for_question(msg_avec_op, niveau_eleve)

                if consigne:
                    st.session_state["choix_consigne"] = consigne
                if img_path and os.path.exists(img_path):
                    st.session_state["choix_image"] = img_path
                else:
                    st.session_state["choix_image"] = None
                    if img_path:
                        import logging
                        logging.warning(f"[IMAGE CAS3] Introuvable : {img_path}")
                st.session_state["operation_detectee"] = operation
                st.session_state[etape_key] = "explication"

    # ── CAS 4 : Réponse à la clarification ──
    elif etape_actuelle == "clarification":
        stored_op = st.session_state.get("hors_niveau_operation", "")
        combined  = f"{stored_op} {user_input}".strip()
        img_path, consigne = get_image_for_question(combined, niveau_eleve)
        if consigne:
            st.session_state["choix_consigne"] = consigne
        if img_path and os.path.exists(img_path):
            st.session_state["choix_image"] = img_path
        else:
            st.session_state["choix_image"] = None
            if img_path:
                import logging
                logging.warning(f"[IMAGE CAS4] Introuvable : {img_path}")
        st.session_state[etape_key] = "explication"
        st.session_state["hors_niveau_operation"] = None

    # RAG (optionnel — silencieux si ChromaDB indisponible)
    context = ""
    if vectorstore:
        try:
            query   = f"mathématiques primaire {user_input}"
            docs    = vectorstore.similarity_search(query, k=3)
            context = "\n\n".join([doc.page_content for doc in docs])
        except Exception:
            context = ""

    # Prompt de base (sera recréé dans le bloc GPT avec l'étape courante)
    prenom_eleve  = st.session_state[eleve_key].get("prenom", "")
    niveau_eleve  = st.session_state[eleve_key].get("niveau", "")

    with st.chat_message("assistant"):
        with st.spinner(t["thinking"]):
            try:
                # ── 1. Injection verdict Python AVANT GPT ──────
                message_avec_verdict = injecter_verdict(
                    user_input, chat_history, langue_choisie
                )
                
                # ── 2. Image et consigne du menu de choix ──────
                etape_actuelle = st.session_state[etape_key]
                _img_path = st.session_state.get("choix_image")
                _choix_consigne = st.session_state.get("choix_consigne")

                if _img_path and not os.path.exists(_img_path):
                    _img_path = None

                # ── 3. Machine à états : Injection de la consigne ──────
                # Récupérer le calcul direct si posé par l'élève
                _calcul_direct = st.session_state.pop("calcul_direct", None)
                consigne_specifique = ""
                # Si problème énoncé → extraire le calcul pour l'exercice
                _op_detectee = st.session_state.pop("operation_detectee", None)
                if not _calcul_direct and _op_detectee and detecter_probleme_enonce(user_input):
                    _calcul_direct = extraire_calcul_depuis_probleme(user_input, _op_detectee)
                _exercice_final = (
                    f"Combien font  {_calcul_direct} ?"
                    if _calcul_direct
                    else f"un exercice de type : {_choix_consigne}"
                )
                _exercice_final_ar = (
                    f"كم يساوي  {_calcul_direct} ?"
                    if _calcul_direct
                    else f"تمرين من نوع : {_choix_consigne}"
                )

                if _img_path and _choix_consigne and etape_actuelle == "explication":
                    # CAS A : Image affichée → consigne avec référence à l'image
                    # Fix 3 : exercice cohérent avec l'image
                    # Fix 5 : si 2ch×2ch → explication des 3 étapes obligatoire
                    is_2x2 = any(k in (_choix_consigne or "") for k in [
                        "2 chiffres", "deux chiffres", "3 chiffres", "trois chiffres",
                        "عددين", "رقمين"
                    ])
                    # Fix 6 : détecter si l'élève a posé un problème énoncé
                    is_pb = detecter_probleme_enonce(user_input)

                    if langue_choisie == "العربية":
                        if is_pb:
                            consigne_specifique = (
                                f"[تعليمات النظام : مسألة حسابية. "
                                f"اكتب 5-6 أسطر بدون قوائم أو نجوم. "
                                f"اسأل 'ماذا نعرف ؟ ماذا نبحث ؟' ثم حدد العملية المناسبة وحل الحساب. "
                                f"اختم بـ '✏️ دورك !' بمسألة مشابهة.]"
                            )
                        elif is_2x2:
                            consigne_specifique = (
                                f"[تعليمات النظام : اكتب إجابتك بهذا الشكل بالضبط :\n"
                                f"السطر 1 : 'لحل هذه المسألة نستخدم الضرب ! ✖️'\n"
                                f"السطر 2 : 'انظر للصورة أدناه 👇 ستجد مثالاً على الطريقة'\n"
                                f""
                                f"السطر 3-4 : اشرح مثال الصورة : السطر الأول = الآحاد تضرب الكل، السطر الثاني = العشرات + نقطة •، ثم الجمع. استخدم أرقام الصورة فقط : {_choix_consigne}\n"
                                f"السطر 5 : 'والآن طبق نفس الطريقة :'\n"
                                f"السطر 6 : '✏️ دورك !' مع : {_exercice_final_ar}\n"
                                f"لا تعطِ الجواب. انتظر التلميذ.]"
                            )
                        else:
                            consigne_specifique = (
                                f"[تعليمات النظام : اكتب إجابتك بهذا الشكل بالضبط :\n"
                                f"السطر 1 : 'لحل هذه المسألة نستخدم [اسم العملية] !'\n"
                                f"السطر 2 : 'انظر للصورة أدناه 👇 ستجد مثالاً على الطريقة'\n"
                                f""
                                f"السطر 3-4 : اشرح مثال الصورة بجملة أو جملتين باستخدام أرقام الصورة فقط : {_choix_consigne}\n"
                                f"السطر 5 : 'والآن طبق نفس الطريقة على مسألتك :'\n"
                                f"السطر 6 : '✏️ دورك !' مع : {_exercice_final_ar}\n"
                                f"لا تحسب. لا تعطِ الجواب. انتظر التلميذ.]"
                            )
                    else:
                        if is_pb:
                            consigne_specifique = (
                                f"[CONSIGNE : Écris ta réponse dans ce format exact :\n"
                                f"Ligne 1 : 'Pour résoudre ce problème, on utilise la [NOM OPERATION] !'\n"
                                f"Ligne 2 : 'Regarde l'image ci-dessus ! 😊 Elle te montre comment faire'\n"
                                f"Ligne 3-4 : Explique l'exemple de l'image en langage simple adapté à un enfant.\n"
                                f"Chiffres à utiliser : {_choix_consigne}\n"
                                f"Pour une DIVISION : dis 'Dans l'image, on partage [X] en [Y] groupes égaux, chaque groupe reçoit [Z]' — JAMAIS 'se répète'.\n"
                                f"Pour une ADDITION : dis 'Dans l'image, on ajoute [X] et [Y], on obtient [Z]'.\n"
                                f"Pour une SOUSTRACTION : dis 'Dans l'image, on enlève [Y] de [X], il reste [Z]'.\n"
                                f"Pour une MULTIPLICATION : dis 'Dans l'image, [X] fois [Y] donne [Z]'.\n"
                                f"Ligne 5 : 'Maintenant, applique la même méthode pour ton problème :'\n"
                                f"Ligne 6 : '✏️ À toi !' avec : {_exercice_final}\n"
                                f"NE CALCULE PAS la réponse. ATTENDS que l'élève réponde.]"
                            )
                        elif is_2x2:
                            consigne_specifique = (
                                f"[CONSIGNE : Écris ta réponse dans ce format exact :\n"
                                f"Ligne 1 : 'Pour ce calcul, on utilise la MULTIPLICATION ! ✖️'\n"
                                f"Ligne 2 : 'Regarde l'image ci-dessus ! 😊 Elle te montre la méthode'\n"
                                f"Ligne 3-4 : Explique l'exemple de l'image en langage simple : {_choix_consigne}\n"
                                f"Dis : 'ligne 1 = les unités multiplient tout, ligne 2 = les dizaines multiplient tout + un point •, puis on additionne les deux lignes'.\n"
                                f"Ligne 5 : 'Maintenant, applique la même méthode :'\n"
                                f"Ligne 6 : '✏️ À toi !' avec : {_exercice_final}\n"
                                f"Ne donne pas la réponse.]"
                            )
                        else:
                            consigne_specifique = (
                                f"[CONSIGNE : Écris ta réponse dans ce format exact :\n"
                                f"Ligne 1 : 'Pour ce calcul, on utilise [NOM OPERATION] !'\n"
                                f"Ligne 2 : 'Regarde l'image ci-dessus ! 😊 Elle te montre comment faire'\n"
                                f"Ligne 3-4 : Explique l'exemple de l'image en langage simple adapté à un enfant.\n"
                                f"Chiffres à utiliser : {_choix_consigne}\n"
                                f"Pour une DIVISION : 'Dans l'image, on partage [X] en [Y] groupes égaux, chaque groupe reçoit [Z]'.\n"
                                f"Pour une ADDITION : 'Dans l'image, on ajoute [X] et [Y], on obtient [Z]'.\n"
                                f"Pour une SOUSTRACTION : 'Dans l'image, on enlève [Y] de [X], il reste [Z]'.\n"
                                f"Pour une MULTIPLICATION : 'Dans l'image, [X] fois [Y] donne [Z]'.\n"
                                f"Ligne 5 : 'Maintenant à toi d'appliquer la même méthode :'\n"
                                f"Ligne 6 : '✏️ À toi !' avec : {_exercice_final}\n"
                                f"NE CALCULE PAS. NE DONNE PAS la réponse. ATTENDS l'élève.]"
                            )
                    message_final = f"{message_avec_verdict}\n{consigne_specifique}"
                    st.session_state["choix_image"] = None
                    st.session_state["choix_consigne"] = None

                elif _choix_consigne and etape_actuelle == "explication":
                    # CAS B : Pas d'image mais on a un type d'exercice
                    is_pb = detecter_probleme_enonce(user_input)
                    if langue_choisie == "العربية":
                        if is_pb:
                            consigne_specifique = (
                                f"[تعليمات النظام : لا توجد صورة. مسألة حسابية. اكتب 5 أسطر بدون قوائم. "
                                f"الخطوة 1 : سمِّ العملية 'لحل هذه المسألة نستخدم [العملية] !' "
                                f"الخطوة 2 : اشرح الطريقة بجملة واحدة بسيطة "
                                f"الخطوة 3 : 'والآن دورك :' "
                                f"الخطوة 4 : '✏️ دورك !' مع : {_exercice_final_ar}. "
                                f"لا تقل 'انظر للصورة'. لا تعطِ الجواب.]"
                            )
                        else:
                            consigne_specifique = (
                                f"[تعليمات النظام : لا توجد صورة. اكتب 4-5 أسطر بدون قوائم أو نجوم. "
                                f"الخطوة 1 : 'سنستخدم [العملية] !' "
                                f"الخطوة 2 : مثال بسيط من الحياة اليومية "
                                f"الخطوة 3 : طريقة ذهنية واحدة "
                                f"الخطوة 4 : '✏️ دورك !' مع : {_choix_consigne}. "
                                f"لا تقل 'انظر للصورة'. لا تعطِ الجواب.]"
                            )
                    else:
                        if is_pb:
                            consigne_specifique = (
                                f"[CONSIGNE : Pas d'image. Problème énoncé. Écris 5 lignes sans listes. "
                                f"Étape 1 : 'Pour résoudre ce problème, on utilise [OPERATION] !' "
                                f"Étape 2 : Explique la méthode en 1 phrase simple "
                                f"Étape 3 : 'Maintenant à toi :' "
                                f"Étape 4 : '✏️ À toi !' avec : {_exercice_final}. "
                                f"Ne dis jamais 'Regarde l'image'. Ne donne pas la réponse.]"
                            )
                        else:
                            consigne_specifique = (
                                f"[CONSIGNE : Pas d'image. Écris 4-5 lignes sans listes ni astérisques. "
                                f"Étape 1 : 'Pour ce calcul, on utilise [OPERATION] !' "
                                f"Étape 2 : Un exemple concret de la vie quotidienne "
                                f"Étape 3 : Une astuce mentale en une phrase "
                                f"Étape 4 : '✏️ À toi !' avec : {_choix_consigne}. "
                                f"Ne dis jamais 'Regarde l'image'. Ne donne pas la réponse.]"
                            )
                    message_final = f"{message_avec_verdict}\n{consigne_specifique}"
                    st.session_state["choix_consigne"] = None

                else:
                    # CAS C : Flux normal (exercices, corrections, quiz...)
                    message_final = injecter_consigne_etape(
                        message_avec_verdict, etape_actuelle, langue_choisie
                    )
                    consigne_specifique = ""
                    _img_path = None

                # ── 3. Construire le system prompt avec la consigne courante ──
                # La consigne est dans le system prompt → priorité haute → GPT ne peut pas l'ignorer
                _consigne_sys = ""
                if consigne_specifique:
                    _consigne_sys = (
                        "\n\n════════ INSTRUCTION PRIORITAIRE COURANTE ════════\n"
                        f"{consigne_specifique}\n"
                        "══════════════════════════════════════════════════"
                    )
                system_prompt = get_system_prompt(
                    langue_choisie, context,
                    prenom=prenom_eleve, niveau=niveau_eleve
                ) + _consigne_sys

                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}")
                ])

                response = (prompt | llm).invoke({
                    "input": message_final,
                    "chat_history": chat_history[-10:]
                })
                assistant_reply = response.content

                # ── Nettoyage + validation Python APRÈS GPT ─
                assistant_reply = post_traitement(
                    assistant_reply, user_input, chat_history, langue_choisie
                )

                # ── Verdict Python ──────────────────────────────
                _verdict = verifier_reponse(user_input, chat_history)
                if _verdict is not None:
                    st.session_state[score_key]["total"] += 1
                    if _verdict == "correct":
                        st.session_state[score_key]["bonnes"] += 1

                # ── Fix 2 : Progression par compteur Python ─────
                etape_av = st.session_state[etape_key]

                if _verdict == "correct":
                    st.session_state["bonnes_consec"] += 1
                elif _verdict == "incorrect":
                    st.session_state["bonnes_consec"] = 0

                # exercice1 → 1 bonne → exercice2
                if etape_av == "exercice1" and _verdict == "correct":
                    st.session_state[etape_key] = "exercice2"
                    st.session_state["bonnes_consec"] = 0

                # correction1 → 1 bonne → exercice2
                elif etape_av == "correction1" and _verdict == "correct":
                    st.session_state[etape_key] = "exercice2"
                    st.session_state["bonnes_consec"] = 0

                # exercice2 → 1 bonne → quiz
                elif etape_av == "exercice2" and _verdict == "correct":
                    st.session_state[etape_key] = "quiz"
                    st.session_state["bonnes_consec"] = 0

                # correction2 → 1 bonne → quiz
                elif etape_av == "correction2" and _verdict == "correct":
                    st.session_state[etape_key] = "quiz"
                    st.session_state["bonnes_consec"] = 0

                # quiz → 1 bonne → félicitations
                elif etape_av in ("quiz", "correction_quiz") and _verdict == "correct":
                    st.session_state[etape_key] = "felicitations"
                    st.session_state["bonnes_consec"] = 0

                # CORRECTIONS : incorrect → rester en correction (PAS avancer même si ✏️ dans reply)
                elif etape_av == "exercice1" and _verdict == "incorrect":
                    st.session_state[etape_key] = "correction1"
                elif etape_av == "exercice2" and _verdict == "incorrect":
                    st.session_state[etape_key] = "correction2"
                elif etape_av in ("quiz", "correction_quiz") and _verdict == "incorrect":
                    st.session_state[etape_key] = "correction_quiz"

                # États de correction : rester jusqu'à une bonne réponse
                elif etape_av in ("correction1", "correction2", "correction_quiz"):
                    # Ne PAS avancer même si GPT a posé un ✏️ dans sa réponse
                    # L'élève doit retenter — on attend son verdict
                    pass

                # explication → exercice1 (quand GPT a posé ✏️)
                elif etape_av == "explication" and "✏️" in assistant_reply:
                    st.session_state[etape_key] = "exercice1"
                    st.session_state["bonnes_consec"] = 0

                else:
                    # Fallback machine à états texte pour les autres cas
                    nouvelle_etape = detecter_etape(
                        assistant_reply, user_input, _verdict, etape_av
                    )
                    st.session_state[etape_key] = nouvelle_etape

                # ── Félicitations : gérer choix 1 (encore) et 2 (autre sujet) ──
                if etape_av == "felicitations":
                    msg_strip = user_input.strip()
                    ul = user_input.lower()
                    # Changer de sujet → reset complet + message amorce direct
                    if msg_strip in ["2", "٢", "2️⃣"] or "autre" in ul or "آخر" in ul or "changer" in ul:
                        st.session_state[etape_key]      = "amorce"
                        st.session_state["bonnes_consec"] = 0
                        st.session_state["choix_image"]   = None
                        st.session_state["choix_consigne"] = None
                        if langue_choisie == "العربية":
                            msg_amorce = f"رائع ! 😊 ماذا تريد أن تتعلم الآن {prenom_eleve} ؟\nالجمع ➕ الطرح ➖ الضرب ✖️ القسمة ➗"
                        else:
                            msg_amorce = f"Super ! 😊 Qu'est-ce que tu veux apprendre maintenant {prenom_eleve} ?\nAddition ➕ Soustraction ➖ Multiplication ✖️ Division ➗"
                        st.session_state[session_key].append(HumanMessage(content=user_input))
                        st.session_state[session_key].append(AIMessage(content=msg_amorce))
                        with st.chat_message("assistant"):
                            st.markdown(f'<div dir="{direction}">{msg_amorce}</div>', unsafe_allow_html=True)
                        db_ajouter_message(st.session_state[eleve_key].get("session_db_id"), "eleve", user_input)
                        db_ajouter_message(st.session_state[eleve_key].get("session_db_id"), "tuteur", msg_amorce)
                        st.rerun()
                    # Encore des exercices → reset état mais garde le sujet
                    elif msg_strip in ["1", "١", "1️⃣"] or "encore" in ul or "oui" in ul or "نعم" in ul:
                        st.session_state[etape_key]      = "amorce"
                        st.session_state["bonnes_consec"] = 0

                # ── Stocker l'image dans l'historique persistant ──────
                if _img_path:
                    next_idx = len(chat_history) + 1
                    st.session_state["images_history"][next_idx] = _img_path

                # ── Affichage stable : image en haut, texte dessous ──────
                if _img_path:
                    st.image(_img_path, use_container_width=True)
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
    # Mise à jour stats en temps réel (avec durée)
    sc    = st.session_state[score_key]
    debut = st.session_state.get("debut_session")
    import datetime as _dt2
    duree_rt = int((_dt2.datetime.now() - debut).total_seconds()) if debut else 0
    db_maj_session(
        session_id    = sid_db,
        bonnes        = sc["bonnes"],
        total         = sc["total"],
        nb_messages   = len(st.session_state[session_key]),
        etape_finale  = st.session_state.get(etape_key, "amorce"),
        duree_minutes = duree_rt,
    )
    st.rerun()

# ============================================================
# 17. FOOTER + ACCÈS ADMIN SECRET
# ============================================================
# ── Footer 2 TuteurIA → admin même page ─────────────────────
if "admin_ouvert2" not in st.session_state:
    st.session_state["admin_ouvert2"] = False
if "admin_ok" not in st.session_state:
    st.session_state["admin_ok"] = False

# Détecter ?admin=1 dans l'URL
try:
    _qp2 = st.query_params
    if _qp2.get("admin") == "1":
        st.session_state["admin_ouvert2"] = True
        st.query_params.clear()
        st.rerun()
except Exception:
    pass

    # Footer 2 simple
    st.markdown("""
    <style>
    div[data-testid="stButton"]:has(button[key="btn_download_conv"]) button,
    div[data-testid="stButton"]:has(button[key^="btn_admin_close"]) button,
    div[data-testid="stButton"]:has(button[key^="btn_admin_deco"]) button {
        background: linear-gradient(135deg, #4ECDC4, #45B7D1) !important;
        background-image: linear-gradient(135deg, #4ECDC4, #45B7D1) !important;
        color: white !important;
        border: none !important;
        border-radius: 20px !important;
        font-size: 0.8rem !important;
        padding: 4px 12px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 6px !important;
        width: auto !important;
        min-width: 40px !important;
        height: 32px !important;
        margin: 0 auto !important;
        font-family: 'Fredoka One', cursive !important;
        white-space: nowrap !important;
        box-shadow: 0 2px 6px rgba(78,205,196,0.3) !important;
    }
    </style>
    """, unsafe_allow_html=True)



if st.session_state["admin_ouvert2"]:
    st.markdown("---")
    st.markdown("### 🔐 Espace Administrateur")

    if not st.session_state["admin_ok"]:
        # Avant connexion : titre + bouton Fermer
        col_t2, col_x2 = st.columns([5, 1])
        with col_t2:
            st.markdown("**Entrez le mot de passe admin :**")
        with col_x2:
           if st.button("✖️", key="btn_admin_close_pre2", use_container_width=False):
                st.session_state["admin_ouvert2"] = False
                st.rerun()
        pwd = st.text_input("Mot de passe :", type="password", key="admin_pwd2")
        if st.button("🔓 Connexion", key="btn_admin_login2"):
            if pwd == ADMIN_PASSWORD:
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect")
    else:
        # Dashboard : titre + Déconnexion + Fermer
        col_titre2, col_deco2, col_close2 = st.columns([3, 1, 1])
        with col_titre2:
            st.markdown("#### 📊 Tableau de bord")
        with col_deco2:
            if st.button("🔒", key="btn_admin_deco2",
                         type="secondary", use_container_width=True):
                st.session_state["admin_ok"] = False
                st.rerun()
        with col_close2:
            if st.button("✖️", key="btn_admin_close2",
                         type="secondary", use_container_width=True):
                st.session_state["admin_ok"]      = False
                st.session_state["admin_ouvert2"] = False
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
                with d1: st.metric("⏱️ Durée moy.", f"{round(df_d['duree_minutes'].mean(),0):.0f} sec")
                with d2: st.metric("⏱️ Durée totale", f"{int(df_d['duree_minutes'].sum())} sec")
                with d3: st.metric("⏱️ Min. session", f"{int(df_d['duree_minutes'].min())} sec")
                with d4: st.metric("⏱️ Max. session", f"{int(df_d['duree_minutes'].max())} sec")

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
                    "taux":"Taux %","duree_minutes":"Durée (sec)",
                    "nb_messages":"Messages","etape_finale":"Étape"
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "Taux %": st.column_config.ProgressColumn("Taux %", min_value=0, max_value=100),
                    "Durée (sec)": st.column_config.NumberColumn("⏱️ Durée (sec)"),
                }
            )

            # ── Export CSV ────────────────────────────────────
            csv = df[cols_affich].to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Exporter CSV", csv,
                               "sessions_pfe.csv", "text/csv",
                               key="btn_export_csv2")
