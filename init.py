"""
Script d'initialisation de la base de données RAG
Tuteur Maths Primaire Marocain — PFE FSE Rabat
Sources : Fichiers locaux + Sites web libres et fiables
Version : 2.0
"""

import os
import shutil
import time
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================
DATABASE_DIR = "database"
CHROMA_DIR   = "chroma_db"
api_key      = os.getenv("OPENAI_API_KEY")

# ============================================================
# URLs EXACTES PAR CHAPITRE ET PAR SITE
# ============================================================
URLS_WEB = {

    "Addition": [
        # ── SOUTIEN67 — Cours théoriques par niveau ──────────
        "https://soutien67.fr/math/niv01/theorie/pages/calcul_01.htm",
        "https://soutien67.fr/math/niv02/theorie/pages/calcul_02.htm",
        "https://soutien67.fr/math/niv03/theorie/pages/calcul_03.htm",
        "https://soutien67.fr/math/niv04/theorie/pages/calcul_04.htm",
        # ── ALLOPROF ──────────────────────────────────────────
        "https://www.alloprof.qc.ca/fr/eleves/bv/mathematiques/l-addition-k1025",
        # ── ILEMATHS ──────────────────────────────────────────
        "https://www.ilemaths.net/sujet-addition-primaire.html",
        # ── RECREAKIDZ ────────────────────────────────────────
        "https://www.recreakidz.com/lecons-exercices/maths/addition",
        # ── LUMNI ─────────────────────────────────────────────
        "https://www.lumni.fr/article/l-addition",
        # ── FICHESPEDAGOGIQUES ────────────────────────────────
    ],

    "Soustraction": [
        # ── SOUTIEN67 ─────────────────────────────────────────
        "https://soutien67.fr/math/niv01/theorie/pages/calcul_01.htm",
        "https://soutien67.fr/math/niv02/theorie/pages/calcul_02.htm",
        "https://soutien67.fr/math/niv03/theorie/pages/calcul_03.htm",
        "https://soutien67.fr/math/niv04/theorie/pages/calcul_04.htm",
        # ── ALLOPROF ──────────────────────────────────────────
        "https://www.alloprof.qc.ca/fr/eleves/bv/mathematiques/la-soustraction-k1026",
        # ── ILEMATHS ──────────────────────────────────────────
        "https://www.ilemaths.net/sujet-soustraction-primaire.html",
        # ── RECREAKIDZ ────────────────────────────────────────
        "https://www.recreakidz.com/lecons-exercices/maths/soustraction",
        # ── LUMNI ─────────────────────────────────────────────
        "https://www.lumni.fr/article/la-soustraction",
        # ── FICHESPEDAGOGIQUES ────────────────────────────────
    ],

    "Multiplication": [
        # ── SOUTIEN67 ─────────────────────────────────────────
        "https://soutien67.fr/math/niv02/theorie/pages/calcul_02.htm",
        "https://soutien67.fr/math/niv03/theorie/pages/calcul_03.htm",
        "https://soutien67.fr/math/niv04/theorie/pages/calcul_04.htm",
        # ── ALLOPROF ──────────────────────────────────────────
        "https://www.alloprof.qc.ca/fr/eleves/bv/mathematiques/la-multiplication-k1027",
        # ── ILEMATHS ──────────────────────────────────────────
        "https://www.ilemaths.net/sujet-multiplication-primaire.html",
        # ── RECREAKIDZ ────────────────────────────────────────
        "https://www.recreakidz.com/lecons-exercices/maths/multiplication",
        # ── LUMNI ─────────────────────────────────────────────
        "https://www.lumni.fr/article/la-multiplication",
        # ── FICHESPEDAGOGIQUES ────────────────────────────────
    ],

    "Fractions": [
        # ── SOUTIEN67 ─────────────────────────────────────────
        "https://soutien67.fr/math/niv04/theorie/pages/numeration_04.htm",
        "https://soutien67.fr/math/niv04/theorie/pages/calcul_04.htm",
        # ── ALLOPROF ──────────────────────────────────────────
        "https://www.alloprof.qc.ca/fr/eleves/bv/mathematiques/les-fractions-k1028",
        # ── ILEMATHS ──────────────────────────────────────────
        "https://www.ilemaths.net/sujet-fractions-primaire.html",
        # ── RECREAKIDZ ────────────────────────────────────────
        "https://www.recreakidz.com/lecons-exercices/maths/fractions",
        # ── LUMNI ─────────────────────────────────────────────
        "https://www.lumni.fr/article/les-fractions",
        # ── FICHESPEDAGOGIQUES ────────────────────────────────
    ],
}


# ============================================================
# 1. CHARGEMENT DES FICHIERS LOCAUX
# ============================================================
def load_local_files():
    print("\n📁 Chargement des fichiers locaux (programme marocain)...")

    fichiers = [
        ("addition.txt",       "Addition"),
        ("soustraction.txt",   "Soustraction"),
        ("multiplication.txt", "Multiplication"),
        ("fractions.txt",      "Fractions"),
    ]

    documents = []
    for fichier, chapitre in fichiers:
        chemin = os.path.join(DATABASE_DIR, fichier)
        if os.path.exists(chemin):
            loader = TextLoader(chemin, encoding="utf-8")
            docs   = loader.load()
            for doc in docs:
                doc.metadata["source"]   = f"Programme officiel marocain — {chapitre}"
                doc.metadata["chapitre"] = chapitre
                doc.metadata["type"]     = "local"
                doc.metadata["priorite"] = "1"
            documents.extend(docs)
            print(f"  ✅ {fichier} — {chapitre} ({len(docs)} doc)")
        else:
            print(f"  ❌ {fichier} introuvable dans '{DATABASE_DIR}/'")

    # PDFs optionnels
    pdf_dir = os.path.join(DATABASE_DIR, "pdf")
    if os.path.exists(pdf_dir):
        for pdf_file in os.listdir(pdf_dir):
            if pdf_file.endswith(".pdf"):
                try:
                    loader = PyPDFLoader(os.path.join(pdf_dir, pdf_file))
                    docs   = loader.load()
                    for doc in docs:
                        doc.metadata["type"]     = "pdf"
                        doc.metadata["priorite"] = "1"
                    documents.extend(docs)
                    print(f"  ✅ {pdf_file} (PDF) — {len(docs)} pages")
                except Exception as e:
                    print(f"  ⚠️ Erreur PDF {pdf_file} : {e}")

    print(f"\n  📊 Total fichiers locaux : {len(documents)} document(s)")
    return documents


# ============================================================
# 2. CHARGEMENT DES SOURCES WEB
# ============================================================
def load_web_sources():
    print("\n🌐 Chargement des sources web...")
    documents = []
    total_ok  = 0
    total_err = 0
    urls_vues = set()  # Éviter les doublons

    for chapitre, urls in URLS_WEB.items():
        print(f"\n  📚 Chapitre : {chapitre}")
        for url in urls:

            # Éviter les doublons
            if url in urls_vues:
                print(f"    ⏭️  Déjà chargée : {url.split('/')[2]}")
                continue
            urls_vues.add(url)

            try:
                time.sleep(1.5)  # Pause pour éviter blocage
                loader = WebBaseLoader([url])
                docs = loader.load()

                for doc in docs:
                    doc.metadata["source"]   = url
                    doc.metadata["chapitre"] = chapitre
                    doc.metadata["type"]     = "web"
                    doc.metadata["priorite"] = "2"
                    doc.page_content = " ".join(doc.page_content.split())

                docs_valides = [d for d in docs if len(d.page_content) > 200]

                if docs_valides:
                    documents.extend(docs_valides)
                    site = url.split("/")[2]
                    print(f"    ✅ [{site}] {len(docs_valides)} doc(s)")
                    total_ok += 1
                else:
                    print(f"    ⚠️  Contenu insuffisant : {url[:50]}")

            except Exception as e:
                print(f"    ❌ Erreur : {url[:50]} — {str(e)[:40]}")
                total_err += 1

    print(f"\n  📊 Sites OK : {total_ok} ✅ | Échecs : {total_err} ❌")
    return documents


# ============================================================
# 3. CRÉATION DU VECTORSTORE
# ============================================================
def create_vectorstore(force=False):
    print("\n" + "=" * 60)
    print("🔧 CRÉATION DU VECTORSTORE CHROMADB")
    print("   Sources : Fichiers locaux + 6 sites web fiables")
    print("=" * 60)

    if force and os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        print(f"\n🗑️  Ancien vectorstore supprimé")

    docs_local = load_local_files()
    docs_web   = load_web_sources()
    documents  = docs_local + docs_web  # Local EN PREMIER = priorité maximale

    print(f"\n{'='*60}")
    print(f"📊 BILAN FINAL :")
    print(f"   Fichiers locaux : {len(docs_local)} document(s)")
    print(f"   Sources web     : {len(docs_web)} document(s)")
    print(f"   TOTAL           : {len(documents)} document(s)")
    print(f"{'='*60}")

    if not documents:
        print("❌ Aucun document chargé !")
        return None

    # Découpage en chunks
    print("\n✂️  Découpage en chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(documents)

    chunks_local = [c for c in chunks if c.metadata.get("type") == "local"]
    chunks_web   = [c for c in chunks if c.metadata.get("type") == "web"]
    print(f"   Chunks locaux : {len(chunks_local)}")
    print(f"   Chunks web    : {len(chunks_web)}")
    print(f"   TOTAL chunks  : {len(chunks)}")

    # Embeddings + ChromaDB
    print("\n🧠 Création des embeddings OpenAI...")
    embeddings = OpenAIEmbeddings(api_key=api_key)

    print("💾 Indexation dans ChromaDB...")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    print(f"\n✅ {len(chunks)} chunks indexés dans '{CHROMA_DIR}/'")
    return vectorstore


# ============================================================
# 4. TEST DU RAG
# ============================================================
def test_rag():
    print("\n" + "=" * 60)
    print("🧪 TEST DU RAG — 4 chapitres")
    print("=" * 60)

    embeddings  = OpenAIEmbeddings(api_key=api_key)
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    tests = [
        ("Addition",       "Comment faire une addition avec retenue ?"),
        ("Soustraction",   "Soustraction avec emprunt 3ème année"),
        ("Multiplication", "Table de multiplication de 7"),
        ("Fractions",      "Comment simplifier une fraction ?"),
    ]

    tous_ok = True
    for chapitre, question in tests:
        docs    = retriever.invoke(f"{chapitre} {question}")
        ok      = len(docs) > 0
        tous_ok = tous_ok and ok
        statut  = "✅" if ok else "❌"

        if docs:
            src  = docs[0].metadata.get("source", "?")
            type_ = docs[0].metadata.get("type", "?")
            info = "📁 Programme marocain" if type_ == "local" else f"🌐 {src.split('/')[2] if 'http' in src else src}"
        else:
            info = "❌ rien trouvé"

        print(f"\n  {statut} [{chapitre}]")
        print(f"     Source  : {info}")
        if docs:
            print(f"     Extrait : {docs[0].page_content[:100]}...")

    print(f"\n{'='*60}")
    print("✅ Tous les chapitres OK !" if tous_ok else "⚠️  Certains chapitres ont des problèmes.")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🧮  INITIALISATION RAG — TUTEUR MATHS PRIMAIRE")
    print("    PFE FSE Rabat | 2025-2026")
    print("    Sources locales + soutien67 + alloprof +")
    print("    ilemaths + recreakidz + lumni + fichespedago")
    print("=" * 60)

    if not api_key:
        print("❌ OPENAI_API_KEY manquante dans .env !")
        exit(1)

    if not os.path.exists(DATABASE_DIR):
        print(f"❌ Dossier '{DATABASE_DIR}/' introuvable !")
        exit(1)

    vs = create_vectorstore(force=True)

    if vs:
        test_rag()
        print("\n" + "=" * 60)
        print("✅  RAG initialisé avec succès !")
        print("🚀  Lance maintenant : python app_rag.py")
        print("🌐  Accès : http://localhost:5000")
        print("=" * 60)
    else:
        print("\n❌ Échec de l'initialisation du RAG.")
