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
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "") or _os2.getenv("ADMIN_PASSWORD", "")

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
def formater_duree(secondes):
    """Convertit des secondes en format lisible (ex: 2m 30s)"""
    try:
        # Sécurité pour les valeurs vides ou NaN (souvent le cas avec .mean() en Pandas)
        if secondes is None or secondes != secondes: 
            return "0s"
            
        sec = int(secondes)
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        
        if h > 0:
            return f"{h}h {m}m"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"
    except Exception:
        return "0s"

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
    /* Rendre le texte des boutons en gras */
    div:not([data-testid="stHorizontalBlock"]) > div > button {
        font-weight: 800 !important;
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
        "footer":       "🧮 TuteurIA | Mounaim 2026"
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
        "footer":       "🧮 TuteurIA | Mounaim 2026"
    }
}

# ============================================================
# 4. CONFIGURATION PÉDAGOGIQUE — Cycle Primaire Marocain
# ============================================================
# Chapitres couverts (CE1 → CE6)
CHAPITRES_PRIMAIRE = ["Addition", "Soustraction", "Multiplication", "Division"]

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
    chapitres_ligne = "➕ الجمع &nbsp;·&nbsp; ➖ الطرح &nbsp;·&nbsp; ✖️ الضرب &nbsp;·&nbsp; 🔢 القسمة"
else:
    chapitres_ligne = "➕ Addition &nbsp;·&nbsp; ➖ Soustraction &nbsp;·&nbsp; ✖️ Multiplication &nbsp;·&nbsp; 🔢 Division"

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
    Extrait l'expression mathématique en scannant TOUT le message de l'assistant.
    Rend Python 100% capable de suivre l'exercice même si l'IA oublie ou déplace l'emoji.
    """
    for msg in reversed(historique):
        if isinstance(msg, AIMessage):
            texte = msg.content.replace('−', '-')
            
            # Chercher TOUS les calculs (entiers uniquement) présents dans le message de l'IA
            matches = list(re.finditer(r'(\d+(?:\s*[+\-×*x÷/]\s*\d+)+)', texte))
            
            if matches:
                # Par défaut, on prend le tout dernier calcul mentionné par le tuteur
                expression_brute = matches[-1].group(1).strip()
                
                # Priorité ABSOLUE : calcul près de ✏️ 🤔 "font" → c'est l'exercice posé à l'élève
                for m in reversed(matches):
                    idx = m.start()
                    contexte_avant = texte[max(0, idx-40):idx].lower()
                    contexte_apres = texte[idx:idx+40].lower()
                    if any(mot in contexte_avant for mot in ["✏️", "🤔", "font", "يساوي", "calcule", "combien font", "كم يساوي"]):
                        expression_brute = m.group(1).strip()
                        break  # STOP — ne pas continuer, cet exercice est prioritaire
                    if any(mot in contexte_apres for mot in ["✏️", "🤔", "?"]):
                        expression_brute = m.group(1).strip()
                        break
                
                # Nettoyage et évaluation
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
                    continue
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
    # Normaliser le signe moins Unicode → ASCII
    user_message = user_message.replace('−', '-')
    exercice = extraire_exercice(historique)
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

    # ── Division euclidienne : vérifier quotient + reste ──
    exercice = extraire_exercice(historique)
    if exercice:
        expr = exercice[0]
        if '÷' in expr or '/' in expr:
            # Extraire a et b de "a ÷ b"
            parts = re.split(r'[÷/]', expr.replace(' ', ''))
            if len(parts) == 2:
                try:
                    a, b = int(parts[0]), int(parts[1])
                    quotient = a // b
                    reste = a % b
                    msg_lower = user_message.lower()
                    # L'élève a donné quotient + reste ?
                    if any(mot in msg_lower for mot in ["reste", "الباقي", "r"]):
                        nombres_trouves = re.findall(r'\d+', user_message)
                        if len(nombres_trouves) >= 2:
                            q_eleve = int(nombres_trouves[0])
                            r_eleve = int(nombres_trouves[1])
                            if q_eleve == quotient and r_eleve == reste:
                                return 'correct'
                            else:
                                etapes_div = [f"{a} ÷ {b} = {quotient} reste {reste}"]
                                return f'incorrect:{quotient} reste {reste}:{"| ".join(etapes_div)}'
                    # L'élève a donné juste le quotient (sans reste)
                    if reponse_eleve == quotient and reste == 0:
                        return 'correct'
                    elif reponse_eleve == quotient and reste != 0:
                        # Quotient correct mais reste manquant
                        etapes_div = [f"{a} ÷ {b} = {quotient} reste {reste}"]
                        return f'presque:{quotient} reste {reste}:{"| ".join(etapes_div)}'
                except (ValueError, ZeroDivisionError):
                    pass

    return ('correct' if reponse_eleve == resultat_attendu
            else f'incorrect:{resultat_attendu}:{"| ".join(etapes)}')

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
                    f"→ Explique ces étapes avec emojis. OBLIGATOIRE : termine par '✏️ À toi !' avec un exercice aux nombres DIFFÉRENTS.]")
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
    elif parties[0] == 'presque':
        resultat = parties[1]
        exercice = extraire_exercice(historique)
        exercice_str = f"{exercice[0]}" if exercice else "cette division"
        if langue == "العربية":
            return (f"{user_message}\n[VERDICT PYTHON: PRESQUE CORRECT 🟡\n"
                    f"القسمة = {resultat}\n"
                    f"التلميذ أعطى الحاصل الصحيح لكنه نسي الباقي.\n"
                    f"قل 'أحسنت على الحاصل ! 👏 لكن لا تنسَ الباقي !\n"
                    f"أعطني الجواب الكامل : الحاصل والباقي معاً.\n"
                    f"✏️ كم يساوي {exercice_str} ؟ 🤔']")
        else:
            return (f"{user_message}\n[VERDICT PYTHON: PRESQUE CORRECT 🟡\n"
                    f"Division = {resultat}\n"
                    f"L'élève a donné le bon quotient mais a oublié le reste.\n"
                    f"Dis 'Bravo pour le quotient ! 👏 Mais n'oublie pas le reste !\n"
                    f"Donne-moi la réponse COMPLÈTE : le quotient ET le reste.\n"
                    f"✏️ Combien font {exercice_str} ? 🤔']")
    else:
        resultat = parties[1]
        etapes_str = " → ".join(parties[2].split('|')) if len(parties) > 2 and parties[2] else ""

        if langue == "العربية":
            _is_div = '÷' in etapes_str or 'reste' in resultat or 'الباقي' in resultat
            _div_warning = "\n⚠️ القسمة دائماً بالحاصل + الباقي. ممنوع الأعداد العشرية!" if _is_div else ""
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌\n"
                f"الجواب الصحيح = {resultat}\n"
                f"الخطوات الصحيحة بالترتيب : {etapes_str}\n"
                f"1. شجع الطالب بلطف 😊\n"
                f"2. قل 'تذكر الصورة التي رأيناها ! 😊' واشرح الخطوات بالأرقام الحقيقية للتمرين\n"
                f"3. لا تعطِ الجواب مباشرة. اسأل سؤالاً للتوجيه : 'حاول مرة أخرى 🤔'\n"
                f"4. انتظر جواب الطالب{_div_warning}]"
            )
        else:
            _is_div = '÷' in etapes_str or 'reste' in resultat
            _div_warning = "\n⚠️ DIVISION : résultat en quotient + reste, JAMAIS de décimaux !" if _is_div else ""
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌\n"
                f"Résultat correct = {resultat}\n"
                f"Étapes exactes dans l'ordre : {etapes_str}\n"
                f"1. Encourage l'élève avec douceur 😊\n"
                f"2. Dis 'Rappelle-toi l'image ! 😊' et explique avec les VRAIS chiffres de l'exercice\n"
                f"3. Ne donne PAS la réponse directement. Pose une question pour guider : 'Essaie encore 🤔'\n"
                f"4. Attends la réponse de l'élève{_div_warning}]"
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

    # ── Supprimer les tentatives de décomposition verticale ──
    reply = re.sub(r'```[\s\S]*?```', '', reply)
    reply = re.sub(r'(\d+\s*\n\s*){2,}', '', reply)

    return reply.strip()

def post_traitement(reply, user_input, historique, langue):
    """Nettoie + corrige si GPT valide une réponse fausse."""
    reply = nettoyer_reponse(reply)

    verdict = verifier_reponse(user_input, historique)
    if verdict is None or verdict == 'correct' or verdict.startswith('presque'):
        return reply

    resultat_correct = verdict.split(':')[1]
    mots_fr = ['bravo', 'félicitations', 'bonne réponse', 'tu as trouvé', 'très bien !', 'super !']
    mots_ar = ['أحسنت', 'إجابة صحيحة', 'تهانينا', 'عمل ممتاز']
    gpt_faux = any(m in reply.lower() for m in mots_fr) or any(m in reply for m in mots_ar)

    if gpt_faux:
        # 1. On retire les encouragements inappropriés si la réponse est fausse
        reply_clean = re.sub(
            r'(🌟\s*)?(Bravo|Félicitations|Bonne réponse|Tu as trouvé|Très bien|Super|Excellent|Parfait|Correct|أحسنت|ممتاز|إجابة صحيحة|عمل ممتاز|C\'est courageux[^\n!]*[!.]?\s*)',
            '', reply, count=1, flags=re.IGNORECASE
        ).strip()
        
        # 2. On supprime aussi toute phrase qui contiendrait ", pas [chiffre]"
        reply_clean = re.sub(r',?\s*pas\s*\d+', '', reply_clean)
        
        # On retourne l'explication générée par GPT (déjà nettoyée) 
        # sans écraser avec une phrase fixe.
        return reply_clean
            
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
            f"En primaire, on retire toujours un petit nombre d'un plus grand. Les nombres négatifs, c'est une autre aventure ! \n\n"
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
    if len(msg) <= 1 and not re.search(r'\d', msg):
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
        # ── Addition ──────────────────────────────────────────────
        "addition_simple":       _fr("26_addition_simple_visuelle.png"),   # 3+2=5
        "addition_sans_retenue": _fr("01_addition_sans_retenue.png"),       # 23+14=37
        "addition_avec_retenue": _fr("02_addition_avec_retenue.png"),       # 27+15=42
        "addition_3_chiffres":   _fr("11_addition_3_chiffres.png"),         # 357+286=643
        # ── Soustraction ──────────────────────────────────────────
        "soustraction_simple":           _fr("27_soustraction_simple_visuelle.png"), # 5-2=3
        "soustraction_sans_retenue":     _fr("03_soustraction_sans_retenue.png"),    # 48-23=25
        "soustraction_2ch_1ch_emprunt":  _fr("04b_soustraction_2ch_1ch_emprunt.png"), # 13-7=6
        "soustraction_avec_retenue":     _fr("04_soustraction_avec_retenue.png"),    # 43-17=26
        "soustraction_3ch_1ch_emprunt":  _fr("04d_soustraction_3ch_1ch_emprunt.png"), # 124-8=116
        "soustraction_3ch_2ch_emprunt":  _fr("04c_soustraction_3ch_2ch_emprunt.png"), # 132-47=85
        "soustraction_3_chiffres":       _fr("12_soustraction_3_chiffres.png"),      # 503-247=256
        "soustraction_double_emprunt":   _fr("38_soustraction_double_emprunt.png"),  # 834-567=267
        # ── Multiplication ────────────────────────────────────────
        "tables_2_5_9":              _fr("09_tables_multiplication_2_5_9.png"),  # tables 2,5,9
        "tables_multiplication":     _fr("39_tables_multiplication.png"),        # tables 1→9
        "tables_1_3_4":              _fr("40_tables_multiplication_1_3_4.png"),  # tables 1,3,4
        "tables_6_7_8":              _fr("41_tables_multiplication_6_7_8.png"),  # tables 6,7,8
        "multiplication_simple":     _fr("05_multiplication_simple.png"),        # 34×6=204
        "multiplication_2_chiffres": _fr("06_multiplication_deux_chiffres.png"), # 24×13=312
        "multiplication_3_chiffres": _fr("29_multiplication_3_chiffres.png"),    # 245×36=8820
        "multiplication_10_100_1000":_fr("13_multiplication_10_100_1000.png"),   # 25×10=250
        # ── Division ──────────────────────────────────────────────
        "division_simple":           _fr("07_division_simple.png"),          # 84÷4=21
        "division_avec_reste":       _fr("08_division_avec_reste.png"),      # 47÷5=9r2
        "division_2_chiffres":       _fr("14_division_2_chiffres.png"),      # 156÷12=13
        # ── Concepts ──────────────────────────────────────────────
        "priorite_operations":  _fr("20_priorite_operations.png"),   # 2+3×4=14
        "operations_mixtes":    _fr("25_operations_mixtes.png"),     # 8-3+2=7
        "multiples_diviseurs":  _fr("30_multiples_diviseurs.png"),   # multiples de 3,5
    },
    "العربية": {
        # Addition
        "addition_simple":       _ar("26_ar_addition_simple_visuelle.png"),
        "addition_sans_retenue": _ar("01_ar_addition_sans_retenue.png"),
        "addition_avec_retenue": _ar("02_ar_addition_avec_retenue.png"),
        "addition_3_chiffres":   _ar("11_ar_addition_3_chiffres.png"),
        # Soustraction
        "soustraction_simple":           _ar("27_ar_soustraction_simple_visuelle.png"),
        "soustraction_sans_retenue":     _ar("03_ar_soustraction_sans_retenue.png"),
        "soustraction_2ch_1ch_emprunt":  _ar("04b_ar_soustraction_2ch_1ch_emprunt.png"),
        "soustraction_avec_retenue":     _ar("04_ar_soustraction_avec_retenue.png"),
        "soustraction_3ch_1ch_emprunt":  _ar("04d_ar_soustraction_3ch_1ch_emprunt.png"),
        "soustraction_3ch_2ch_emprunt":  _ar("04c_ar_soustraction_3ch_2ch_emprunt.png"),
        "soustraction_3_chiffres":       _ar("12_ar_soustraction_3_chiffres.png"),
        "soustraction_double_emprunt":   _ar("38_ar_soustraction_double_emprunt.png"),
        # ── Multiplication ────────────────────────────────────────
        "tables_2_5_9":              _ar("09_ar_tables_multiplication_2_5_9.png"),
        "tables_multiplication":     _ar("39_ar_tables_multiplication.png"),
        "tables_1_3_4":              _ar("40_ar_tables_multiplication_1_3_4.png"),
        "tables_6_7_8":              _ar("41_ar_tables_multiplication_6_7_8.png"),
        "multiplication_simple":     _ar("05_ar_multiplication_simple.png"),
        "multiplication_2_chiffres": _ar("06_ar_multiplication_deux_chiffres.png"),
        "multiplication_3_chiffres": _ar("29_ar_multiplication_3_chiffres.png"),
        "multiplication_10_100_1000":_ar("13_ar_multiplication_10_100_1000.png"),
        # ── Division ──────────────────────────────────────────────
        "division_simple":           _ar("07_ar_division_simple.png"),
        "division_avec_reste":       _ar("08_ar_division_avec_reste.png"),
        "division_2_chiffres":       _ar("14_ar_division_2_chiffres.png"),
        # ── Concepts ──────────────────────────────────────────────
        "priorite_operations":  _ar("20_ar_priorite_operations.png"),
        "operations_mixtes":    _ar("25_ar_operations_mixtes.png"),
        "multiples_diviseurs":  _ar("30_ar_multiples_diviseurs.png"),
    }
}
# Fallback : si image AR introuvable → image FR utilisée automatiquement
for k, v in IMAGES_MAP["Français"].items():
    ar_path = IMAGES_MAP["العربية"].get(k)
    if not ar_path or not os.path.exists(ar_path):
        IMAGES_MAP["العربية"][k] = v

# ============================================================
# EXPLICATIONS STATIQUES DES IMAGES
# ============================================================
EXPLICATIONS_IMAGES = {
    "addition_simple": {
        "Français": "Regarde l'image ! 😊 Elle montre 3 billes bleues + 2 billes bleues = 5 billes vertes. C'est ça l'addition : on met tout ensemble ! 💡 Astuce : mets le grand nombre dans ta tête et compte avec tes doigts !",
        "العربية": "انظر للصورة ! 😊 تُظهر 3 كرات زرقاء + 2 كرات زرقاء = 5 كرات خضراء. هذا هو الجمع : نضع الكل معاً ! 💡 نصيحة : ضع العدد الكبير في رأسك وعدّ بأصابعك !"
    },
    "addition_sans_retenue": {
        "Français": "Regarde l'image ! 😊 Les colonnes D (Dizaines) et U (Unités) en bleu t'aident à poser le calcul. On additionne colonne par colonne en commençant par les unités (à droite). Le résultat est en vert en bas.",
        "العربية": "انظر للصورة ! 😊 الأعمدة ع (عشرات) و آ (آحاد) بالأزرق تساعدك على ترتيب الحساب. نجمع عموداً بعمود بدءاً من الآحاد. النتيجة بالأخضر."
    },
    "addition_avec_retenue": {
        "Français": "Regarde l'image ! 😊 Tu vois le rond rouge 🔴 au-dessus de la colonne D ? C'est la retenue ! Quand les unités dépassent 9, on écrit le chiffre des unités et on retient 1 pour les dizaines.",
        "العربية": "انظر للصورة ! 😊 ترى الدائرة الحمراء 🔴 فوق عمود العشرات ؟ هذا هو الاحتفاظ ! عندما تتجاوز الآحاد 9، نكتب رقم الآحاد ونحتفظ بـ 1 للعشرات."
    },
    "addition_3_chiffres": {
        "Français": "Regarde l'image ! 😊 Trois colonnes : C (Centaines), D (Dizaines), U (Unités). Tu vois les deux ronds rouges 🔴 ? Ce sont les retenues. On additionne colonne par colonne de droite à gauche, et chaque fois que ça dépasse 9, on retient 1.",
        "العربية": "انظر للصورة ! 😊 ثلاثة أعمدة : م (مئات)، ع (عشرات)، آ (آحاد). ترى الدوائر الحمراء 🔴 ؟ هذا هو الاحتفاظ. نجمع من اليمين لليسار، وكلما تجاوز الرقم 9 نحتفظ بـ 1."
    },
    "soustraction_simple": {
        "Français": "Regarde l'image ! 😊 Elle montre 5 billes bleues, on enlève 2 billes (barrées en rouge), il reste 3 billes vertes. C'est ça la soustraction : on enlève ! 💡 Astuce : mets le grand nombre dans ta tête et compte à rebours !",
        "العربية": "انظر للصورة ! 😊 تُظهر 5 كرات زرقاء، نزيل 2 كرات (مشطوبة بالأحمر)، يبقى 3 كرات خضراء. هذا هو الطرح : ننزع ! 💡 نصيحة : ضع العدد الكبير في رأسك واعدّ للخلف !"
    },
    "soustraction_sans_retenue": {
        "Français": "Regarde l'image ! 😊 On pose le calcul verticalement. Le signe moins est en orange. On soustrait colonne par colonne en commençant par les unités. Le résultat est en vert.",
        "العربية": "انظر للصورة ! 😊 نرتب الحساب عمودياً. علامة الطرح بالبرتقالي. نطرح عموداً بعمود بدءاً من الآحاد. النتيجة بالأخضر."
    },
    "soustraction_avec_retenue": {
        "Français": "Regarde l'image ! 😊 Tu vois la flèche rouge et les chiffres barrés ? C'est l'emprunt ! Quand le chiffre du haut est plus petit que celui du bas, on emprunte 1 dizaine. Le chiffre des dizaines diminue de 1 et les unités augmentent de 10.",
        "العربية": "انظر للصورة ! 😊 ترى السهم الأحمر والأرقام المشطوبة ؟ هذا هو الاستلاف ! عندما يكون الرقم العلوي أصغر من السفلي، نستلف عشرة واحدة."
    },
    "soustraction_2ch_1ch_emprunt": {
        "Français": "Regarde l'image ! 😊 Tu vois la flèche rouge de D vers U ? On emprunte 1 dizaine car le chiffre des unités est trop petit. Le 1 des dizaines devient 0 et les unités passent à 13. Le résultat des dizaines est en gris (0) et les unités en vert.",
        "العربية": "انظر للصورة ! 😊 ترى السهم الأحمر من ع إلى آ ؟ نستلف عشرة لأن رقم الآحاد صغير جداً. النتيجة بالأخضر."
    },
    "soustraction_3ch_1ch_emprunt": {
        "Français": "Regarde l'image ! 😊 Trois colonnes C, D, U. La flèche rouge montre l'emprunt des dizaines vers les unités. Le chiffre des unités barré est remplacé par un nombre plus grand (avec 10 de plus). Les centaines restent inchangées.",
        "العربية": "انظر للصورة ! 😊 ثلاثة أعمدة م، ع، آ. السهم الأحمر يُظهر الاستلاف من العشرات للآحاد. المئات لا تتغير."
    },
    "soustraction_3ch_2ch_emprunt": {
        "Français": "Regarde l'image ! 😊 Tu vois les flèches rouges →12 ? C'est le double emprunt ! Quand les unités ET les dizaines sont trop petites, on emprunte en cascade : des centaines vers les dizaines, puis des dizaines vers les unités.",
        "العربية": "انظر للصورة ! 😊 ترى الأسهم الحمراء →12 ؟ هذا استلاف مزدوج ! عندما تكون الآحاد والعشرات صغيرتين، نستلف بالتسلسل."
    },
    "soustraction_double_emprunt": {
        "Français": "Regarde l'image ! 😊 Tu vois les chiffres barrés en rouge dans les trois colonnes C, D, U ? C'est le double emprunt ! On emprunte des centaines vers les dizaines (le 8 devient 7, le 3 devient 12), puis des dizaines vers les unités (le 12 reste 12, le 4 devient 14).",
        "العربية": "انظر للصورة ! 😊 ترى الأرقام المشطوبة بالأحمر في الأعمدة الثلاثة ؟ هذا استلاف مزدوج ! نستلف من المئات للعشرات ثم من العشرات للآحاد."
    },
    "soustraction_3_chiffres": {
        "Français": "Regarde l'image ! 😊 Tu vois les flèches rouges →→ ? C'est le double emprunt en cascade ! Les unités 3 est trop petit, les dizaines valent 0, donc on emprunte d'abord aux centaines. Le 5 devient 4, le 0 devient 9, le 3 devient 13.",
        "العربية": "انظر للصورة ! 😊 ترى الأسهم الحمراء →→ ؟ هذا استلاف مزدوج متسلسل ! الآحاد صغيرة والعشرات تساوي 0، لذلك نستلف أولاً من المئات."
    },
    "multiplication_simple": {
        "Français": "Regarde l'image ! 😊 Les colonnes C, D, U en bleu. Le signe × est en violet. Tu vois le rond rouge 🔴 avec le chiffre 2 ? C'est la retenue ! On multiplie colonne par colonne en commençant par les unités.",
        "العربية": "انظر للصورة ! 😊 الأعمدة م، ع، آ بالأزرق. علامة × بالبنفسجي. ترى الدائرة الحمراء 🔴 ؟ هذا هو الاحتفاظ ! نضرب عموداً بعمود بدءاً من الآحاد."
    },
    "multiplication_2_chiffres": {
        "Français": "Regarde l'image ! 😊 On fait DEUX lignes de multiplication. Ligne 1 (en vert) : on multiplie par les unités du deuxième nombre. Ligne 2 : on multiplie par les dizaines et on décale d'un cran (le point orange montre le décalage). Puis on additionne les deux lignes !",
        "العربية": "انظر للصورة ! 😊 نقوم بخطين من الضرب. الخط 1 (بالأخضر) : نضرب في آحاد العدد الثاني. الخط 2 : نضرب في العشرات ونزيح خانة (النقطة البرتقالية تُظهر الإزاحة). ثم نجمع الخطين !"
    },
    "multiplication_3_chiffres": {
        "Français": "Regarde l'image ! 😊 C'est la même méthode que la multiplication à 2 chiffres mais avec 3 chiffres en haut. Tu vois les ronds rouges 🔴 ? Ce sont les retenues. Ligne 1 : on multiplie 245 par les unités (6). Ligne 2 : on multiplie 245 par les dizaines (3) avec décalage (point orange). Puis on additionne !",
        "العربية": "انظر للصورة ! 😊 نفس الطريقة لكن بثلاثة أرقام. ترى الدوائر الحمراء 🔴 ؟ الخط 1 : نضرب 245 في الآحاد (6). الخط 2 : نضرب 245 في العشرات (3) مع الإزاحة. ثم نجمع !"
    },
    "division_simple": {
        "Français": "Regarde l'image ! 😊 La division simple : le diviseur rentre un nombre exact de fois dans le dividende, sans reste. Le quotient est en vert à droite.",
        "العربية": "انظر للصورة ! 😊 القسمة المطولة : نقسم خطوة بخطوة. أولاً نبحث كم مرة يدخل المقسوم عليه في الرقم الأول، نطرح (بالأحمر)، ثم ننزل الرقم التالي (السهم الأحمر). الحاصل بالأخضر."
    },
    "division_avec_reste": {
        "Français": "Regarde l'image ! 😊 Comme la division simple, mais cette fois il reste quelque chose ! Tu vois le ← reste ? C'est ce qui ne peut plus être partagé. Le quotient est en vert à droite.",
        "العربية": "انظر للصورة ! 😊 مثل القسمة البسيطة، لكن هذه المرة يبقى شيء ! ترى ← الباقي ؟ هذا ما لا يمكن تقسيمه. الحاصل بالأخضر."
    },
    "division_2_chiffres": {
        "Français": "Regarde l'image ! 😊 On divise par un nombre à 2 chiffres. D'abord on cherche combien de fois 12 rentre dans 15, on soustrait (en rouge). Puis on descend le chiffre suivant (← abaisser) et on recommence. Le quotient est en vert.",
        "العربية": "انظر للصورة ! 😊 نقسم على عدد من رقمين. أولاً نبحث كم مرة يدخل 12 في 15، نطرح (بالأحمر). ثم ننزل الرقم التالي (← إنزال) ونكرر. الحاصل بالأخضر."
    },
    "tables_multiplication": {
        "Français": "Regarde l'image ! 😊 Toutes les 9 tables de multiplication de 1 à 9. Les astuces en couleur en bas t'aident à les retenir !",
        "العربية": "انظر للصورة ! 😊 كل جداول الضرب التسعة من 1 إلى 9. الحيل بالألوان في الأسفل تساعدك على حفظها !"
    },
    "tables_2_5_9": {
        "Français": "Regarde l'image ! 😊 Les tables faciles : ×2 c'est doubler, ×5 le résultat finit par 0 ou 5, ×9 les chiffres du résultat font toujours 9 !",
        "العربية": "انظر للصورة ! 😊 الجداول السهلة : ×2 نضاعف، ×5 النتيجة تنتهي بـ 0 أو 5، ×9 أرقام النتيجة تساوي دائماً 9 !"
    },
    "tables_1_3_4": {
        "Français": "Regarde l'image ! 😊 Les tables de 1, 3 et 4. Astuces : ×1 le résultat est toujours le même nombre, ×3 on ajoute 3 fois, ×4 on double deux fois !",
        "العربية": "انظر للصورة ! 😊 جداول 1 و 3 و 4. حيل : ×1 النتيجة دائماً نفس العدد، ×3 نجمع 3 مرات، ×4 نضاعف مرتين !"
    },
    "tables_6_7_8": {
        "Français": "Regarde l'image ! 😊 Les tables difficiles : 6, 7 et 8. La plus dure à retenir : 7 × 8 = 56 → les chiffres se suivent : 5, 6, 7, 8 !",
        "العربية": "انظر للصورة ! 😊 الجداول الصعبة : 6 و 7 و 8. الأصعب : 7 × 8 = 56 ← الأرقام متتالية : 5، 6، 7، 8 !"
    },
    "multiplication_10_100_1000": {
        "Français": "Regarde l'image ! 😊 L'astuce des zéros : ×10 on ajoute 1 zéro, ×100 on ajoute 2 zéros, ×1000 on ajoute 3 zéros !",
        "العربية": "انظر للصورة ! 😊 حيلة الأصفار : ×10 نضيف صفراً واحداً، ×100 نضيف صفرين، ×1000 نضيف 3 أصفار !"
    },
    "priorite_operations": {
        "Français": "Regarde l'image ! 😊 La règle d'or : × et ÷ se calculent EN PREMIER, puis + et −. Par exemple 2 + 3 × 4 = 14 (pas 20 !) car on fait d'abord 3 × 4 = 12.",
        "العربية": "انظر للصورة ! 😊 القاعدة الذهبية : × و ÷ تُحسب أولاً، ثم + و −. مثلاً 2 + 3 × 4 = 14 (وليس 20 !) لأننا نحسب أولاً 3 × 4 = 12."
    },
    "operations_mixtes": {
        "Français": "Regarde l'image ! 😊 Quand il y a + et − ensemble, on calcule de gauche à droite. Le résultat est toujours positif en primaire !",
        "العربية": "انظر للصورة ! 😊 عندما يكون + و − معاً، نحسب من اليسار لليمين. النتيجة دائماً إيجابية في الابتدائي !"
    }
}
# ============================================================
# MENU DE CHOIX PAR OPÉRATION ET NIVEAU
# ============================================================
# Quand l'élève dit "l'addition", le tuteur propose un menu
# filtré par niveau. L'élève tape le numéro → image + exercice cohérents.

CHOIX_OPERATIONS = {
    "addition": {
        1: [
            {"label_fr": "Addition simple (5 + 3)", "label_ar": "جمع بسيط (5 + 3)", "image": "addition_simple",
             "consigne": "addition simple à 1 chiffre, nombres entre 2 et 9"},
        ],
        2: [
            {"label_fr": "Addition sans retenue (23 + 14)", "label_ar": "جمع بدون احتفاظ (23 + 14)", "image": "addition_sans_retenue",
             "consigne": "addition à 2 chiffres SANS retenue, nombres entre 10 et 49"},
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue, nombres entre 15 et 89"},
        ],
        3: [
            {"label_fr": "Addition sans retenue (23 + 14)", "label_ar": "جمع بدون احتفاظ (23 + 14)", "image": "addition_sans_retenue",
             "consigne": "addition à 2 chiffres SANS retenue, nombres entre 10 et 49"},
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue, nombres entre 15 et 89"},
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues, nombres entre 100 et 999"},
        ],
        4: [
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue, nombres entre 15 et 89"},
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues"},
        ],
        5: [
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues"},
        ],
        6: [
            {"label_fr": "Addition à 3 chiffres (357 + 286)", "label_ar": "جمع بثلاثة أرقام (357 + 286)", "image": "addition_3_chiffres",
             "consigne": "addition à 3 chiffres avec retenues, nombres entre 100 et 999"},
            {"label_fr": "Addition avec retenue (27 + 35)", "label_ar": "جمع مع الاحتفاظ (27 + 35)", "image": "addition_avec_retenue",
             "consigne": "addition à 2 chiffres AVEC retenue, nombres entre 15 et 89"},
        ],
    },
    "soustraction": {
        1: [
            {"label_fr": "Soustraction simple (7 - 3)", "label_ar": "طرح بسيط (7 - 3)", "image": "soustraction_simple",
             "consigne": "soustraction simple à 1 chiffre, nombres entre 2 et 9, le premier PLUS GRAND que le deuxième"},
        ],
        2: [
            {"label_fr": "Soustraction sans emprunt (48 - 23)", "label_ar": "طرح بدون استلاف (48 - 23)", "image": "soustraction_sans_retenue",
             "consigne": "soustraction à 2 chiffres SANS emprunt, nombres entre 20 et 89, le premier PLUS GRAND que le deuxième"},
            {"label_fr": "Soustraction avec emprunt (43 - 17)", "label_ar": "طرح مع الاستلاف (43 - 17)", "image": "soustraction_avec_retenue",
             "consigne": "soustraction à 2 chiffres AVEC emprunt, nombres entre 20 et 89, le premier PLUS GRAND que le deuxième"},
            {"label_fr": "Soustraction 2 chiffres − 1 chiffre avec emprunt (32 − 7)", "label_ar": "طرح رقمين − رقم مع الاستلاف (32 − 7)", "image": "soustraction_2ch_1ch_emprunt",
             "consigne": "soustraction 2 chiffres − 1 chiffre AVEC emprunt, le premier entre 20 et 50, le deuxième entre 5 et 9"},
        ],
        3: [
            {"label_fr": "Soustraction avec emprunt (43 - 17)", "label_ar": "طرح مع الاستلاف (43 - 17)", "image": "soustraction_avec_retenue",
             "consigne": "soustraction à 2 chiffres AVEC emprunt, nombres entre 20 et 89, le premier PLUS GRAND que le deuxième"},
            {"label_fr": "Soustraction à 3 chiffres (834 - 567)", "label_ar": "طرح بثلاثة أرقام (834 - 567)", "image": "soustraction_double_emprunt",
             "consigne": "soustraction à 3 chiffres avec double emprunt, nombres entre 100 et 999"},
            {"label_fr": "Soustraction 3 chiffres − 1 chiffre (125 − 8)", "label_ar": "طرح ثلاثة أرقام − رقم (125 − 8)", "image": "soustraction_3ch_1ch_emprunt",
             "consigne": "soustraction 3 chiffres − 1 chiffre avec emprunt, le premier entre 100 et 300"},
            {"label_fr": "Soustraction 3 chiffres − 2 chiffres (345 − 67)", "label_ar": "طرح ثلاثة أرقام − رقمين (345 − 67)", "image": "soustraction_3ch_2ch_emprunt",
             "consigne": "soustraction 3 chiffres − 2 chiffres avec emprunt, le premier entre 100 et 999"},
        ],
        4: [
            {"label_fr": "Soustraction à 3 chiffres (503 - 247)", "label_ar": "طرح بثلاثة أرقام (503 - 247)", "image": "soustraction_3_chiffres",
             "consigne": "soustraction à 3 chiffres avec emprunts"},
            {"label_fr": "Soustraction avec emprunt (72 - 48)", "label_ar": "طرح مع الاستلاف (72 - 48)", "image": "soustraction_avec_retenue",
             "consigne": "soustraction à 2 chiffres AVEC emprunt, nombres entre 20 et 89, le premier PLUS GRAND que le deuxième"},
            {"label_fr": "Soustraction à 3 chiffres (503 - 247)", "label_ar": "طرح بثلاثة أرقام (503 - 247)", "image": "soustraction_3_chiffres",
             "consigne": "soustraction à 3 chiffres avec emprunts"},
        ],
        5: [
            {"label_fr": "Soustraction à 3 chiffres (503 - 247)", "label_ar": "طرح بثلاثة أرقام (503 - 247)", "image": "soustraction_3_chiffres",
             "consigne": "soustraction à 3 chiffres avec emprunts, nombres entre 100 et 999"},
            {"label_fr": "Soustraction avec double emprunt (400 - 156)", "label_ar": "طرح مع استلاف مزدوج (400 - 156)", "image": "soustraction_double_emprunt",
             "consigne": "soustraction à 3 chiffres avec double emprunt, nombres entre 100 et 999"},
        ],
        6: [
            {"label_fr": "Soustraction à 3 chiffres (503 - 247)", "label_ar": "طرح بثلاثة أرقام (503 - 247)", "image": "soustraction_3_chiffres",
             "consigne": "soustraction à 3 chiffres avec emprunts, nombres entre 100 et 999"},
            {"label_fr": "Soustraction avec double emprunt (400 - 156)", "label_ar": "طرح مع استلاف مزدوج (400 - 156)", "image": "soustraction_double_emprunt",
             "consigne": "soustraction à 3 chiffres avec double emprunt, nombres entre 100 et 999"},
        ],
    },
    "multiplication": {
        2: [
            {"label_fr": "Les 9 tables de multiplication (1 à 9)", "label_ar": "جداول الضرب التسعة (1 إلى 9)", "image": "tables_multiplication",
             "consigne": "tables de multiplication de 1 à 9, produit simple entre 1×1 et 9×10"},
            {"label_fr": "Multiplication simple (3 × 4)", "label_ar": "الضرب البسيط (3 × 4)", "image": "multiplication_simple",
             "consigne": "multiplication simple 1 chiffre × 1 chiffre, nombres entre 2 et 9, résultat ≤ 50"},
            {"label_fr": "Tables faciles (2, 5 et 9)", "label_ar": "جداول سهلة (2, 5 و 9)", "image": "tables_2_5_9",
             "consigne": "tables de multiplication 2, 5 et 9 uniquement"},
            {"label_fr": "Tables moyennes (1, 3 et 4)", "label_ar": "جداول متوسطة (1, 3 و 4)", "image": "tables_1_3_4",
             "consigne": "tables de multiplication 1, 3 et 4 uniquement"},
        ],
        3: [
            {"label_fr": "Les 9 tables de multiplication", "label_ar": "جداول الضرب التسعة", "image": "tables_multiplication",
             "consigne": "tables de multiplication de 1 à 9"},
            {"label_fr": "Tables difficiles (6, 7 et 8)", "label_ar": "جداول صعبة (6, 7 و 8)", "image": "tables_6_7_8",
             "consigne": "tables de multiplication 6, 7 et 8 uniquement"},
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
            {"label_fr": "Multiplication à 3 chiffres (245 × 7)", "label_ar": "الضرب بثلاثة أرقام (245 × 7)", "image": "multiplication_3_chiffres",
             "consigne": "multiplication 3 chiffres × 1 chiffre avec retenues"},
        ],
        6: [
            {"label_fr": "Multiplication à 2 chiffres (24 × 13)", "label_ar": "الضرب بعددين (24 × 13)", "image": "multiplication_2_chiffres",
             "consigne": "multiplication 2 chiffres × 2 chiffres, deux lignes + addition"},
            {"label_fr": "Multiplication à 3 chiffres (245 × 7)", "label_ar": "الضرب بثلاثة أرقام (245 × 7)", "image": "multiplication_3_chiffres",
             "consigne": "multiplication 3 chiffres × 1 chiffre avec retenues"},
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
        ],
        6: [

            {"label_fr": "Division par 2 chiffres (156 ÷ 12)", "label_ar": "قسمة بعددين (156 ÷ 12)", "image": "division_2_chiffres",
             "consigne": "division diviseur 2 chiffres"},
            {"label_fr": "Division avec reste (47 ÷ 5)", "label_ar": "قسمة مع الباقي (47 ÷ 5)", "image": "division_avec_reste",
             "consigne": "division avec reste, diviseur 1 chiffre"},
        ],
    },

}
def detecter_operation_demandee(message):
    """
    Détecte quelle opération l'élève demande via GPT (few-shot).
    GPT comprend le langage naturel, les fautes, les synonymes, l'arabe.
    Fallback rapide par mots-clés si GPT échoue ou dit 'autre'.
    """
    msg = (message or "").strip()
    if not msg or len(msg) < 3:
        return None

    # ── Appel GPT classifier avec exemples (few-shot) ──
    try:
        classification_prompt = (
            "Tu dois identifier l'opération mathématique dans le message de l'élève.\n"
            "Même s'il y a des fautes d'orthographe ou qu'il écrit juste un mot, trouve l'opération.\n\n"
            "Exemples :\n"
            '"partager 45 bonbons" → division\n'
            '"3 groupes de 4 pommes" → multiplication\n'
            '"j ai 15 billes, j en perds 7" → soustraction\n'
            '"addition" → addition\n'
            '"la soustrcation" (faute) → soustraction\n'
            '"multiplicatoin" (faute) → multiplication\n'
            '"je veux faire des divisions" → division\n'
            '"la géographie" → autre\n\n'
            f'Message de l\'élève : "{msg}"\n\n'
            "Réponds avec UN seul mot parmi : "
            "addition, soustraction, multiplication, division, autre"
        )
        result = llm_classifier.invoke([HumanMessage(content=classification_prompt)])
        op = result.content.strip().lower().split()[0].rstrip('.,!?')
        if op in ["addition", "soustraction", "multiplication", "division"]:
            return op
            
        # 🔥 LA CORRECTION EST ICI 🔥
        # On a SUPPRIMÉ la ligne `if op == "autre": return None` !
        # Si le mini-LLM échoue, le code continue vers les mots-clés de secours.
        
    except Exception:
        pass

    # ── Fallback mots-clés (si GPT dit 'autre' ou est indisponible) ──
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
    return None

def detecter_calcul_direct(message):
    """
    Détecte si l'élève a écrit un calcul direct (NOMBRES ENTIERS UNIQUEMENT).
    Règle pour "/" : si a < b (ex: 1/2), c'est une fraction → ignoré.
    """
    m = (message or "").strip()
    m_norm = m.replace('×','*').replace('÷','/').replace('−','-')

    match = re.fullmatch(r'(\d+)\s*([+\-×*x÷/])\s*(\d+)', m)
    if not match:
        match = re.fullmatch(r'(\d+)\s*([+\-*/])\s*(\d+)', m_norm)
    if not match:
        match = re.search(r'(\d+)\s*([+\-−×*x÷/])\s*(\d+)', m)
    if not match:
        return None

    a = match.group(1)
    op = match.group(2)
    b = match.group(3)

    # Règle fraction vs division pour "/"
    if op == '/':
        if int(a) < int(b):
            # numérateur < dénominateur → c'est une fraction → on l'ignore
            return None

    expr_display = m.replace('/', ' ÷ ').replace('*', ' × ')
    op_norm = '÷' if op == '/' else ('×' if op in ['*','x'] else op)

    # On retourne des INT, plus de FLOAT !
    return (expr_display.strip(), int(a), op_norm, int(b))

def extraire_calcul_dans_phrase(message):
    """
    Détecte si le message est une demande d'explication pour un calcul embarqué.
    (NOMBRES ENTIERS UNIQUEMENT).
    """
    match = re.search(r'(\d+)\s*([+\-−×*x÷/])\s*(\d+)', message)
    if not match:
        return None  

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
        mots = ["montre","affiche","comment","explique","aide","fais","résoudre",
                "résous","calcule","ارني","كيف","أرني","وضّح","افعل","حل","ساعد"]
        if not any(m in message.lower() for m in mots):
            return None

    a = match.group(1)
    op = match.group(2)
    b = match.group(3)

    if op == '/':
        if int(a) < int(b):
            return None # Ignore les fractions

    expr_display = f"{a} {op} {b}"
    op_norm = (
        '÷' if op in ['/', '÷'] else
        '×' if op in ['*', 'x', '×'] else
        '-' if op == '−' else op
    )
    return (expr_display.strip(), int(a), op_norm, int(b))

def get_image_for_calcul(a, op, b, niveau, langue):
    """
    Détermine l'image + consigne pour un calcul direct a op b.
    La consigne inclut l'exemple RÉEL de l'image pour que GPT
    explique avec les mêmes chiffres que l'image.
    """
    imgs = IMAGES_MAP.get(langue, IMAGES_MAP["Français"])
    
    ia, ib = int(a), int(b)
    nb_ch_a = len(str(abs(ia)))
    nb_ch_b = len(str(abs(ib)))

    # ── 1. ADDITION ──
    if op in ['+']:
        u_a = abs(ia) % 10
        u_b = abs(ib) % 10
        has_carry = (u_a + u_b) >= 10
        
        if nb_ch_a >= 3 or nb_ch_b >= 3:
            return imgs.get("addition_3_chiffres"), "addition à 3 chiffres, exemple image : 357 + 286 = 643"
        
        if nb_ch_a <= 1 and nb_ch_b <= 1:
            return imgs.get("addition_simple"), "addition simple, exemple image : 5 + 3 = 8"
            
        if has_carry:
            return imgs.get("addition_avec_retenue"), "addition avec retenue, exemple image : 27 + 15 = 42"
        else:
            return imgs.get("addition_sans_retenue"), "addition sans retenue, exemple image : 23 + 14 = 37"

    # ── 2. SOUSTRACTION ──
    if op in ['-', '−']:
        # Correction pour garantir un résultat positif (cycle primaire)
        if ia < ib:
            ia, ib = ib, ia
        
        u_a = abs(ia) % 10
        u_b = abs(ib) % 10
        d_a = (abs(ia) // 10) % 10
        d_b = (abs(ib) // 10) % 10
        
        needs_borrow_unites = u_a < u_b
        needs_borrow_dizaines = d_a < d_b or (d_a == d_b and needs_borrow_unites)
        
        # SOUSTRACTION 3 CHIFFRES
        if nb_ch_a >= 3 and nb_ch_b >= 3:
            if needs_borrow_unites and needs_borrow_dizaines:
                return imgs.get("soustraction_double_emprunt"), "soustraction avec double emprunt, exemple : 834 − 567 = 267"
            return imgs.get("soustraction_3_chiffres"), "soustraction 3ch, exemple : 503 − 247 = 256"
            
        if nb_ch_a >= 3 and nb_ch_b == 2:
            if needs_borrow_unites:
                return imgs.get("soustraction_3ch_2ch_emprunt"), "soustraction 3ch−2ch avec emprunt, exemple : 132 − 47 = 85"
            return imgs.get("soustraction_3_chiffres"), "soustraction 3ch, exemple : 503 − 247 = 256"
            
        if nb_ch_a >= 3 and nb_ch_b == 1:
            if needs_borrow_unites:
                return imgs.get("soustraction_3ch_1ch_emprunt"), "soustraction 3ch−1ch avec emprunt, exemple : 124 − 8 = 116"
            return imgs.get("soustraction_sans_retenue"), "soustraction sans emprunt, exemple : 48 − 23 = 25"
            
        # SOUSTRACTION 2 CHIFFRES
        if nb_ch_a == 2 and nb_ch_b == 2:
            if needs_borrow_unites:
                return imgs.get("soustraction_avec_retenue"), "soustraction 2ch avec emprunt, exemple : 43 − 17 = 26"
            return imgs.get("soustraction_sans_retenue"), "soustraction sans emprunt, exemple : 48 − 23 = 25"
                
        if nb_ch_a == 2 and nb_ch_b == 1:
            if needs_borrow_unites:
                return imgs.get("soustraction_2ch_1ch_emprunt"), "soustraction 2ch−1ch avec emprunt, exemple : 13 − 7 = 6"
            return imgs.get("soustraction_simple"), "soustraction simple, exemple : 7 − 3 = 4"
                
        # SOUSTRACTION SIMPLE (1 chiffre)
        return imgs.get("soustraction_simple"), "soustraction simple, exemple : 5 − 2 = 3"

    # ── 3. MULTIPLICATION ──
    if op in ['×', '*', 'x']:
        # Multiplication par 10, 100, 1000 (Image 13)
        if ia in [10, 100, 1000] or ib in [10, 100, 1000]:
            return imgs.get("multiplication_10_100_1000"), "multiplication par 10, 100, 1000, exemple : 25 × 10 = 250"
            
        if nb_ch_a >= 3 or nb_ch_b >= 3:
            return imgs.get("multiplication_3_chiffres"), "multiplication 3 chiffres, exemple : 245 × 36 = 8820"
            
        if nb_ch_a == 2 and nb_ch_b == 2:
            return imgs.get("multiplication_2_chiffres"), "multiplication 2ch×2ch, exemple : 24 × 13 = 312"
            
        if (nb_ch_a == 2 and nb_ch_b == 1) or (nb_ch_a == 1 and nb_ch_b == 2):
            return imgs.get("multiplication_simple"), "multiplication 2ch×1ch, exemple : 34 × 6 = 204"
            
        # Tables de multiplication (Images 09, 39, 40, 41)
        if nb_ch_a <= 1 and nb_ch_b <= 1:
            if ia in [6, 7, 8] or ib in [6, 7, 8]:
                return imgs.get("tables_6_7_8"), "tables de 6, 7 et 8"
            elif ia in [2, 5, 9] or ib in [2, 5, 9]:
                return imgs.get("tables_2_5_9"), "tables de 2, 5 et 9"
            elif ia in [1, 3, 4] or ib in [1, 3, 4]:
                return imgs.get("tables_1_3_4"), "tables de 1, 3 et 4"
            else:
                return imgs.get("tables_multiplication"), "tables de 1 à 9"

    # ── 4. DIVISION ──
    if op in ['÷', '/']:
        if ib == 0: 
            return None, None # Sécurité Anti-Crash
            
        if ib >= 10:
            return imgs.get("division_2_chiffres"), "division diviseur 2ch, exemple image : 156 ÷ 12 = 13"
            
        if ia % ib == 0:
            return imgs.get("division_simple"), "division simple, exemple image : 84 ÷ 4 = 21"
        else:
            return imgs.get("division_avec_reste"), "division avec reste, exemple image : 47 ÷ 5 = 9 reste 2"

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

    # Fallback regex : prendre les nombres les plus pertinents (ENTIERS UNIQUEMENT)
    import re
    nombres = re.findall(r'\d+', message) # ❌ Plus de recherche de virgules
    
    if len(nombres) >= 2:
        # Pour division/soustraction : le plus grand divisé par le dernier
        if operation in ["division", "soustraction"]:
            a = max(nombres, key=lambda x: int(x)) # ❌ int() au lieu de float()
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
    Détecte si le message de l'élève est un problème énoncé à résoudre.
    NOUVELLE LOGIQUE : S'il y a du texte ET au moins DEUX nombres, c'est un problème !
    """
    msg = (message or "").lower().strip()

    # ❌ import re supprimé ici (déjà fait au début du fichier)

    # 1. On cherche tous les nombres présents dans le message
    nombres = re.findall(r'\d+', msg)
    has_multiple_numbers = len(nombres) >= 2
    
    # 2. On vérifie s'il y a du texte (lettres françaises ou arabes)
    has_letters = any(c.isalpha() for c in msg) or any(0x0600 <= ord(c) <= 0x06FF for c in msg)

    # 3. On vérifie que ce n'est pas juste un calcul tapé directement (Nombres entiers uniquement)
    is_direct_calc = bool(re.search(r'^\s*\d+\s*[+\-×÷*/x]\s*\d+\s*$', msg))

    # Verdict : Si on a au moins 2 nombres + du texte + pas de calcul direct = PROBLÈME
    return has_multiple_numbers and has_letters and not is_direct_calc

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
                    "multiplication": "de multiplication", "division": "de division"}
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
    msg = (message or "").lower()
    images = IMAGES_MAP.get(langue, IMAGES_MAP["Français"])

    demande_apprentissage = any(mot in msg for mot in [
        "apprendre", "expliquer", "comment", "c'est quoi", "montre", "aide", "comprends pas", "je veux",
        "تعلم", "اشرح", "كيف", "ساعد", "لم أفهم", "أريد",
        "addition", "soustraction", "multiplication", "division", "table", "double", "moitié", "priorité",
        "numération", "multiple", "diviseur",
        "الجمع", "الطرح", "الضرب", "القسمة", "جدول", "الضعف", "النصف", "أولوية", "ترقيم"
    ])

    if not demande_apprentissage:
        return None

    niv_num = int(str(niveau).replace("CE", "")) if niveau and niveau[0:2] == "CE" else 3

    if any(mot in msg for mot in ["addition", "جمع"]):
        # 1. Priorité aux 3 chiffres d'abord !
        if any(mot in msg for mot in ["3 chiffres", "trois", "centaine", "ثلاث", "مئ"]):
            return images.get("addition_3_chiffres")
        
        # 2. Ensuite les retenues
        if any(mot in msg for mot in ["retenue", "احتفاظ"]):
            return images.get("addition_avec_retenue")
            
        # 3. Le reste
        if niv_num <= 1: return images.get("addition_simple")
        return images.get("addition_sans_retenue")

    if any(mot in msg for mot in ["soustraction", "طرح"]):
        if niv_num <= 1: return images.get("soustraction_simple")
        if any(mot in msg for mot in ["double emprunt", "استلافين"]): return images.get("soustraction_double_emprunt")
        if any(mot in msg for mot in ["3 chiffres", "مئ"]): return images.get("soustraction_3_chiffres")
        if any(mot in msg for mot in ["emprunt", "استلاف"]): return images.get("soustraction_avec_retenue")
        return images.get("soustraction_sans_retenue")

    if any(mot in msg for mot in ["multiplication", "ضرب"]):
        if any(mot in msg for mot in ["table", "جدول"]): return images.get("tables_multiplication")
        if any(mot in msg for mot in ["10", "100", "1000"]): return images.get("multiplication_10_100_1000")
        if niv_num <= 3: return images.get("multiplication_simple")
        if niv_num == 4: return images.get("multiplication_2_chiffres")
        return images.get("multiplication_3_chiffres")

    if any(mot in msg for mot in ["division", "قسمة"]):
        if niv_num <= 3: return images.get("division_simple")
        return images.get("division_2_chiffres")

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
        return images.get("addition_sans_retenue")

    # --- Soustraction ---
    if any(mot in msg for mot in ["soustraction", "soustraire", "enlever", "retirer", "الطرح", "يطرح"]):
        if niv_num <= 1:
            return images.get("soustraction_simple")
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
            return images.get("soustraction_3_chiffres")
        return images.get("soustraction_sans_retenue")

# --- Multiplication ---
    if any(mot in msg for mot in ["multiplication", "multiplie", "fois", "الضرب", "يضرب", "×"]):
        if any(mot in msg for mot in ["table", "جدول"]):
            return images.get("tables_multiplication")
        if any(mot in msg for mot in ["10", "100", "1000"]):
            return images.get("multiplication_10_100_1000")
        
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
        if niv_num <= 3:
            return images.get("division_simple")
        elif niv_num == 4:
            return images.get("division_2_chiffres")
        elif niv_num >= 5:
            return images.get("division_2_chiffres")
        return images.get("division_simple")
    
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
                        "Pour addition → 'Tu veux l'addition simple ou l'addition avec retenue ? 😊' "
                        "Pour multiplication → 'Tu veux les tables de multiplication ou la multiplication posée ? 😊' "
                        "Pour soustraction → 'Tu veux la soustraction simple ou la soustraction avec emprunt ? 😊' "
                        "Adapte la question au niveau de l'élève. Réponse TRÈS courte, 1-2 lignes max.]",
            "العربية": "[تعليمات النظام : التلميذ طرح سؤالاً عاماً عن عملية حسابية. "
                       "اطرح سؤالاً واحداً قصيراً وطبيعياً للتوضيح (بدون قائمة مرقمة !). "
                       "أمثلة : "
                       "للجمع : 'تريد الجمع البسيط أم الجمع مع الاحتفاظ ؟ 😊' "
                       "للضرب : 'تريد جداول الضرب أم الضرب المطول ؟ 😊' "
                       "للطرح : 'تريد الطرح البسيط أم الطرح مع الاستلاف ؟ 😊' "
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
                        "❌ NE DONNE JAMAIS la bonne réponse de l'exercice en cours. "
                        "❌ PAS de markdown gras **réponse**. "
                        "✅ Applique les 4 TEMPS dans cet ordre STRICT : "
                        "TEMPS 1 : Encouragement ('👏 C'est courageux !') "
                        "TEMPS 2 : Modelage — ❌ INTERDIT d'utiliser les chiffres de l'exercice de l'élève. "
                        "Invente un calcul DIFFÉRENT avec des nombres proches (même opération, même difficulté) et résous-le ENTIÈREMENT avec le résultat final. "
                        "Exemple : si l'élève bloque sur 126-29, tu résous 143-56=87 devant lui, PAS 126-29. "
                        "TEMPS 3 : Transfert (Demande-lui de résoudre SON calcul original : 'À toi de jouer avec tes chiffres...') "
                        "TEMPS 4 : ARRÊTE-TOI. N'écris plus rien. "
                        "⚠️ AVERTISSEMENT : N'utilise JAMAIS les mots 'Bravo', 'Juste', 'Correct', 'Exact' ou 'Parfait' si l'élève s'est trompé !]",
            "العربية": "[تعليمات النظام : الإجابة خاطئة. "
                       "قواعد مطلقة : "
                       "❌ لا تعطِ الإجابة الصحيحة لتمرين التلميذ أبداً. "
                       "✅ طبق المراحل الأربع بهذا الترتيب الصارم : "
                       "المرحلة 1 : تشجيع ('👏 محاولة جيدة !') "
                       "المرحلة 2 : نمذجة — ❌ ممنوع استخدام أرقام تمرين التلميذ. "
                        "ابتكر حساباً مختلفاً بأرقام قريبة (نفس العملية، نفس الصعوبة) وقم بحله بالكامل مع النتيجة النهائية. "
                        "مثال : إذا كان التلميذ عالقاً في 126-29، تحل أنت 143-56=87 أمامه، وليس 126-29. "
                       "المرحلة 3 : تطبيق (اطلب منه حل عمليته الأصلية : 'الآن دورك مع أرقامك...') "
                       "المرحلة 4 : توقف. لا تكتب شيئاً آخر. "
                       "⚠️ تحذير صارم : لا تستخدم أبداً كلمات مثل 'أحسنت'، 'صحيح'، 'ممتاز' أو 'رائع' إذا أخطأ التلميذ !]"
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
            section_eleve += "\n→ Grands nombres, opérations complexes autorisées."

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
✅ Division (÷)  → inclut la division posée, division avec reste

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

2. DÉCOMPOSITION VISUELLE VERTICALE :
   ⛔ RÈGLE ABSOLUE — SI UNE IMAGE EST AFFICHÉE :
   NE fais JAMAIS de décomposition verticale en texte. L'image le montre déjà.
   Dis UNIQUEMENT : "Regarde bien l'image ! 😊" puis pose l'exercice.

   ✅ SEULEMENT si aucune image n'est affichée :
   Tu peux expliquer le calcul en texte linéaire (ex: "7+5=12, j'écris 2 je retiens 1").
   Utilise 🔴 pour les retenues et 🟢 pour le résultat final.
   Reste concis : 2-3 lignes maximum.

3. STRATÉGIE MENTALE (ZPD) : Donne UNE technique concrète que l'enfant peut reproduire seul.
   - Addition : "Mets 5 dans ta tête 🧠, lève 3 doigts 🤚, compte : 6, 7, 8 !"
   - Soustraction : "Pars de 3, compte jusqu'à 7 sur tes doigts : 4, 5, 6, 7 → 4 doigts levés !"
   - Multiplication : "3×4 = 4+4+4. Compte par bonds de 4 : 4, 8, 12 !"
   - Division : "Cherche combien de fois le diviseur rentre dans le dividende. Compte par bonds : 4, 8, 12... Tu t'arrêtes avant de dépasser !"

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

   TEMPS 2 — MODELAGE (Exemple similaire résolu) :
   Tu vas inventer un NOUVEAU calcul très ressemblant à celui de l'élève (même opération, même difficulté) pour lui montrer l'exemple.
   Commence TOUJOURS par : "Regarde comment je fais pour un calcul qui ressemble : on suit les mêmes étapes dans l'image et on applique ! 😊"
   
   ⚠️ RÈGLE DE COHÉRENCE VISUELLE ABSOLUE : 
   Tu dois résoudre ce calcul inventé en utilisant EXACTEMENT la même méthode que celle montrée dans l'image.
   - Si l'image montre une opération posée (colonnes D et U), ton explication DOIT décrire le calcul colonne par colonne en mentionnant les retenues.
   - Si l'image montre une méthode horizontale, un arbre, ou du calcul mental, utilise cette méthode précise.
   - Utilise le vocabulaire visuel approprié (ex: "colonne des unités", "on descend le chiffre", "le reste", etc.).

   Ensuite, donne le résultat final de ton calcul inventé.
   ❌ Tu ne dois JAMAIS donner le résultat du calcul ORIGINAL de l'élève.

   TEMPS 3 — TRANSFERT (À l'élève de jouer) :
   Demande à l'élève d'appliquer ce qu'il vient de voir sur son PROPRE calcul.
   Commence TOUJOURS par : "À toi de jouer maintenant avec tes chiffres : Combien font [a] [op] [b] ? 🤔"
   (Remplace a et b par les vrais nombres de l'exercice de l'élève).
   → Ajoute OBLIGATOIREMENT l'emoji ✏️ ou 🤔 devant la question !
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

⚠️ RÈGLE ABSOLUE — VERDICT PYTHON :
   Le message de l'élève peut contenir un [VERDICT PYTHON]. Ce verdict est calculé par Python et il a TOUJOURS raison.
   Tu ne dois JAMAIS le contredire ou faire ton propre calcul.
    → Si [VERDICT PYTHON: CORRECT ✅] : tu DOIS dire Bravo et féliciter. JAMAIS dire que c'est faux.
    → Si [VERDICT PYTHON: PRESQUE CORRECT 🟡] : tu DOIS féliciter le quotient trouvé, puis demander la réponse COMPLÈTE (quotient ET reste). JAMAIS demander juste le reste seul. Redemande le MÊME exercice avec ✏️.
    → Si [VERDICT PYTHON: INCORRECT ❌] : tu DOIS suivre les 4 TEMPS de correction. Les ÉTAPES EXACTES sont fournies — utilise-les telles quelles, ne les invente pas.
    → Si pas de verdict : l'élève n'a pas répondu à un exercice, traite normalement.

   ⚠️ DIVISION AU PRIMAIRE — RÈGLE ABSOLUE :
   La division est TOUJOURS euclidienne : quotient entier + reste.
   JAMAIS de résultat décimal (pas de virgule, pas de "environ").
   89 ÷ 9 = 9 reste 8 ✅ (JAMAIS "9,89" ou "environ 9.89" ❌)
   48 ÷ 5 = 9 reste 3 ✅ (JAMAIS "9,6" ❌)
   36 ÷ 4 = 9 ✅ (pas de reste car 36 = 4 × 9 exactement)

   ⚠️ NOMBRES DÉCIMAUX — RÈGLE ABSOLUE :
   JAMAIS de nombres décimaux dans les exercices ni les explications.
   JAMAIS de virgule dans un résultat (pas de 9,6 ni de 7,25 ni de 3,5).
   Tous les calculs utilisent des nombres ENTIERS uniquement.
   Si un résultat Python est décimal, convertis en division euclidienne :
   48 ÷ 5 = 9 reste 3 ✅ (JAMAIS 9,6 ❌)
   17 ÷ 4 = 4 reste 1 ✅ (JAMAIS 4,25 ❌)
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

if "erreurs_consec" not in st.session_state: st.session_state["erreurs_consec"] = 0
if session_key    not in st.session_state: st.session_state[session_key]    = []
if etape_key      not in st.session_state: st.session_state[etape_key]      = "amorce"
if score_key      not in st.session_state: st.session_state[score_key]      = {"bonnes": 0, "total": 0}
if eleve_key      not in st.session_state: st.session_state[eleve_key]      = {"prenom": "", "niveau": "", "session_db_id": None}
if "debut_session" not in st.session_state: st.session_state["debut_session"] = None
if chat_actif_key not in st.session_state: st.session_state[chat_actif_key] = False
if "choix_list"    not in st.session_state: st.session_state["choix_list"]    = None
if "choix_image"   not in st.session_state: st.session_state["choix_image"]   = None
if "choix_consigne" not in st.session_state: st.session_state["choix_consigne"] = None
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
    lbl_start  = " Commencer" if langue_choisie == "Français" else " ابدأ"

    # Bandeau compact animé
    if langue_choisie == "Français":
        titre_html = (
            "<span style=\"font-size:1.1rem; font-weight:500; color:white;\">👋 Bienvenue ! Je suis ton tuteur IA en mathématiques.</span><br>"
            "<span style=\"font-size:0.9rem; font-weight:400; color:white; opacity:1;\">"
            "Écris ton prénom, choisis ton niveau, puis clique sur <b>Commencer</b> pour débuter !"
            "</span>"
        )
    else:
        titre_html = (
            "<span style=\"font-size:1.1rem; font-weight:500; color:white;\">👋 مرحباً بك! أنا معلمك الذكي في الرياضيات.</span><br>"
            "<span style=\"font-size:0.9rem; font-weight:400; color:white; opacity:1;\">"
            "اكتب اسمك، اختر مستواك، ثم اضغط على <b>ابدأ</b> للبدء!"
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
            msg_bv = f"👋 Bonjour **{prenom}** ! 🌟\n\nJe suis ton tuteur de mathématiques — niveau **{niveau}** 😊\n\nÉcris un calcul ou dis-moi ce que tu veux apprendre !"
        else:
            msg_bv = f"👋 مرحباً **{prenom}** ! 🌟\n\nأنا معلمك للرياضيات — مستوى **{niveau}** 😊\n\n اكتب عملية أو أخبرني بما تريد تعلمه ! "
        st.session_state[session_key] = [AIMessage(content=msg_bv)]
        st.rerun()

    # ── Footer toujours visible ──

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
            pdf.cell(60,7,f"Duree : {formater_duree(duree_d)}",ln=True)
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
_img_hist = st.session_state.get("images_history", {})
for i, msg in enumerate(chat_history):
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        if role == "assistant":
            # --- MODIFICATION ICI : Vérification stricte de l'image ---
            _img_stored = _img_hist.get(i)
            if _img_stored:
                if os.path.exists(_img_stored):
                    st.image(_img_stored, width=300) # Taille augmentée pour la soutenance
                else:
                    st.warning(f"Image introuvable : {_img_stored}")
            # --- FIN DE LA MODIFICATION ---
            
            st.markdown(f'<div dir="{direction}">{msg.content}</div>', unsafe_allow_html=True)
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
if chat_actif:
    # ── Calcul du score et de la barre de progression ──
    _bonnes = st.session_state[score_key]["bonnes"]
    _total  = st.session_state[score_key]["total"]
    _taux_aff = round(_bonnes / _total * 100) if _total > 0 else 0

    if _taux_aff >= 80:
        _bar_col, _star = "#4ECDC4, #00b894", "🌟"
    elif _taux_aff >= 50:
        _bar_col, _sh_col, _star = "#FF9A3C, #FFD93D", "#FF9A3C", "⭐"
    else:
        _bar_col, _sh_col, _star = "#FF6B6B, #FF9A3C", "#FF6B6B", "💪"

    _titre = f"🏅 {_bonnes}/{_total} — {_star}"

    _, _col_bar, _ = st.columns([2, 2, 2])
    with _col_bar:
        st.markdown(f"""
        <div style="margin:4px auto; padding:5px 12px; background:white; border-radius:14px; border:1.5px solid #4ECDC4; box-shadow:0 2px 8px rgba(78,205,196,0.15); font-family:'Fredoka One',cursive;">
            <div style="font-size:11px; color:#0F6E56; font-weight:700; text-align:center; margin-bottom:4px;">
                {_titre} ({_taux_aff}%)
            </div>
            <div style="background:#f0f0f0; border-radius:20px; height:10px; overflow:hidden;">
                <div style="background:linear-gradient(90deg,{_bar_col}); width:{_taux_aff}%; height:100%; border-radius:20px;"></div>
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
                reply_inc = "👋 مرحباً ! 😊 أنا معلم الرياضيات للسلك الابتدائي.\nاكتب عملية حسابية أو أخبرني بما تريد تعلمه ! "
            else:
                reply_inc = "👋 Bonjour ! 😊 Je suis ton tuteur de maths du cycle primaire.\nÉcris un calcul ou dis-moi ce que tu veux apprendre ! "
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

        def est_question_generique(msg, op=None):
            """True si l'élève nomme une opération sans préciser le type."""
            m = (msg or "").lower().strip()
            # op = résultat de detecter_operation_demandee (passé en paramètre)
            has_generic = op is not None
            mots_specifiques = [
                "retenue","emprunt","sans","avec","simple","deux chiffres","trois chiffres",
                "virgule","décimale","dénominateur","fractions équivalentes",
                "احتفاظ","استلاف","بدون","بعدد","أرقام","عشري",
            ]
            has_specific = any(mot in m for mot in mots_specifiques)
            has_number   = any(c.isdigit() for c in m)
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
                return imgs.get("addition_3_chiffres"), "addition à 3 chiffres"

            # ── Soustraction ──
            if any(x in m for x in ["soustraction","soustraire","enlever","الطرح"]):
                if any(x in m for x in ["double emprunt","استلافين"]):
                    return imgs.get("soustraction_double_emprunt"), "soustraction avec double emprunt, 3 chiffres"
                if any(x in m for x in ["3 chiffres","trois chiffres"]) and any(x in m for x in ["3 chiffres","trois chiffres","mêm"]):
                    return imgs.get("soustraction_3_chiffres"), "soustraction à 3 chiffres"
                if any(x in m for x in ["sans emprunt", "sans retenue", "بدون استلاف", "بدون احتفاظ"]):
                    return imgs.get("soustraction_sans_retenue"), "soustraction sans emprunt"
                if any(x in m for x in ["emprunt","استلاف","retenu","retenue"]):
                    return imgs.get("soustraction_avec_retenue"), "soustraction avec emprunt, 2 chiffres"
                if n <= 1: return imgs.get("soustraction_simple"),       "soustraction simple"
                if n == 2: return imgs.get("soustraction_sans_retenue"), "soustraction sans emprunt"
                if n == 3: return imgs.get("soustraction_avec_retenue"), "soustraction avec emprunt"
                if n == 4: return imgs.get("soustraction_3_chiffres"),   "soustraction à 3 chiffres"
                return imgs.get("soustraction_3_chiffres"), "soustraction à 3 chiffres"

            # ── Multiplication ──
            if any(x in m for x in ["multiplication","multiplier","multiplie","الضرب","يضرب","×"]):
                if any(x in m for x in ["table","جدول"]):
                    return imgs.get("tables_multiplication"), "tables de multiplication"
                if any(x in m for x in ["10","100","1000"]):
                    return imgs.get("multiplication_10_100_1000"), "multiplication par 10, 100, 1000"
                if any(x in m for x in ["deux chiffres","2 chiffres","بعددين"]):
                    return imgs.get("multiplication_2_chiffres"), "multiplication 2 chiffres × 2 chiffres, deux lignes + addition finale"
                if n <= 3: return imgs.get("tables_multiplication"),   "tables de multiplication"
                if n == 4: return imgs.get("multiplication_simple"),   "multiplication 2 chiffres × 1 chiffre"
                if n == 5: return imgs.get("multiplication_2_chiffres"), "multiplication 2 chiffres × 2 chiffres"
                return imgs.get("multiplication_3_chiffres"), "multiplication à 3 chiffres"

            # ── Division ──
            if any(x in m for x in ["division","diviser","divise","القسمة","يقسم","÷"]):
                if any(x in m for x in ["deux chiffres","2 chiffres","بعددين"]):
                    return imgs.get("division_2_chiffres"), "division posée, diviseur à 2 chiffres"
                if any(x in m for x in ["reste","الباقي"]):
                    return imgs.get("division_avec_reste"), "division avec reste"
                if n <= 3: return imgs.get("division_simple"),     "division simple, exemple image : 84 ÷ 4 = 21"
                if n == 4: return imgs.get("division_2_chiffres"), "division diviseur 2ch, exemple image : 156 ÷ 12 = 13"
                return imgs.get("division_2_chiffres"), "division posée, diviseur à 2 chiffres"

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
                img_path_p, consigne_p = get_image_for_calcul(a_p, op_p, b_p, niveau_eleve, langue_choisie)
                if img_path_p and os.path.exists(img_path_p):
                    st.session_state["choix_image"]    = img_path_p
                    st.session_state["choix_consigne"] = consigne_p
                    st.session_state["calcul_direct"]  = expr_p
                    st.session_state[etape_key]        = "explication"
                    etape_actuelle                     = "explication"

        # ── Détection changement de sujet EN COURS de séquence ──────
        mots_changement = ["passe à","passe a","change de","autre chose","autre sujet",
                       "maintenant","je veux apprendre","ننتقل","موضوع آخر","الآن أريد", "changer"]
    
        _new_operation = detecter_operation_demandee(user_input) if etape_actuelle != "amorce" else None
        
        # Vérifie si l'élève utilise un mot-clé de changement
        veut_changer_explicitement = any(m in user_input.lower() for m in mots_changement)
        
        est_changement = (
            etape_actuelle not in ("amorce", "clarification")
            and (
                # Soit il donne une nouvelle opération valide
                (_new_operation is not None and (veut_changer_explicitement or not any(c.isdigit() for c in user_input)))
                # Soit il dit EXPLICITEMENT qu'il veut changer (même s'il ne dit pas vers quoi !)
                or veut_changer_explicitement
            )
        )
        if est_changement:
            st.session_state[etape_key]       = "amorce"
            st.session_state["bonnes_consec"]  = 0
            st.session_state["choix_image"]    = None
            st.session_state["choix_consigne"] = None
            etape_actuelle = "amorce"
            # ── Pas de chiffres → clarification directe sans GPT ──
            if _new_operation and not any(c.isdigit() for c in user_input):
                st.session_state["hors_niveau_operation"] = _new_operation
                st.session_state[etape_key] = "clarification"
                if langue_choisie == "العربية":
                    _questions_ch = {
                        "addition"      : "تريد الجمع البسيط أم الجمع مع الاحتفاظ ؟ 😊",
                        "soustraction"  : "تريد الطرح البسيط أم الطرح مع الاستلاف ؟ 😊",
                        "multiplication": "تريد جداول الضرب أم الضرب المطول ؟ 😊",
                        "division"      : "تريد القسمة المضبوطة أم القسمة مع الباقي ؟😊",
                    }
                else:
                    _questions_ch = {
                        "addition"      : "Pas de problème ! 😊 Tu veux l'addition simple ou l'addition avec retenue ?",
                        "soustraction"  : "Pas de problème ! 😊 Tu veux la soustraction simple ou la soustraction avec emprunt ?",
                        "multiplication": "Pas de problème ! 😊 Tu veux les tables de multiplication ou la multiplication posée ?",
                        "division"      : "Pas de problème ! 😊 Tu veux la division exacte ou la division avec reste ?",
                    }
                _clarif_ch = _questions_ch.get(_new_operation, "Quel type tu veux apprendre ? 😊")
                direction = "rtl" if langue_choisie == "العربية" else "ltr"
                with st.chat_message("assistant"):
                    st.markdown(f'<div dir="{direction}">{_clarif_ch}</div>', unsafe_allow_html=True)
                st.session_state[session_key].append(HumanMessage(content=user_input))
                st.session_state[session_key].append(AIMessage(content=_clarif_ch))
                try:
                    sid_db = st.session_state[eleve_key].get("session_db_id")
                    db_ajouter_message(sid_db, "eleve", user_input)
                    db_ajouter_message(sid_db, "tuteur", _clarif_ch)
                except Exception:
                    pass
                st.rerun()

        # ── RÈGLE UNIVERSELLE : pas de chiffres + opération → clarification (toutes étapes) ──
        def _detecter_op_locale(msg):
            m = (msg or "").lower()
            if any(x in m for x in ["addit", "ajouter", "additionn", "adition", "الجمع", "جمع"]): return "addition"
            if any(x in m for x in ["soustract", "soustraire", "enlever", "retranch", "soustrcation", "الطرح", "طرح"]): return "soustraction"
            if any(x in m for x in ["multipli", "fois", "table", "multiplicatoin", "الضرب", "ضرب"]): return "multiplication"
            if any(x in m for x in ["divis", "partage", "répartir", "distribuer", "divison", "القسمة", "قسمة"]): return "division"
            return None
        _operation_universelle = _detecter_op_locale(user_input)
        _pas_chiffres_univ = not any(c.isdigit() for c in user_input)
        _calcul_univ = detecter_calcul_direct(user_input)
        if (_operation_universelle
                and _pas_chiffres_univ
                and not _calcul_univ
                and etape_actuelle not in ("clarification",)
                and not detecter_probleme_enonce(user_input)):
            st.session_state["hors_niveau_operation"] = _operation_universelle
            st.session_state[etape_key] = "clarification"
            if langue_choisie == "العربية":
                _questions_univ = {
                    "addition"      : "تريد الجمع البسيط أم الجمع مع الاحتفاظ ؟ 😊",
                    "soustraction"  : "تريد الطرح البسيط أم الطرح مع الاستلاف ؟ 😊",
                    "multiplication": "تريد جداول الضرب أم الضرب المطول ؟ 😊",
                    "division"      : "تريد القسمة المضبوطة أم القسمة مع الباقي ؟ 😊",
                }
            else:
                _questions_univ = {
                    "addition"      : "Tu veux l'addition simple ou l'addition avec retenue ? 😊",
                    "soustraction"  : "Tu veux la soustraction simple ou la soustraction avec emprunt ? 😊",
                    "multiplication": "Tu veux les tables de multiplication ou la multiplication posée ? 😊",
                    "division"      : "Tu veux la division exacte ou la division avec reste ? 😊",
                }
            _clarif_univ = _questions_univ.get(_operation_universelle, "Quel type tu veux apprendre ? 😊")
            direction = "rtl" if langue_choisie == "العربية" else "ltr"
            with st.chat_message("assistant"):
                st.markdown(f'<div dir="{direction}">{_clarif_univ}</div>', unsafe_allow_html=True)
            st.session_state[session_key].append(HumanMessage(content=user_input))
            st.session_state[session_key].append(AIMessage(content=_clarif_univ))
            try:
                sid_db = st.session_state[eleve_key].get("session_db_id")
                db_ajouter_message(sid_db, "eleve", user_input)
                db_ajouter_message(sid_db, "tuteur", _clarif_univ)
            except Exception:
                pass
            st.rerun()

        _skip_gpt = False
        if etape_actuelle == "amorce":
            operation = detecter_operation_demandee(user_input)
            calcul = detecter_calcul_direct(user_input)
        
            # ── CAS 1 : Calcul direct (ex: "13-7", "27+35", "15/4") ──
            if calcul:
                expr, a, op, b = calcul
                
                # On passe "langue_choisie" directement à la fonction
                img_path, consigne = get_image_for_calcul(a, op, b, niveau_eleve, langue_choisie)
                
                if consigne:
                    st.session_state["choix_consigne"] = consigne
                if img_path and os.path.exists(img_path):
                    st.session_state["choix_image"] = img_path
                else:
                    import logging
                    logging.warning(f"[IMAGE CAS1] Introuvable : {img_path}")
                    st.session_state["choix_image"] = None
                    
                st.session_state["calcul_direct"] = expr
                st.session_state[etape_key] = "explication"
                etape_actuelle = "explication"
            elif operation:
                # ── CAS 2 : Pas de chiffres → TOUJOURS clarification (quelle que soit la précision)
                _pas_de_chiffres = not any(c.isdigit() for c in user_input)
                if _pas_de_chiffres:
                    st.session_state["hors_niveau_operation"] = operation
                    st.session_state[etape_key] = "clarification"

                    # Générer la question de clarification en Python
                    _prenom = st.session_state[eleve_key].get("prenom", "")
                    if langue_choisie == "العربية":
                        _questions = {
                            "addition": f"تريد الجمع البسيط أم الجمع مع الاحتفاظ ؟ 😊",
                            "soustraction": f"تريد الطرح البسيط أم الطرح مع الاستلاف ؟ 😊",
                            "multiplication": f"تريد جداول الضرب أم الضرب المطول ؟ 😊",
                            "division": f"تريد القسمة المضبوطة أم القسمة مع الباقي ؟ 😊",
                        }
                    else:
                        _questions = {
                            "addition": f"Tu veux l'addition simple ou l'addition avec retenue ? 😊",
                            "soustraction": f"Tu veux la soustraction simple ou la soustraction avec emprunt ? 😊",
                            "multiplication": f"Tu veux les tables de multiplication ou la multiplication posée ? 😊",
                            "division": f"Tu veux la division exacte ou la division avec reste ? 😊",
                        }
                    _q = _questions.get(operation, "Quel type tu veux apprendre ? 😊")
                    _clarif_msg = f"{_q}"

                    # Injecter directement dans le chat sans appeler GPT
                    direction = "rtl" if langue_choisie == "العربية" else "ltr"
                    with st.chat_message("assistant"):
                        st.markdown(f'<div dir="{direction}">{_clarif_msg}</div>', unsafe_allow_html=True)
                    st.session_state[session_key].append(HumanMessage(content=user_input))
                    st.session_state[session_key].append(AIMessage(content=_clarif_msg))
                    try:
                        sid_db = st.session_state[eleve_key].get("session_db_id")
                        db_ajouter_message(sid_db, "eleve", user_input)
                        db_ajouter_message(sid_db, "tuteur", _clarif_msg)
                    except Exception:
                        pass
                    _skip_gpt = True

                # ── CAS 3 : Problème énoncé avec chiffres → image précise via calcul extrait ──
                else:
                    # Si pas de problème énoncé détecté → clarification directe
                    if not detecter_probleme_enonce(user_input):
                        st.session_state["hors_niveau_operation"] = operation
                        st.session_state[etape_key] = "clarification"
                        if langue_choisie == "العربية":
                            _questions_c3 = {
                                "addition"      : "تريد الجمع البسيط أم الجمع مع الاحتفاظ ؟ 😊",
                                "soustraction"  : "تريد الطرح البسيط أم الطرح مع الاستلاف ؟ 😊",
                                "multiplication": "تريد جداول الضرب أم الضرب المطول ؟ 😊",
                                "division"      : "تريد القسمة المضبوطة أم القسمة مع الباقي ؟ 😊",
                            }
                        else:
                            _questions_c3 = {
                                "addition"      : "Tu veux l'addition simple ou l'addition avec retenue ? 😊",
                                "soustraction"  : "Tu veux la soustraction simple ou la soustraction avec emprunt ? 😊",
                                "multiplication": "Tu veux les tables de multiplication ou la multiplication posée ? 😊",
                                "division"      : "Tu veux la division exacte ou la division avec reste ? 😊",
                            }
                        _clarif_c3 = _questions_c3.get(operation, "Quel type tu veux apprendre ? 😊")
                        direction = "rtl" if langue_choisie == "العربية" else "ltr"
                        with st.chat_message("assistant"):
                            st.markdown(f'<div dir="{direction}">{_clarif_c3}</div>', unsafe_allow_html=True)
                        st.session_state[session_key].append(HumanMessage(content=user_input))
                        st.session_state[session_key].append(AIMessage(content=_clarif_c3))
                        try:
                            sid_db = st.session_state[eleve_key].get("session_db_id")
                            db_ajouter_message(sid_db, "eleve", user_input)
                            db_ajouter_message(sid_db, "tuteur", _clarif_c3)
                        except Exception:
                            pass
                        st.rerun()
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
                                
                                # Appel avec les bonnes variables définies AU-DESSUS + langue_choisie
                                img_path, consigne = get_image_for_calcul(_a, _op, _b, niveau_eleve, langue_choisie)
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
                    etape_actuelle = "explication"
        # ── CAS 4 : Réponse à la clarification ──
        elif etape_actuelle == "clarification":
            stored_op = st.session_state.get("hors_niveau_operation", "")
            combined  = f"{stored_op} {user_input}".strip()
            # ── Enrichir les réponses courtes de l'élève ──
            _ui = user_input.lower().strip()
            if stored_op == "soustraction":
                if "avec" in _ui and "emprunt" not in _ui:
                    combined = "soustraction avec emprunt"
                elif "simple" in _ui or "sans" in _ui:
                    combined = "soustraction sans emprunt"
            elif stored_op == "addition":
                if "avec" in _ui and "retenue" not in _ui:
                    combined = "addition avec retenue"
                elif "simple" in _ui or "sans" in _ui:
                    combined = "addition sans retenue"
            elif stored_op == "multiplication":
                if "table" in _ui:
                    combined = "multiplication tables"
                elif "posée" in _ui or "posé" in _ui or "posee" in _ui or "pose" in _ui or "deux" in _ui or "2" in _ui:
                    combined = "multiplication deux chiffres"
            elif stored_op == "division":
                if "exact" in _ui or "simple" in _ui or "sans" in _ui or "مضبوط" in _ui or "بدون" in _ui:
                    combined = "division simple"
                elif "reste" in _ui or "باقي" in _ui:
                    combined = "division avec reste"
                elif "deux" in _ui or "2" in _ui or "رقمين" in _ui or "posée" in _ui:
                    combined = "division deux chiffres"
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
            etape_actuelle = "explication"
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

        if not _skip_gpt:
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
                        if _img_path and _choix_consigne and etape_actuelle in ("explication", "choix_sujet"):
                            # 1. Retrouver la clé de l'image (ex: "addition_simple") à partir de son chemin
                            image_key = None
                            images_dict = IMAGES_MAP.get(langue_choisie, {})
                            for key, path in images_dict.items():
                                if path == _img_path:
                                    image_key = key
                                    break
                            # 2. Récupérer l'explication fixée dans ton dictionnaire EXPLICATIONS_IMAGES
                            explication_statique = ""
                            if image_key and 'EXPLICATIONS_IMAGES' in globals() and image_key in EXPLICATIONS_IMAGES:
                                explication_statique = EXPLICATIONS_IMAGES[image_key].get(langue_choisie, "")

                            # 3. إجبار GPT على استخدام الشرح، ثم إرجاع الكرة للتلميذ ليقوم بالحل (بدون إعطاء النتيجة)
                            if langue_choisie == "العربية":
                                consigne_specifique = (
                                    f"[تعليمات النظام : تم عرض صورة تعليمية. "
                                    f"✅ إلزامي جداً : 1) يجب عليك أن تبدأ إجابتك بالحرف الواحد بهذا النص :\n"
                                    f"« {explication_statique} »\n"
                                    f"2) ❌ ممنوع منعاً باتاً : لا تقم بحل العملية ولا تعطِ النتيجة النهائية أبداً.\n"
                                    f"3) اطلب من التلميذ أن يطبق هذه الطريقة بنفسه واختم بـ '✏️ دورك !' مع : {_exercice_final_ar} ]"
                                )
                            else:
                                consigne_specifique = (
                                    f"[CONSIGNE SYSTÈME : Une image pédagogique est affichée. "
                                    f"✅ OBLIGATOIRE : 1) Tu DOIS commencer ta réponse EXACTEMENT mot pour mot par ce texte :\n"
                                    f"« {explication_statique} »\n"
                                    f"2) ❌ INTERDIT ABSOLU : NE RÉSOUD PAS le calcul et NE DONNE JAMAIS le résultat final.\n"
                                    f"3) Demande à l'élève d'appliquer cette méthode lui-même et termine par '✏️ À toi !' avec : {_exercice_final} ]"
                                )
                                
                            message_final = f"{message_avec_verdict}\n{consigne_specifique}"
                            
                            # Nettoyer les variables après utilisation
                            st.session_state["choix_image"] = None
                            st.session_state["choix_consigne"] = None

                        elif _choix_consigne and etape_actuelle in ("explication", "choix_sujet"):
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
                                        f"[تعليمات مطلقة : لا توجد صورة. "
                                        f"❌ ممنوع منعاً باتاً : التفكيك العمودي، أعمدة الأرقام، المحاذاة. "
                                        f"❌ ممنوع : قول 'انظر'، 'إليك'، عرض عملية مرتبة. "
                                        f"❌ ممنوع : سؤال 'هل تريد تمريناً ؟'. يجب أن تطرح تمريناً مباشرة. "
                                        f"✅ الشكل الإلزامي في 4 أسطر كحد أقصى : "
                                        f"السطر 1 : 'لحل هذا الحساب، نستخدم [العملية] !' "
                                        f"السطر 2 : مثال ملموس من الحياة اليومية (حلويات، كرات) في جملة واحدة "
                                        f"السطر 3 : حيلة ذهنية في جملة واحدة "
                                        f"السطر 4 : '✏️ دورك ! كم يساوي [أ] [عملية] [ب] ؟' مع : {_choix_consigne}. "
                                        f"لا تعطِ الجواب أبداً. انتظر التلميذ.]"
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
                                        f"[CONSIGNE ABSOLUE : Il n'y a PAS d'image. "
                                        f"❌ INTERDIT ABSOLU : décomposition verticale, colonnes de chiffres, alignement. "
                                        f"❌ INTERDIT : dire 'Regarde', 'Voici', montrer un calcul posé. "
                                        f"❌ INTERDIT : demander 'Tu veux un exercice ?'. Tu DOIS en poser un directement. "
                                        f"✅ FORMAT OBLIGATOIRE en 4 lignes MAXIMUM : "
                                        f"Ligne 1 : 'Pour ce calcul, on utilise [OPERATION] !' "
                                        f"Ligne 2 : Un exemple concret du quotidien (bonbons, billes) en UNE phrase "
                                        f"Ligne 3 : Une astuce mentale en UNE phrase "
                                        f"Ligne 4 : '✏️ À toi ! Combien font [a] [op] [b] ?' avec : {_choix_consigne}. "
                                        f"Ne donne JAMAIS la réponse. ATTENDS l'élève.]"
                                    )
                            message_final = f"{message_avec_verdict}\n{consigne_specifique}"
                            st.session_state["choix_consigne"] = None

                        else:
                            # CAS C : Flux normal — verdict calculé AVANT pour choisir la bonne consigne
                            _verdict_pre = verifier_reponse(user_input, chat_history)
                            etape_pour_consigne = etape_actuelle
                            if _verdict_pre and isinstance(_verdict_pre, str) and (
                                _verdict_pre.startswith("incorrect") or _verdict_pre.startswith("presque")
                            ):
                                if etape_actuelle == "exercice1":
                                    etape_pour_consigne = "correction1"
                                elif etape_actuelle == "exercice2":
                                    etape_pour_consigne = "correction2"
                                elif etape_actuelle in ("quiz", "correction_quiz"):
                                    etape_pour_consigne = "correction_quiz"
                            message_final = injecter_consigne_etape(
                                message_avec_verdict, etape_pour_consigne, langue_choisie
                            )
                        # Forcer la consigne en priorité haute pour clarification
                            if etape_actuelle == "clarification":
                                if langue_choisie == "العربية":
                                    consigne_specifique = (
                                        "[تعليمات مطلقة : التلميذ طرح سؤالاً عاماً. "
                                        "❌ ممنوع : شرح العملية أو إعطاء أمثلة أو طرح تمرين. "
                                        "✅ اطرح سؤالاً واحداً فقط للتوضيح في سطر واحد. "
                                        "مثال للطرح : 'تريد الطرح البسيط أم الطرح مع الاستلاف ؟ 😊' "
                                        "لا تكتب أي شيء آخر بعد السؤال.]"
                                    )
                                else:
                                    consigne_specifique = (
                                        "[CONSIGNE ABSOLUE : L'élève a posé une question générique. "
                                        "❌ INTERDIT : expliquer l'opération, donner des exemples, poser un exercice. "
                                        "✅ Pose UNE SEULE question de clarification en UNE ligne. "
                                        "Exemple pour soustraction : 'Tu veux la soustraction simple ou la soustraction avec emprunt ? 😊' "
                                        "N'écris RIEN d'autre après la question.]"
                                    )
                            else:
                                consigne_specifique = ""
                            _img_path = None

                        # ── 3. Construire le system prompt avec la consigne courante ──
                        # La consigne est dans le system prompt → priorité haute → GPT ne peut pas l'ignorer
                        # --- GESTION DE LA FRUSTRATION (Max 2 erreurs) ---
                        if "_verdict_pre" not in locals():
                            _verdict_pre = verifier_reponse(user_input, chat_history)

                        if _verdict_pre and isinstance(_verdict_pre, str) and (
                            _verdict_pre.startswith("incorrect") or _verdict_pre.startswith("presque")
                        ):
                            st.session_state["erreurs_consec"] += 1
                        elif _verdict_pre == "correct":
                            st.session_state["erreurs_consec"] = 0

                        if st.session_state["erreurs_consec"] >= 2:
                            if langue_choisie == "العربية":
                                alerte_frustration = (
                                    "\n\n[تعليمات النظام - أولوية قصوى : التلميذ أخطأ مرتين ! ❌ "
                                    "تجاهل قاعدة 'لا تعط الجواب'. "
                                    "قم بحل عملية التلميذ الأصلية واشرحها خطوة بخطوة. "
                                    "⚠️ قاعدة الحل : "
                                    "- إذا كانت الأعداد كبيرة (تحتاج إلى وضع عمودي)، اشرح عموداً بعمود (الوحدات ثم العشرات مع الاحتفاظ). "
                                    "- إذا كانت الأعداد صغيرة (رقم واحد)، اشرح بطريقة العد الذهني البسيطة. "
                                    "أعطِ النتيجة النهائية بوضوح.\n"
                                    "🚨 أمر صارم جداً بعد إعطاء النتيجة : يجب عليك أن تطرح عملية رياضية جديدة كلياً (بأرقام مختلفة) لتتأكد من فهمه. "
                                    "❌ لا تطلب منه أبداً إعادة الحساب الذي قمت بحله للتو ! "
                                    "اختم رسالتك بـ '✏️ نمر إلى تمرين آخر للتدرب ! دورك : كم يساوي [العملية_الجديدة] ؟'\n"
                                    "⚠️ تحذير صارم : لا تستخدم أبداً كلمات مثل 'أحسنت'، 'صحيح'، 'ممتاز' أو 'رائع' في إجابتك !]"
                                )
                            else:
                                alerte_frustration = (
                                    "\n\n[CONSIGNE SYSTÈME - PRIORITÉ ABSOLUE : L'élève a fait 2 erreurs ! ❌ "
                                    "IGNORE la règle 'NE DONNE JAMAIS LA RÉPONSE'. "
                                    "RÉSOUS le calcul original de l'élève étape par étape. "
                                    "⚠️ RÈGLE DE RÉSOLUTION : "
                                    "- Si les nombres sont grands, tu DOIS expliquer colonne par colonne (unités, dizaines, retenues). "
                                    "- Si ce sont de petits nombres (1 seul chiffre), explique simplement (ex: 'Mets 5 dans ta tête et avance de 3'). "
                                    "Donne le résultat final clairement.\n"
                                    "🚨 ORDRE STRICT APRÈS AVOIR DONNÉ LE RÉSULTAT : Tu DOIS proposer un TOUT NOUVEAU calcul (avec des nombres différents) pour vérifier s'il a compris. "
                                    "❌ Ne lui demande JAMAIS de refaire le calcul que tu viens de résoudre ! "
                                    "Termine ton message par '✏️ On passe à un autre pour s'entraîner ! À toi : Combien font [nouveau_calcul] ?'\n"
                                    "⚠️ AVERTISSEMENT : N'utilise JAMAIS les mots 'Bravo', 'Juste', 'Correct', 'Exact' ou 'Parfait' dans cette réponse !]"
                                )
                            # 1. On écrase la consigne pour forcer GPT à obéir
                            consigne_specifique = alerte_frustration
                            # 2. On cache le verdict Python (qui lui disait de ne pas répondre)
                            message_final = user_input
                        # ------------------------------------------------
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
                        # RESET ERREURS SI FRUSTRATION A ÉTÉ DÉCLENCHÉE
                        if st.session_state["erreurs_consec"] >= 2:
                            st.session_state["erreurs_consec"] = 0
                        # ── Verdict Python ──────────────────────────────
                        _verdict = verifier_reponse(user_input, chat_history)
                        if _verdict is not None:
                            st.session_state[score_key]["total"] += 1
                            if _verdict == "correct" or (isinstance(_verdict, str) and _verdict.startswith("correct")):
                                st.session_state[score_key]["bonnes"] += 1
                                # Filet de sécurité : si GPT a dit quelque chose de négatif alors que c'est correct
                                mots_negatifs = ["courageux", "essayé", "tentative", "pas tout à fait", "شجاع", "محاولة"]
                                if any(m in assistant_reply.lower() for m in mots_negatifs):
                                    prenom = st.session_state[eleve_key].get("prenom", "")
                                    exercice = extraire_exercice(chat_history)
                                    expr = exercice[0] if exercice else ""
                                    if langue_choisie == "العربية":
                                        assistant_reply = f"🌟 أحسنت {prenom} ! الجواب صحيح ! 💪\n✏️ نكمل ! 😊"
                                    else:
                                        assistant_reply = f"🌟 Bravo {prenom} ! Tu as trouvé la bonne réponse ! 💪\n✏️ On continue ! 😊"
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
                            # Encore des exercices → force l'exercice 1
                            elif msg_strip in ["1", "١", "1️⃣"] or "encore" in ul or "oui" in ul or "نعم" in ul:
                                st.session_state[etape_key]      = "exercice1" 
                                st.session_state["bonnes_consec"] = 0
                                # Force le tuteur à poser un nouvel exercice immédiatement
                                st.session_state["choix_consigne"] = "exercice de renforcement"

                        # ── Stocker l'image dans l'historique persistant ──────
                        if _img_path:
                            next_idx = len(chat_history) + 1
                            st.session_state["images_history"][next_idx] = _img_path

                        # ── Affichage stable : image en haut, texte dessous ──────
                        if _img_path:
                            st.image(_img_path, width=250)  # Utilise la même taille qu'au-dessus
                        st.markdown(f'<div dir="{direction}">{assistant_reply}</div>', unsafe_allow_html=True)

                    except Exception as e:
                        import traceback
                        st.error(f"❌ {type(e).__name__}: {e}")
                        st.code(traceback.format_exc())
                        st.stop()

        if not _skip_gpt:
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
            import plotly.express as px
            import plotly.graph_objects as go
            from datetime import datetime, timedelta

            df = pd.DataFrame(sessions)
            if "created_at" in df.columns:
                df["created_at"] = pd.to_datetime(df["created_at"])

            # ════════════════════════════════
            # FILTRES
            # ════════════════════════════════
            st.markdown("#### 🔍 Filtres")
            f1, f2, f3, f4 = st.columns(4)

            with f1:
                niveaux_opts = ["Tous"] + sorted(df["niveau"].dropna().unique().tolist()) if "niveau" in df else ["Tous"]
                filtre_niveau = st.selectbox("Niveau", niveaux_opts, key="f_niveau")

            with f2:
                langues_opts = ["Toutes"] + sorted(df["langue"].dropna().unique().tolist()) if "langue" in df else ["Toutes"]
                filtre_langue = st.selectbox("Langue", langues_opts, key="f_langue")

            with f3:
                periodes = ["Tout", "7 derniers jours", "30 derniers jours", "Aujourd'hui"]
                filtre_periode = st.selectbox("Période", periodes, key="f_periode")

            with f4:
                etapes_opts = ["Toutes"] + sorted(df["etape_finale"].dropna().unique().tolist()) if "etape_finale" in df else ["Toutes"]
                filtre_etape = st.selectbox("Étape finale", etapes_opts, key="f_etape")

            # Appliquer les filtres
            dff = df.copy()
            if filtre_niveau != "Tous" and "niveau" in dff:
                dff = dff[dff["niveau"] == filtre_niveau]
            if filtre_langue != "Toutes" and "langue" in dff:
                dff = dff[dff["langue"] == filtre_langue]
            if filtre_etape != "Toutes" and "etape_finale" in dff:
                dff = dff[dff["etape_finale"] == filtre_etape]
            if "created_at" in dff.columns:
                now = pd.Timestamp.now(tz="UTC")
                if filtre_periode == "Aujourd'hui":
                    dff = dff[dff["created_at"] >= now - timedelta(days=1)]
                elif filtre_periode == "7 derniers jours":
                    dff = dff[dff["created_at"] >= now - timedelta(days=7)]
                elif filtre_periode == "30 derniers jours":
                    dff = dff[dff["created_at"] >= now - timedelta(days=30)]

            st.markdown(f"<small style='color:#888'>**{len(dff)}** session(s) affichée(s) sur {len(df)} au total</small>", unsafe_allow_html=True)
            st.markdown("---")

            # ════════════════════════════════
            # MÉTRIQUES LIGNE 1
            # ════════════════════════════════
            c1, c2, c3, c4, c5 = st.columns(5)

            def metric_card(col, val, lbl, color="#FF6B6B"):
                col.markdown(f'''<div class="admin-metric">
                    <div class="val" style="color:{color}">{val}</div>
                    <div class="lbl">{lbl}</div>
                </div>''', unsafe_allow_html=True)

            with c1: metric_card(c1, len(dff), "Sessions", "#4ECDC4")
            with c2:
                taux_moy = round(dff["taux"].mean(), 1) if "taux" in dff and len(dff) > 0 else 0
                metric_card(c2, f"{taux_moy}%", "Taux moyen", "#FF6B6B" if taux_moy < 50 else "#4ECDC4")
            with c3:
                felicitations = len(dff[dff["etape_finale"] == "felicitations"]) if "etape_finale" in dff.columns else 0
                pct_complet = round(felicitations/len(dff)*100) if len(dff) > 0 else 0
                metric_card(c3, f"{pct_complet}%", "Séquences complètes", "#FFE66D")
            with c4:
                moy_msg = round(dff["nb_messages"].mean(), 1) if "nb_messages" in dff.columns else 0
                metric_card(c4, moy_msg, "Messages/session", "#764ba2")
            with c5:
                niv_uniq = dff["niveau"].nunique() if "niveau" in dff.columns else 0
                metric_card(c5, niv_uniq, "Niveaux actifs", "#FF9A3C")

            # MÉTRIQUES LIGNE 2 — Durées
            if "duree_minutes" in dff.columns and dff["duree_minutes"].sum() > 0:
                df_d = dff[dff["duree_minutes"] > 0]
                if len(df_d) > 0:
                    st.markdown("")
                    d1, d2, d3, d4 = st.columns(4)
                    with d1: st.metric("⏱️ Durée moy.", formater_duree(df_d['duree_minutes'].mean()))
                    with d2: st.metric("⏱️ Durée totale", formater_duree(df_d['duree_minutes'].sum()))
                    with d3: st.metric("⏱️ Min. session", formater_duree(df_d['duree_minutes'].min()))
                    with d4: st.metric("⏱️ Max. session", formater_duree(df_d['duree_minutes'].max()))

            st.markdown("---")

            # ════════════════════════════════
            # GRAPHIQUES — 2 colonnes
            # ════════════════════════════════
            col_g1, col_g2 = st.columns(2)

            # Graphique 1 — Taux par niveau (barres)
            with col_g1:
                if "niveau" in dff.columns and "taux" in dff.columns and len(dff) > 0:
                    df_niv = dff.groupby("niveau")["taux"].mean().reset_index().sort_values("niveau")
                    fig1 = px.bar(df_niv, x="niveau", y="taux",
                        color="taux",
                        color_continuous_scale=["#FF6B6B","#FFE66D","#4ECDC4"],
                        labels={"niveau": "Niveau", "taux": "Taux %"},
                        title="📊 Taux de réussite par niveau",
                        text="taux")
                    fig1.update_traces(texttemplate='%{text:.0f}%', textposition='outside')
                    fig1.update_layout(height=280, showlegend=False,
                        plot_bgcolor="white", paper_bgcolor="white",
                        margin=dict(t=40, b=20))
                    st.plotly_chart(fig1, use_container_width=True)

            # Graphique 2 — Répartition par langue (camembert)
            with col_g2:
                if "langue" in dff.columns and len(dff) > 0:
                    df_lang = dff["langue"].value_counts().reset_index()
                    df_lang.columns = ["Langue", "Count"]
                    fig2 = px.pie(df_lang, names="Langue", values="Count",
                        color_discrete_sequence=["#4ECDC4","#FF6B6B","#FFE66D"],
                        title="🌐 Répartition par langue",
                        hole=0.4)
                    fig2.update_layout(height=280, margin=dict(t=40, b=20))
                    st.plotly_chart(fig2, use_container_width=True)

            col_g3, col_g4 = st.columns(2)

            # Graphique 3 — Évolution dans le temps
            with col_g3:
                if "created_at" in dff.columns and len(dff) > 1:
                    df_time = dff.copy()
                    df_time["date"] = df_time["created_at"].dt.date
                    df_time_grp = df_time.groupby("date").agg(
                        sessions=("taux", "count"),
                        taux_moy=("taux", "mean")
                    ).reset_index()
                    fig3 = go.Figure()
                    fig3.add_trace(go.Bar(x=df_time_grp["date"], y=df_time_grp["sessions"],
                        name="Sessions", marker_color="#4ECDC4", yaxis="y"))
                    fig3.add_trace(go.Scatter(x=df_time_grp["date"], y=df_time_grp["taux_moy"],
                        name="Taux %", line=dict(color="#FF6B6B", width=2),
                        mode="lines+markers", yaxis="y2"))
                    fig3.update_layout(
                        title="📈 Évolution dans le temps",
                        height=280, plot_bgcolor="white", paper_bgcolor="white",
                        margin=dict(t=40, b=20),
                        yaxis=dict(title="Sessions"),
                        yaxis2=dict(title="Taux %", overlaying="y", side="right", range=[0,100]),
                        legend=dict(orientation="h", y=-0.2)
                    )
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("Pas assez de données pour l'évolution temporelle")

            # Graphique 4 — Répartition étapes finales
            with col_g4:
                if "etape_finale" in dff.columns and len(dff) > 0:
                    df_etapes = dff["etape_finale"].value_counts().reset_index()
                    df_etapes.columns = ["Étape", "Count"]
                    etape_colors = {
                        "felicitations": "#4ECDC4",
                        "quiz": "#FFE66D",
                        "exercice2": "#FF9A3C",
                        "exercice1": "#FF6B6B",
                        "explication": "#764ba2",
                        "amorce": "#cccccc",
                        "correction1": "#ff4444",
                    }
                    colors = [etape_colors.get(e, "#888") for e in df_etapes["Étape"]]
                    fig4 = px.bar(df_etapes, x="Count", y="Étape", orientation="h",
                        title="🎯 Étapes finales atteintes",
                        color="Étape",
                        color_discrete_map=etape_colors)
                    fig4.update_layout(height=280, showlegend=False,
                        plot_bgcolor="white", paper_bgcolor="white",
                        margin=dict(t=40, b=20))
                    st.plotly_chart(fig4, use_container_width=True)

            st.markdown("---")

            # ════════════════════════════════
            # TABLEAU SESSIONS + VUE DÉTAILLÉE
            # ════════════════════════════════
            st.markdown("#### 📋 Détail des sessions")

            cols_affich = [c for c in ["created_at","prenom","niveau","langue",
                                        "bonnes","total","taux","duree_minutes","nb_messages","etape_finale"]
                           if c in dff.columns]

            df_display = dff[cols_affich].rename(columns={
                "created_at":"Date","prenom":"Prénom","niveau":"Niveau",
                "langue":"Langue","bonnes":"Bonnes","total":"Total",
                "taux":"Taux %","duree_minutes":"Durée",
                "nb_messages":"Messages","etape_finale":"Étape"
            })

            # Sélecteur de session pour vue détaillée
            selected_indices = st.dataframe(
                df_display,
                use_container_width=True, hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "Taux %": st.column_config.ProgressColumn("Taux %", min_value=0, max_value=100),
                    "Durée (sec)": st.column_config.NumberColumn("⏱️ Durée (sec)"),
                    "Date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY HH:mm"),
                }
            )

            # Vue détaillée si ligne sélectionnée
            if selected_indices and selected_indices.selection and selected_indices.selection.rows:
                idx = selected_indices.selection.rows[0]
                row = dff.iloc[idx]
                st.markdown("---")
                st.markdown(f"#### 🔎 Détail — {row.get('prenom','?')} | {row.get('niveau','?')} | {row.get('langue','?')}")

                det1, det2, det3, det4 = st.columns(4)
                with det1:
                    taux_row = row.get('taux', 0)
                    color = "#4ECDC4" if taux_row >= 70 else "#FF9A3C" if taux_row >= 40 else "#FF6B6B"
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val" style="color:{color}">{taux_row}%</div>
                        <div class="lbl">Taux de réussite</div>
                    </div>''', unsafe_allow_html=True)
                with det2:
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{row.get("bonnes",0)}/{row.get("total",0)}</div>
                        <div class="lbl">Bonnes réponses</div>
                    </div>''', unsafe_allow_html=True)
                with det3:
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{row.get("nb_messages",0)}</div>
                        <div class="lbl">Messages échangés</div>
                    </div>''', unsafe_allow_html=True)
                with det4:
                    duree = row.get("duree_minutes", 0)
                    st.markdown(f'''<div class="admin-metric">
                        <div class="val">{formater_duree(duree)}</div>
                        <div class="lbl">Durée session</div>
                    </div>''', unsafe_allow_html=True)

                # Jauge de progression
                etape = row.get("etape_finale", "amorce")
                etapes_ordre = ["amorce","explication","exercice1","correction1","exercice2","correction2","quiz","correction_quiz","felicitations"]
                etape_idx = etapes_ordre.index(etape) if etape in etapes_ordre else 0
                progression = round((etape_idx / (len(etapes_ordre)-1)) * 100)

                st.markdown(f"""
                <div style="margin:10px 0; padding:10px; background:white; border-radius:10px; border:1px solid #e5e7eb;">
                    <div style="font-size:12px; color:#666; margin-bottom:5px;">
                        Progression pédagogique — étape finale : <strong>{etape}</strong>
                    </div>
                    <div style="background:#f0f0f0; border-radius:20px; height:12px; overflow:hidden;">
                        <div style="background:linear-gradient(90deg,#4ECDC4,#45B7D1);
                                    width:{progression}%; height:100%; border-radius:20px;"></div>
                    </div>
                    <div style="font-size:11px; color:#aaa; text-align:right; margin-top:3px;">{progression}%</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # ════════════════════════════════
            # NOUVELLES MÉTRIQUES PÉDAGOGIQUES
            # ════════════════════════════════
            st.markdown("#### 📚 Analyse pédagogique")

            an1, an2 = st.columns(2)

            with an1:
                # Taux par langue
                if "langue" in dff.columns and "taux" in dff.columns and len(dff) > 0:
                    df_lang_taux = dff.groupby("langue")["taux"].mean().reset_index()
                    df_lang_taux.columns = ["Langue", "Taux moyen"]
                    df_lang_taux["Taux moyen"] = df_lang_taux["Taux moyen"].round(1)
                    fig_lang = px.bar(df_lang_taux, x="Langue", y="Taux moyen",
                        color="Langue",
                        color_discrete_sequence=["#4ECDC4","#FF6B6B"],
                        title="🌐 Taux de réussite par langue",
                        text="Taux moyen")
                    fig_lang.update_traces(texttemplate='%{text}%', textposition='outside')
                    fig_lang.update_layout(height=250, showlegend=False,
                        plot_bgcolor="white", paper_bgcolor="white",
                        margin=dict(t=40,b=20), yaxis=dict(range=[0,100]))
                    st.plotly_chart(fig_lang, use_container_width=True)

            with an2:
                # Distribution des taux (histogramme)
                if "taux" in dff.columns and len(dff) > 0:
                    fig_hist = px.histogram(dff, x="taux",
                        nbins=10,
                        color_discrete_sequence=["#764ba2"],
                        title="📊 Distribution des taux de réussite",
                        labels={"taux": "Taux %", "count": "Nombre de sessions"})
                    fig_hist.add_vline(x=dff["taux"].mean(), line_dash="dash",
                        line_color="#FF6B6B", annotation_text=f"Moy: {dff['taux'].mean():.0f}%")
                    fig_hist.update_layout(height=250, plot_bgcolor="white",
                        paper_bgcolor="white", margin=dict(t=40,b=20))
                    st.plotly_chart(fig_hist, use_container_width=True)

            # Top 3 élèves les plus actifs
            if "prenom" in dff.columns and len(dff) > 0:
                top_eleves = dff.groupby("prenom").agg(
                    sessions=("taux","count"),
                    taux_moy=("taux","mean")
                ).reset_index().sort_values("sessions", ascending=False).head(5)
                top_eleves.columns = ["Prénom","Sessions","Taux moyen %"]
                top_eleves["Taux moyen %"] = top_eleves["Taux moyen %"].round(1)
                st.markdown("**🏅 Élèves les plus actifs**")
                st.dataframe(top_eleves, use_container_width=True, hide_index=True,
                    column_config={
                        "Taux moyen %": st.column_config.ProgressColumn("Taux moyen %", min_value=0, max_value=100, format="%.1f %%")
                    })

            st.markdown("---")

            # ════════════════════════════════
            # EXPORTS
            # ════════════════════════════════
            ex1, ex2 = st.columns(2)
            with ex1:
                csv = dff[cols_affich].to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Exporter CSV (filtré)", csv,
                                   "sessions_pfe.csv", "text/csv",
                                   key="btn_export_csv2")
            with ex2:
                csv_all = df[cols_affich].to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Exporter tout (CSV complet)", csv_all,
                                   "sessions_pfe_complet.csv", "text/csv",
                                   key="btn_export_csv_all")