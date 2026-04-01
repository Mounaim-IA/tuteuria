from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
import os
import re
import uuid

load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURATION
# ============================================================
CHROMA_DIR = "chroma_db"
openai_key = os.getenv("OPENAI_API_KEY")

# ── GPT-4o + Validation Python ──────────────────────────────
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.2,
    api_key=openai_key,
    max_tokens=600
)

def get_vectorstore():
    embeddings = OpenAIEmbeddings(api_key=openai_key)
    if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        return Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings
        )
    return None

vectorstore = get_vectorstore()
retriever   = vectorstore.as_retriever(
    search_kwargs={"k": 4}
) if vectorstore else None

conversations = {}

# ============================================================
# CONFIGURATION PÉDAGOGIQUE
# ============================================================
NIVEAUX = {
    "1ère année": {"fr": "1ère année",  "ar": "السنة الأولى"},
    "2ème année": {"fr": "2ème année",  "ar": "السنة الثانية"},
    "3ème année": {"fr": "3ème année",  "ar": "السنة الثالثة"},
    "4ème année": {"fr": "4ème année",  "ar": "السنة الرابعة"},
    "5ème année": {"fr": "5ème année",  "ar": "السنة الخامسة"},
    "6ème année": {"fr": "6ème année",  "ar": "السنة السادسة"},
}

CHAPITRES = {
    "Addition":       {"fr": "Addition",       "ar": "الجمع"},
    "Soustraction":   {"fr": "Soustraction",   "ar": "الطرح"},
    "Multiplication": {"fr": "Multiplication", "ar": "الضرب"},
    "Fractions":      {"fr": "Fractions",      "ar": "الكسور"},
}

# ============================================================
# VALIDATION PYTHON — APRÈS GPT-4o
# ============================================================
def extraire_exercice(historique):
    """
    Extrait l'exercice du DERNIER message du tuteur.
    Utilise la DERNIÈRE occurrence de ✏️ ou 🎯
    pour éviter de confondre avec les emojis dans l'explication.
    """
    patterns = [
        (r'(\d+)\s*\+\s*(\d+)', '+'),
        (r'(\d+)\s*-\s*(\d+)',  '-'),
        (r'(\d+)\s*[×x\*]\s*(\d+)', '*'),
    ]
    for msg in reversed(historique):
        if isinstance(msg, AIMessage):
            texte = msg.content

            # Chercher la DERNIÈRE occurrence de ✏️ ou 🎯
            pos = -1
            if "✏️" in texte:
                pos = texte.rindex("✏️")  # rindex = dernière occurrence
            elif "🎯" in texte:
                pos = texte.rindex("🎯")  # rindex = dernière occurrence

            if pos >= 0:
                # Chercher UNIQUEMENT après la DERNIÈRE ✏️ ou 🎯
                texte_exercice = texte[pos:]
                for pattern, op in patterns:
                    match = re.search(pattern, texte_exercice)
                    if match:
                        a = int(match.group(1))
                        b = int(match.group(2))
                        if op == '+':
                            return (a, '+', b, a + b)
                        elif op == '-' and a >= b:
                            return (a, '-', b, a - b)
                        elif op == '*':
                            return (a, '*', b, a * b)
            break  # S'arrêter au premier message du tuteur
    return None


def verifier_reponse(user_message: str, historique: list):
    """
    Vérifie si la réponse de l'élève est correcte.
    Retourne : 'correct', 'incorrect:X', ou None
    """
    exercice = extraire_exercice(historique)
    if not exercice:
        return None

    a, op, b, resultat_attendu = exercice
    nombres = re.findall(r'\d+', user_message.strip())
    if not nombres:
        return None

    return 'correct' if int(nombres[0]) == resultat_attendu else f'incorrect:{resultat_attendu}'


def injecter_verdict(user_message: str, historique: list, langue: str) -> str:
    """
    Injecte le verdict Python dans le message AVANT GPT.
    GPT reçoit le verdict et génère une explication complète :
    1. Encourage
    2. Explique le calcul
    3. Donne la bonne réponse
    4. Donne un nouvel exercice
    """
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
                f"2. اشرح كيف نحسب الجواب خطوة بخطوة بأمثلة ملموسة\n"
                f"3. أعطِ الجواب الصحيح = {resultat}\n"
                f"4. أعطِ تمريناً جديداً مختلفاً وانتظر جواب الطالب]"
            )
        else:
            return (
                f"{user_message}\n[VERDICT PYTHON: INCORRECT ❌ — Résultat correct = {resultat}\n"
                f"1. Encourage l'élève avec douceur 😊\n"
                f"2. Explique comment calculer étape par étape avec des exemples concrets\n"
                f"3. Donne la bonne réponse = {resultat}\n"
                f"4. Donne un nouvel exercice différent et attends la réponse]"
            )


def nettoyer_reponse(reply: str) -> str:
    """
    Supprime les étiquettes d'étapes interdites
    et la notation LaTeX de la réponse GPT.
    """
    import re as re2

    # Supprimer étiquettes d'étapes
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
        reply = re2.sub(pattern, '', reply)

    # Supprimer notation LaTeX
    reply = re2.sub(r'\\\((.+?)\\\)', r'\1', reply)
    reply = re2.sub(r'\\\[(.+?)\\\]', r'\1', reply)

    return reply.strip()


def post_traitement(assistant_reply: str, user_message: str,
                    historique: list, langue: str) -> str:
    """
    1. Nettoie les étiquettes et LaTeX
    2. Dernier filet de sécurité : si GPT dit encore Bravo
       pour une réponse fausse, ajoute le bon verdict
       SANS supprimer son explication
    """
    # Nettoyer d'abord
    assistant_reply = nettoyer_reponse(assistant_reply)

    verdict = verifier_reponse(user_message, historique)
    if verdict is None or verdict == 'correct':
        return assistant_reply

    # Réponse INCORRECTE → GPT a-t-il quand même dit Bravo ?
    resultat_correct = verdict.split(':')[1]
    mots_fr = ['bravo', 'correct', 'exact', 'parfait', 'excellent', 'très bien', 'super', 'juste']
    mots_ar = ['أحسنت', 'صحيح', 'ممتاز', 'رائع', 'جيد']

    reply_lower  = assistant_reply.lower()
    gpt_a_valide = (
        any(m in reply_lower for m in mots_fr) or
        any(m in assistant_reply for m in mots_ar)
    )

    if gpt_a_valide:
        # GPT s'est trompé → on AJOUTE la correction en tête
        # SANS supprimer son explication et son exercice
        if langue == "العربية":
            correction = f"👏 أحسنت على المحاولة ! الجواب الصحيح هو **{resultat_correct}** 😊\n\n"
        else:
            correction = f"👏 C'est bien d'avoir essayé ! La bonne réponse est **{resultat_correct}** 😊\n\n"

        # Supprimer le "Bravo" de GPT et remplacer par notre correction
        import re as re3
        reply_sans_bravo = re3.sub(
            r'(🌟\s*)?(Bravo|Excellent|Parfait|Super|Correct|أحسنت|ممتاز)[^\n!]*[!.]?\s*',
            '', assistant_reply, count=1, flags=re3.IGNORECASE
        ).strip()

        return correction + reply_sans_bravo

    return assistant_reply



# ============================================================
# PROMPT — 9 RÈGLES TECHNOPÉDAGOGIQUES
# ============================================================
def get_system_prompt(niveau: str, chapitre_nom: str,
                      langue: str, context: str = "") -> str:

    # ── RAG ────────────────────────────────────────────────
    if context:
        rag_section = f"""
📚 BASE DE CONNAISSANCES :
─────────────────────────────────────────
{context}
─────────────────────────────────────────
Utilise UNIQUEMENT ces extraits pour tes exemples et exercices.
Ne génère JAMAIS de contenu hors de ces extraits.
"""
    else:
        rag_section = """
⚠️ Contenu non disponible pour ce chapitre.
Dis à l'élève : "Je n'ai pas encore ce contenu. Choisis un autre chapitre 📚"
"""

    # ── Messages selon la langue ────────────────────────────
    if langue == "العربية":
        r6_msg = f'قل : "لاحظت علامة من درس آخر. درسنا **{chapitre_nom}**. هل تريد الاستمرار ؟ نعم أو لا."'
        r6_oui = f'نعم → استأنف **{chapitre_nom}**'
        r6_non = '"اختر درساً آخر من القائمة 📚"'
        r7_hors = f'"أنا معلم الرياضيات فقط ! لنعد إلى **{chapitre_nom}** 🧮"'
        r7_chap = '"اختر هذا الدرس من القائمة 📚"'
        r7_niv  = '"😊 هذا النوع غير مقرر في مستواك ! ستتعلمه لاحقاً 📚"'
    else:
        r6_msg = f'Dis : "Je remarque un signe d\'un autre chapitre. Notre séance : **{chapitre_nom}**. Tu continues ? Oui ou Non."'
        r6_oui = f'Oui → reprends **{chapitre_nom}**'
        r6_non = '"Choisis un autre chapitre dans le menu 📚"'
        r7_hors = f'"Je suis ton tuteur de maths ! Revenons à **{chapitre_nom}** 🧮"'
        r7_chap = '"Choisis ce chapitre dans le menu 📚"'
        r7_niv  = '"😊 Ce type d\'opération n\'est pas prévu à ton niveau ! Tu le découvriras plus tard 📚"'

    return f"""Tu es un tuteur de mathématiques pour enfants du cycle primaire.
Niveau : **{niveau}** | Chapitre : **{chapitre_nom}** | Langue : **{langue}**

{rag_section}

════════════════════════════════
RÈGLES ABSOLUES — LIRE EN PREMIER
════════════════════════════════

1. JAMAIS de LaTeX : écris 3 + 4 = 7, JAMAIS \(3+4\) ou \[3+4\]
2. JAMAIS le nom ou numéro d'étape : ❌ "Étape 3" ❌ "ÉTAPE 0" ❌ "📖 EXPLICATION :"
3. JAMAIS "Bravo" si l'élève n'a pas répondu à un exercice posé par toi.
   Si l'élève écrit un calcul spontané (ex: "3-3", "5+2") →
   COMMENCE la séquence depuis l'explication sur **{chapitre_nom}** UNIQUEMENT.
   ✅ "3-3" + chapitre=Soustraction → explique la Soustraction
   ❌ "3-3" + chapitre=Soustraction → explique l'Addition (INTERDIT !)
4. TOUJOURS UN SEUL exemple dans l'explication. JAMAIS deux.
5. Chiffres arabes uniquement : 0-9. JAMAIS ١٢٣

════════════════════════════════
SÉQUENCE PÉDAGOGIQUE (ordre strict)
════════════════════════════════

📖 EXPLICATION (toujours en premier) :
→ Explique **{chapitre_nom}** avec UN objet concret + emojis
→ UN seul exemple avec des nombres ex: "5 - 2 = 3"
→ Termine : "Tu as compris ? 😊 On essaie !"

✏️ EXERCICE 1 (vérification) :
→ Pose UNIQUEMENT la question, rien d'autre
→ "✏️ À toi ! Combien font [a] [op] [b] ? 😊"
→ Nombres DIFFÉRENTS de l'exemple
→ ATTENDS la réponse sans rien ajouter

📝 CORRECTION :
→ Si le message contient [VERDICT PYTHON: CORRECT] → dis "🌟 Bravo ! Tu es fort(e) ! [explication]"
→ Si le message contient [VERDICT PYTHON: INCORRECT = X] → dis "👏 C'est bien d'avoir essayé ! La bonne réponse est X. [explication douce]"
→ Si pas de verdict Python → calcule toi-même avant de juger
→ JAMAIS "Bravo" si la réponse est fausse

✏️ EXERCICE 2 (application) :
→ Pose UNIQUEMENT la question
→ "✏️ À toi ! Combien font [a] [op] [b] ? 😊"
→ Si correct → Quiz | Si incorrect → Encourage + nouvel exercice

🎯 QUIZ (2-3 questions une par une) :
→ "🎯 Question [n] : Combien font [a] [op] [b] ?"
→ ATTENDS la réponse avant la suivante

🏆 CONCLUSION :
"🏆 Félicitations ! Tu as terminé ta séance sur **{chapitre_nom}** ! 😊
Qu'est-ce que tu veux faire ?
  1️⃣ Autre exercice sur **{chapitre_nom}**
  2️⃣ Passer à un autre chapitre"

════════════════════════════════
RÈGLES DE CONTENU
════════════════════════════════

🔴 Résultats négatifs : Python gère déjà ce cas automatiquement.
   Ne propose JAMAIS un exercice a-b si a < b.
   Ex: 8-3 ✅ | 3-8 ❌

🔴 Décimaux selon le niveau :
→ 1ère/2ème/3ème : interdits → STOP + "👏 Tu découvriras les décimaux en 4ème année 📚 Continue avec les entiers, tu avances très bien ! 💪"
→ 4ème : lecture/écriture seulement → si opérations → STOP + "👏 Les opérations sur les décimaux t'attendent en 5ème 📚 💪"
→ 5ème : +/- seulement → si ×/÷ → STOP + "👏 ×/÷ des décimaux t'attendent en 6ème 📚 💪"
→ 6ème : tout autorisé ✅

🔴 Signe _ : n'est PAS une soustraction → "👋 Utilise - pour soustraire, comme : 3 - 2 😊"

🔴 Opération incomplète (3+, 5-) : "😊 Il manque un nombre ! Écris par exemple : 3 + 4. Complète et on continue ! 💪"

🔴 Signe incompatible : {r6_msg}
   → STOP après cette question. N'explique RIEN. ATTENDS Oui ou Non.
   → Si Oui : reprends la séquence sur **{chapitre_nom}**
   → Si Non : "Super ! Choisis un autre chapitre dans le menu 📚"

════════════════════════════════
LANGUE ET TON
════════════════════════════════
→ Réponds UNIQUEMENT en **{langue}**
→ Bascule FR/AR immédiatement si l'élève change de langue
→ Toujours bienveillant, encourageant, doux avec les enfants
→ Si message incompréhensible : "👋 Bonjour ! Tu veux commencer la leçon sur **{chapitre_nom}** ? Écris 'Oui' ! 😊"
"""


# ============================================================
# DÉTECTION RÉSULTAT NÉGATIF — PAR PYTHON (avant GPT)
# ============================================================
def detecter_resultat_negatif(message: str):
    """
    Détecte si l'élève propose une soustraction à résultat négatif.
    Ex: "2-8" ou "3-9" → résultat négatif
    Ex: "8-2" ou "9-3" → résultat positif → OK
    Retourne True si négatif, False sinon.
    """
    match = re.search(r'(\d+)\s*-\s*(\d+)', message)
    if match:
        a = int(match.group(1))
        b = int(match.group(2))
        if a < b:  # résultat négatif
            return True
    return False


def message_negatif(langue: str) -> str:
    if langue == "العربية":
        return (
            "👏 يا لها من فضول رائع ! لكن في الابتدائي، "
            "نشتغل فقط مع النتائج الموجبة 😊\n"
            "ستكتشف هذا النوع في الإعدادي 📚\n"
            "جرب أن يكون العدد الأول أكبر ! 💪"
        )
    else:
        return (
            "👏 Quelle bonne curiosité ! Mais en primaire, "
            "on travaille avec des résultats positifs 😊\n"
            "Tu découvriras ça au collège 📚\n"
            "Essaie avec un plus grand nombre en premier ! 💪"
        )


# Signes par chapitre
SIGNES_CHAPITRES = {
    "Addition":       ["+"],
    "Soustraction":   ["-"],
    "Multiplication": ["×", "*", "x"],
    "Fractions":      ["/", "÷"],
}

def detecter_signe_incompatible(message: str, chapitre_cle: str, langue: str):
    """
    Détecte si l'élève utilise un signe d'un autre chapitre.
    Retourne le message R6 si incompatible, None sinon.
    """
    msg = message.lower().strip()

    # Signes compatibles avec le chapitre actuel
    signes_ok = SIGNES_CHAPITRES.get(chapitre_cle, [])

    # Vérifier si un signe incompatible est présent
    for chap, signes in SIGNES_CHAPITRES.items():
        if chap == chapitre_cle:
            continue
        for signe in signes:
            if signe in msg:
                # Signe incompatible trouvé !
                chap_fr = {"Addition": "Addition", "Soustraction": "Soustraction",
                           "Multiplication": "Multiplication", "Fractions": "Fractions"}
                chap_ar = {"Addition": "الجمع", "Soustraction": "الطرح",
                           "Multiplication": "الضرب", "Fractions": "الكسور"}
                nom_chap = chap_ar[chapitre_cle] if langue == "العربية" else chap_fr[chapitre_cle]

                if langue == "العربية":
                    return (
                        f"😊 لاحظت أنك تستخدم علامة من درس آخر !\n"
                        f"درسنا اليوم هو **{nom_chap}**.\n"
                        f"هل تريد الاستمرار مع **{nom_chap}** ؟\n"
                        f"أجب بـ **نعم** أو **لا** 😊"
                    )
                else:
                    return (
                        f"😊 Je remarque que tu utilises un signe d'un autre chapitre !\n"
                        f"Notre séance porte sur **{nom_chap}**.\n"
                        f"Tu veux continuer avec **{nom_chap}** ?\n"
                        f"Réponds par **Oui** ou **Non** 😊"
                    )
    return None


# ============================================================
# ROUTES FLASK
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data         = request.json
        user_message = data.get('message', '')
        session_id   = data.get('session_id', str(uuid.uuid4()))
        niveau_cle   = data.get('niveau', '3ème année')
        chapitre_cle = data.get('chapitre', 'Addition')
        langue       = data.get('langue', 'Français')

        if not user_message:
            return jsonify({"error": "Message vide"}), 400

        # ── Noms FR/AR ──────────────────────────────────────
        niveau_info   = NIVEAUX.get(niveau_cle, NIVEAUX["3ème année"])
        chapitre_info = CHAPITRES.get(chapitre_cle, CHAPITRES["Addition"])
        niveau_nom    = niveau_info["ar"]   if langue == "العربية" else niveau_info["fr"]
        chapitre_nom  = chapitre_info["ar"] if langue == "العربية" else chapitre_info["fr"]

        # ── RAG ─────────────────────────────────────────────
        context = ""
        if retriever:
            query   = f"{chapitre_cle} {niveau_cle} {user_message}"
            docs    = retriever.invoke(query)
            context = "\n\n".join([d.page_content for d in docs])

        # ── Historique ──────────────────────────────────────
        if session_id not in conversations:
            conversations[session_id] = []
        history = conversations[session_id][-10:]

        # ── Détection résultat négatif — Python AVANT GPT ──
        # UNIQUEMENT pour le chapitre Soustraction !
        if chapitre_cle == "Soustraction" and detecter_resultat_negatif(user_message):
            reply = message_negatif(langue)
            conversations[session_id].append(HumanMessage(content=user_message))
            conversations[session_id].append(AIMessage(content=reply))
            return jsonify({
                "response": reply, "session_id": session_id,
                "etape": "amorce", "rag_used": False, "status": "success"
            })

        # ── Détection signe incompatible — Python AVANT GPT ─
        signe_incompatible = detecter_signe_incompatible(user_message, chapitre_cle, langue)
        if signe_incompatible:
            conversations[session_id].append(HumanMessage(content=user_message))
            conversations[session_id].append(AIMessage(content=signe_incompatible))
            return jsonify({
                "response": signe_incompatible, "session_id": session_id,
                "etape": "amorce", "rag_used": False, "status": "success"
            })

        # ── Prompt ──────────────────────────────────────────
        system_prompt = get_system_prompt(
            niveau_nom, chapitre_nom, langue, context
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])

        # ── Injection verdict Python AVANT GPT ───────────────
        message_avec_verdict = injecter_verdict(user_message, history, langue)

        # ── Appel GPT-4o ─────────────────────────────────────
        response        = (prompt | llm).invoke({
            "input":        message_avec_verdict,
            "chat_history": history
        })
        assistant_reply = response.content

        # ── Nettoyage + validation Python APRÈS GPT-4o ───────
        assistant_reply = post_traitement(
            assistant_reply, user_message, history, langue
        )

        # ── Détection étape ─────────────────────────────────
        etape       = "amorce"
        reply_lower = assistant_reply.lower()
        if "✏️" in assistant_reply or "exercice" in reply_lower or "تمرين" in assistant_reply:
            etape = "exercice"
        elif "🎯" in assistant_reply or "quiz" in reply_lower or "اختبار" in assistant_reply:
            etape = "quiz"
        elif "🏆" in assistant_reply or "félicitations" in reply_lower or "أحسنت" in assistant_reply:
            etape = "felicitations"
        elif "🌟" in assistant_reply:
            etape = "encouragement"

        # ── Sauvegarde ──────────────────────────────────────
        conversations[session_id].append(HumanMessage(content=user_message))
        conversations[session_id].append(AIMessage(content=assistant_reply))

        return jsonify({
            "response":   assistant_reply,
            "session_id": session_id,
            "etape":      etape,
            "rag_used":   bool(context),
            "status":     "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/reset', methods=['POST'])
def reset():
    try:
        data = request.json
        sid  = data.get('session_id')
        if sid in conversations:
            del conversations[sid]
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status":     "✅ API Flask opérationnelle !",
        "model":      "gpt-4o",
        "validation": "✅ Validation Python après GPT-4o",
        "rag":        "✅ Activé" if retriever else "❌ Non initialisé",
        "langues":    ["Français", "العربية"],
        "niveaux":    list(NIVEAUX.keys()),
        "chapitres":  list(CHAPITRES.keys()),
    })


if __name__ == '__main__':
    print("=" * 55)
    print("🧮  TUTEUR MATHS PRIMAIRE")
    print("    ✅ GPT-4o")
    print("    ✅ Validation Python après GPT-4o")
    print("    ✅ 9 Règles Technopédagogiques")
    print("    PFE FSE Rabat")
    print("=" * 55)
    if not retriever:
        print("⚠️  Lance d'abord : python init_rag.py")
    else:
        print("✅  RAG chargé avec succès !")
    print("🌐  Accès : http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
