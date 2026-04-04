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

# Limite à 200 sessions max pour éviter la fuite mémoire
MAX_SESSIONS = 200
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
# VALIDATION PYTHON — COUCHE 1 : EXTRACTION EXERCICE
# ============================================================
def extraire_exercice(historique):
    """
    Cherche l'exercice après la DERNIÈRE occurrence de ✏️ ou 🎯
    dans le dernier message du tuteur.
    → rindex évite de confondre avec les emojis dans l'explication.
    """
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
                pos = texte.rindex("✏️")  # DERNIÈRE occurrence ✅
            elif "🎯" in texte:
                pos = texte.rindex("🎯")  # DERNIÈRE occurrence ✅
            if pos >= 0:
                texte_exercice = texte[pos:]
                for pattern, op in patterns:
                    match = re.search(pattern, texte_exercice)
                    if match:
                        a, b = int(match.group(1)), int(match.group(2))
                        if op == '+': return (a, '+', b, a + b)
                        if op == '-' and a >= b: return (a, '-', b, a - b)
                        if op == '*': return (a, '*', b, a * b)
            break
    return None


# ============================================================
# VALIDATION PYTHON — COUCHE 2 : VÉRIFICATION RÉPONSE
# ============================================================
def verifier_reponse(user_message: str, historique: list):
    """
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


# ============================================================
# VALIDATION PYTHON — COUCHE 3 : INJECTION VERDICT AVANT GPT
# ============================================================
def injecter_verdict(user_message: str, historique: list, langue: str) -> str:
    """
    Injecte le verdict Python dans le message AVANT GPT.
    GPT reçoit le verdict et génère une explication complète.
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


# ============================================================
# VALIDATION PYTHON — COUCHE 4 : NETTOYAGE RÉPONSE GPT
# ============================================================
def nettoyer_reponse(reply: str) -> str:
    """
    Supprime les étiquettes d'étapes interdites et la notation LaTeX.
    """
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
    # Supprimer notation LaTeX
    reply = re.sub(r'\\\((.+?)\\\)', r'\1', reply)
    reply = re.sub(r'\\\[(.+?)\\\]', r'\1', reply)
    return reply.strip()


# ============================================================
# VALIDATION PYTHON — COUCHE 5 : POST-TRAITEMENT APRÈS GPT
# ============================================================
def post_traitement(assistant_reply: str, user_message: str,
                    historique: list, langue: str) -> str:
    """
    Dernier filet de sécurité :
    1. Nettoie LaTeX et noms d'étapes
    2. Si GPT valide une réponse fausse → corrige en gardant son explication
    """
    assistant_reply = nettoyer_reponse(assistant_reply)

    verdict = verifier_reponse(user_message, historique)
    if verdict is None or verdict == 'correct':
        return assistant_reply

    resultat_correct = verdict.split(':')[1]
    mots_fr = ['bravo', 'correct', 'exact', 'parfait', 'excellent', 'très bien', 'super', 'juste']
    mots_ar = ['أحسنت', 'صحيح', 'ممتاز', 'رائع', 'جيد']

    reply_lower  = assistant_reply.lower()
    gpt_a_valide = (
        any(m in reply_lower for m in mots_fr) or
        any(m in assistant_reply for m in mots_ar)
    )

    if gpt_a_valide:
        # Supprimer le "Bravo" de GPT et ajouter la correction
        reply_sans_bravo = re.sub(
            r'(🌟\s*)?(Bravo|Excellent|Parfait|Super|Correct|أحسنت|ممتاز)[^\n!]*[!.]?\s*',
            '', assistant_reply, count=1, flags=re.IGNORECASE
        ).strip()

        if langue == "العربية":
            correction = f"👏 أحسنت على المحاولة ! الجواب الصحيح هو **{resultat_correct}** 😊\n\n"
        else:
            correction = f"👏 C'est bien d'avoir essayé ! La bonne réponse est **{resultat_correct}** 😊\n\n"

        return correction + reply_sans_bravo

    return assistant_reply


# ============================================================
# DÉTECTION RÉSULTAT NÉGATIF — PYTHON AVANT GPT
# ============================================================
def detecter_resultat_negatif(message: str) -> bool:
    """Détecte une soustraction à résultat négatif (a < b)."""
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


# ============================================================
# DÉTECTION SIGNE INCOMPATIBLE — PYTHON AVANT GPT
# ============================================================
def detecter_signe_incompatible(message: str, chapitre_cle: str, langue: str):
    """
    Détecte si l'élève utilise un signe d'un autre chapitre.
    Regex précise pour éviter les faux positifs (ex: 'x' dans 'veux').
    """
    msg = message.lower().strip()

    # Mots autorisés → laisser GPT gérer
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
# PROMPT — 9 RÈGLES TECHNOPÉDAGOGIQUES
# ============================================================
def get_system_prompt(niveau: str, chapitre_nom: str,
                      langue: str, context: str = "") -> str:

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
   Si l'élève écrit un calcul spontané → COMMENCE la séquence depuis l'explication.
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
   Ne propose JAMAIS un exercice a-b si a < b.

🔴 Décimaux selon le niveau :
→ 1ère/2ème/3ème : interdits → STOP + "👏 Tu découvriras les décimaux en 4ème année 📚 Tu avances très bien ! 💪"
→ 4ème : lecture/écriture seulement → si opérations → STOP + "👏 Les opérations décimaux t'attendent en 5ème 📚 💪"
→ 5ème : +/- seulement → si ×/÷ → STOP + "👏 ×/÷ des décimaux t'attendent en 6ème 📚 💪"
→ 6ème : tout autorisé ✅

🔴 Signe _ : n'est PAS une soustraction → "👋 Utilise - pour soustraire : 3 - 2 😊"
🔴 Opération incomplète (3+, 5-) : "😊 Il manque un nombre ! Écris par exemple : 3 + 4 💪"
🔴 Signe incompatible : {r6_msg}
   → STOP. ATTENDS Oui ou Non.
   → Si Oui : {r6_oui}
   → Si Non : {r6_non}

════════════════════════════════
LANGUE ET TON
════════════════════════════════
→ Réponds UNIQUEMENT en **{langue}**
→ Bascule FR/AR immédiatement si l'élève change de langue
→ Toujours bienveillant, encourageant, doux avec les enfants
→ Si message incompréhensible : "👋 Bonjour ! Tu veux commencer la leçon sur **{chapitre_nom}** ? Écris 'Oui' ! 😊"
→ Hors maths : {r7_hors}
→ Autre chapitre : {r7_chap}
→ Hors niveau : {r7_niv}

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
Tuteur : "👏 Quelle curiosité ! En primaire, on travaille avec des résultats positifs 😊 Tu découvriras cela au collège 📚 Essaie avec un plus grand nombre en premier ! 💪"

4. OPÉRATION INCOMPLÈTE :
Élève : "8 +"
Tuteur : "😊 Il manque un nombre ! Écris par exemple 8 + 4. Complète et on continue ! 💪"
"""


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

        # ── Gestion sessions (limite mémoire) ───────────────
        if len(conversations) >= MAX_SESSIONS:
            oldest = next(iter(conversations))
            del conversations[oldest]
        if session_id not in conversations:
            conversations[session_id] = []
        history = conversations[session_id][-10:]

        # ── Détection résultat négatif — Python AVANT GPT ──
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
        system_prompt = get_system_prompt(niveau_nom, chapitre_nom, langue, context)
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

        # ── Nettoyage + validation Python APRÈS GPT ──────────
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
        "validation": "✅ Triple couche Python",
        "rag":        "✅ Activé" if retriever else "❌ Non initialisé",
        "sessions":   len(conversations),
        "langues":    ["Français", "العربية"],
        "niveaux":    list(NIVEAUX.keys()),
        "chapitres":  list(CHAPITRES.keys()),
    })


if __name__ == '__main__':
    print("=" * 55)
    print("🧮  TUTEUR MATHS PRIMAIRE — Flask + RAG")
    print("    ✅ GPT-4o | ✅ Validation Python triple couche")
    print("    ✅ 9 Règles Technopédagogiques | PFE FSE Rabat")
    print("=" * 55)
    if not retriever:
        print("⚠️  Lance d'abord : python init_rag.py")
    else:
        print("✅  RAG chargé avec succès !")
    print("🌐  Accès : http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
