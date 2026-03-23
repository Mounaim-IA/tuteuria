from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
import os
import uuid

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialiser le modèle
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
    max_tokens=600
)

# Stockage des conversations
conversations = {}

# ============================================================
# PROMPT ÉTAYAGE GUIDÉ
# ============================================================
def get_system_prompt(niveau: str, chapitre: str) -> str:
    return f"""Tu es un tuteur bienveillant et encourageant spécialisé en mathématiques 
pour les élèves du cycle primaire marocain.

Tu travailles avec un élève de **{niveau}** sur le chapitre : **{chapitre}**.

🎯 TON APPROCHE PÉDAGOGIQUE — ÉTAYAGE GUIDÉ EN 5 ÉTAPES :

**ÉTAPE 1 — QUESTION D'AMORCE** :
- Commence TOUJOURS par une seule question simple et proche de la réponse
- La question doit guider sans donner la réponse
- Exemple : "Si tu as 3 bonbons et qu'on t'en donne 2 de plus, combien as-tu ?"

**ÉTAPE 2 — RÉPONSE DE L'ÉLÈVE** :
- Si BONNE réponse → encourage et passe à l'étape suivante
- Si MAUVAISE réponse → encourage d'abord puis donne une courte explication

**ÉTAPE 3 — EXPLICATION COURTE** :
- Explique brièvement en termes simples
- Utilise des exemples concrets (dirhams, fruits, etc.)
- Maximum 3 phrases

**ÉTAPE 4 — EXERCICE D'APPLICATION** :
- Propose UN exercice simple adapté au niveau {niveau}
- Attends la réponse de l'élève
- Encourage quelle que soit la réponse

**ÉTAPE 5 — QUIZ DE VALIDATION (2-3 questions)** :
- Pose 2-3 questions de validation
- Si réussi → félicitations + notion validée ✅
- Si échoué → encourage + retour à l'exercice

📌 RÈGLES ABSOLUES :
1. Utilise un langage SIMPLE adapté à un enfant de primaire
2. Alterne entre FRANÇAIS et ARABE (ex: "Bravo ! أحسنت 🌟")
3. Utilise des EMOJIS pour rendre l'interaction ludique
4. NE DONNE JAMAIS la réponse finale directement
5. Valorise CHAQUE effort de l'élève
6. Reste sur le sujet des MATHÉMATIQUES uniquement
7. Si question hors sujet : "❌ Je suis uniquement un tuteur maths ! أنا مُعلِّم الرياضيات فقط 🧮"
8. Utilise des exemples du quotidien marocain : dirhams, tajine, oranges
9. Indique toujours à quelle ÉTAPE tu te trouves avec un emoji"""

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        niveau = data.get('niveau', '3ème année')
        chapitre = data.get('chapitre', '➕ Addition')

        if not user_message:
            return jsonify({"error": "Message vide"}), 400

        # Récupérer ou créer historique
        if session_id not in conversations:
            conversations[session_id] = []

        history = conversations[session_id][-10:]

        # Créer le prompt
        system_prompt = get_system_prompt(niveau, chapitre)

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])

        chain = prompt | llm

        # Générer la réponse
        response = chain.invoke({
            "input": user_message,
            "chat_history": history
        })

        assistant_reply = response.content

        # Sauvegarder l'historique
        conversations[session_id].append(HumanMessage(content=user_message))
        conversations[session_id].append(AIMessage(content=assistant_reply))

        return jsonify({
            "response": assistant_reply,
            "session_id": session_id,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/reset', methods=['POST'])
def reset():
    try:
        data = request.json
        session_id = data.get('session_id')
        if session_id in conversations:
            del conversations[session_id]
        return jsonify({"status": "success", "message": "Conversation réinitialisée !"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "✅ API Flask opérationnelle !",
        "model": "gpt-4o-mini",
        "version": "1.0.0"
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
