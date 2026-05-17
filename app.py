import streamlit as st
import os
import json
import base64
from datetime import datetime
from recipe_processor import RecipeProcessor
from rag_pipeline import RAGPipeline
from built_in_recipes import BUILT_IN_RECIPES


@st.cache_data
def img_to_data_uri(path: str) -> str:
    """Read a local image and return a base64 data URI for use in <img src>."""
    if not path or not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(ext, "jpeg")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/{mime};base64,{data}"


try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


st.set_page_config(page_title="RecipeAI", page_icon="🤖", layout="wide")

with open("style.css", "r", encoding="utf-8") as css_file:
    st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)


if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user' not in st.session_state: st.session_state.user = None
if 'page' not in st.session_state: st.session_state.page = 'login'
if 'chat_open' not in st.session_state: st.session_state.chat_open = False
if 'recipes_processed' not in st.session_state: st.session_state.recipes_processed = False
if 'rag_pipeline' not in st.session_state: st.session_state.rag_pipeline = None
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'checked_existing_db' not in st.session_state: st.session_state.checked_existing_db = False
if 'auto_processed' not in st.session_state: st.session_state.auto_processed = False
if 'show_auth' not in st.session_state: st.session_state.show_auth = False
if 'selected_recipe' not in st.session_state: st.session_state.selected_recipe = None
if 'builtin_indexed' not in st.session_state: st.session_state.builtin_indexed = False

# User database file
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

# Top navigation bar
if st.session_state.logged_in:
    bar_left, bar_nav, bar_right = st.columns([2.2, 3, 1])
    with bar_left:
        st.markdown(f"""
        <div class="topbar-left">
            <div class="topbar-icon">🍳</div>
            <div>
                <div class="topbar-title">RecipeAI</div>
                <div class="topbar-welcome">Welcome, {st.session_state.user}!</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with bar_nav:
        n1, n2, n3 = st.columns(3)
        with n1:
            if st.button("🏠  Home", key="nav_home", use_container_width=True,
                         type="primary" if st.session_state.page == 'home' else "secondary"):
                st.session_state.page = 'home'
                st.rerun()
        with n2:
            if st.button("ℹ️  About", key="nav_about", use_container_width=True,
                         type="primary" if st.session_state.page == 'about' else "secondary"):
                st.session_state.page = 'about'
                st.rerun()
        with n3:
            if st.button("👤  Profile", key="nav_profile", use_container_width=True,
                         type="primary" if st.session_state.page == 'profile' else "secondary"):
                st.session_state.page = 'profile'
                st.rerun()
    with bar_right:
        if st.button("🚪  Logout", key="nav_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.page = 'login'
            st.rerun()
    st.markdown('<div class="topbar-divider"></div>', unsafe_allow_html=True)

# ============ LOGIN PAGE ============
if not st.session_state.logged_in:
    st.markdown("""
    <div class="brand-header">
        <div class="brand-icon">🍳</div>
        <h1 class="brand-title">RecipeAI</h1>
        <p class="brand-tagline">Discover and share amazing recipes</p>
    </div>
    """, unsafe_allow_html=True)

    left, center, right = st.columns([1, 1.3, 1])
    with center:
        tab1, tab2 = st.tabs(["Log In", "Sign Up"])

        with tab1:
            username = st.text_input("Username", key="login_user", placeholder="Enter your username")
            password = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
            if st.button("Log In", type="primary", use_container_width=True, key="btn_signin"):
                users = load_users()
                if username in users and users[username]['password'] == password:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.session_state.page = 'home'
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        with tab2:
            new_user = st.text_input("Username", key="signup_user", placeholder="Choose a username")
            new_email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
            new_pass = st.text_input("Password", type="password", key="signup_pass", placeholder="••••••••")
            if st.button("Sign Up", type="primary", use_container_width=True, key="btn_signup"):
                if not new_user or not new_pass:
                    st.error("Username and password are required")
                else:
                    users = load_users()
                    if new_user in users:
                        st.error("Username already taken")
                    else:
                        users[new_user] = {'password': new_pass, 'email': new_email, 'created': str(datetime.now())}
                        save_users(users)
                        st.success("Account created! You can now log in.")

# ============ LOGGED IN PAGES ============
else:
    if st.session_state.page == 'home':
        recipes = BUILT_IN_RECIPES
        categories = ["All", "Italian", "Pasta", "Salad", "Dessert", "Seafood", "Mexican"]

        if 'selected_category' not in st.session_state:
            st.session_state.selected_category = "All"

        # ==== DETAIL VIEW ====
        if st.session_state.selected_recipe is not None:
            r = recipes[st.session_state.selected_recipe]
            if st.button("✕  Close", key="detail_close"):
                st.session_state.selected_recipe = None
                st.rerun()

            st.markdown(f"""
            <div class="detail-hero">
                <img src="{img_to_data_uri(r['img'])}" class="detail-img"/>
                <div class="detail-overlay">
                    <span class="detail-badge">{r['category']}</span>
                    <h1 class="detail-title">{r['title']}</h1>
                    <div class="detail-meta">
                        <span>🕒 {r['time']}</span>
                        <span>👥 {r['servings']}</span>
                    </div>
                </div>
            </div>
            <p class="detail-desc">{r['description']}</p>
            """, unsafe_allow_html=True)

            ing_col, ins_col = st.columns(2)
            with ing_col:
                ing_html = "".join([f"<li>{i}</li>" for i in r['ingredients']])
                st.markdown(f"""
                <div class="detail-section">
                    <h3 class="detail-section-title">👨‍🍳 Ingredients</h3>
                    <ul class="ingredient-list">{ing_html}</ul>
                </div>
                """, unsafe_allow_html=True)
            with ins_col:
                ins_html = "".join([
                    f'<div class="instruction-item"><span class="instruction-num">{i+1}</span><span>{step}</span></div>'
                    for i, step in enumerate(r['instructions'])
                ])
                st.markdown(f"""
                <div class="detail-section">
                    <h3 class="detail-section-title">Instructions</h3>
                    {ins_html}
                </div>
                """, unsafe_allow_html=True)
        else:
            # ==== LIST VIEW ====
            search = st.text_input("Search", placeholder="🔍  Search recipes...", label_visibility="collapsed", key="recipe_search")

            cols = st.columns(len(categories))
            for i, cat in enumerate(categories):
                with cols[i]:
                    is_active = st.session_state.selected_category == cat
                    if st.button(cat, key=f"cat_{cat}", use_container_width=True,
                                 type="primary" if is_active else "secondary"):
                        st.session_state.selected_category = cat
                        st.rerun()

            filtered = [(idx, r) for idx, r in enumerate(recipes)
                        if (st.session_state.selected_category == "All" or r["category"] == st.session_state.selected_category)
                        and (not search or search.lower() in r["title"].lower())]

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            if not filtered:
                st.info("No recipes found.")
            else:
                for row_start in range(0, len(filtered), 3):
                    row = filtered[row_start:row_start+3]
                    cols = st.columns(3)
                    for col, (idx, r) in zip(cols, row):
                        with col:
                            st.markdown(f"""
                            <div class="recipe-card">
                                <div class="recipe-img-wrap">
                                    <img src="{img_to_data_uri(r['img'])}" class="recipe-img"/>
                                    <span class="recipe-badge">{r['category']}</span>
                                    <span class="recipe-heart">♡</span>
                                </div>
                                <div class="recipe-body">
                                    <div class="recipe-title">{r['title']}</div>
                                    <div class="recipe-meta">
                                        <span>🕒 {r['time']}</span>
                                        <span>👥 {r['servings']}</span>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button("View Recipe", key=f"view_{idx}", use_container_width=True):
                                st.session_state.selected_recipe = idx
                                st.rerun()
    
    elif st.session_state.page == 'about':
        st.markdown("""
        <div class="page-hero">
            <h1>About RecipeAI</h1>
            <p>AI-powered recipe discovery for everyday cooks.</p>
        </div>
        """, unsafe_allow_html=True)

        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown("""
            <div class="info-card">
                <div class="info-icon">🎯</div>
                <h3>Our Mission</h3>
                <p>Make cooking accessible to everyone by helping you discover recipes based on what's in your kitchen, dietary needs, and cooking style.</p>
            </div>
            """, unsafe_allow_html=True)
        with a2:
            st.markdown("""
            <div class="info-card">
                <div class="info-icon">⚡</div>
                <h3>Technology</h3>
                <p>Powered by <b>RAG</b>, <b>vector search</b>, <b>LangChain</b>, <b>ChromaDB</b>, and <b>OpenAI GPT</b> for fast, accurate recipe answers.</p>
            </div>
            """, unsafe_allow_html=True)
        with a3:
            st.markdown("""
            <div class="info-card">
                <div class="info-icon">🍳</div>
                <h3>How It Works</h3>
                <p>Upload your recipe collection, the AI indexes them, then chat naturally to find dishes by ingredients, cuisine, or time.</p>
            </div>
            """, unsafe_allow_html=True)

    elif st.session_state.page == 'profile':
        st.markdown(f"""
        <div class="profile-header">
            <div class="profile-avatar">{st.session_state.user[0].upper()}</div>
            <div>
                <h1>{st.session_state.user}</h1>
                <p>Your profile and cooking preferences</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        p1, p2 = st.columns(2)
        with p1:
            with st.container(border=True):
                st.markdown("#### 🥗 Dietary Preferences")
                dietary_prefs = st.multiselect(
                    "Select preferences",
                    ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Keto", "Low-carb"],
                    label_visibility="collapsed",
                )
                if dietary_prefs:
                    st.success(f"Saved: {', '.join(dietary_prefs)}")
        with p2:
            with st.container(border=True):
                st.markdown("#### 🌍 Favorite Cuisines")
                cuisines = st.multiselect(
                    "Select cuisines",
                    ["Italian", "Mexican", "Thai", "Indian", "Chinese", "Japanese", "French", "Mediterranean"],
                    label_visibility="collapsed",
                )
                if cuisines:
                    st.success(f"Saved: {', '.join(cuisines)}")

# ============ FLOATING CHAT WIDGET ============
if st.session_state.logged_in:
    # Auto-load recipes at login so the user can chat without uploading.
    # Retry every rerun until we actually have a working pipeline.
    if st.session_state.rag_pipeline is None:
        if not OPENAI_API_KEY:
            st.warning("⚠️ OPENAI_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or Streamlit Cloud Secrets, then restart the app.")
        # If an index already exists, just load it
        elif os.path.exists("./chroma_db"):
            try:
                rag = RAGPipeline()
                rag.initialize_vectorstore([])  # load existing
                # Check if the loaded store is actually populated
                try:
                    count = rag.vectorstore._collection.count()
                except Exception:
                    count = 0
                if count == 0:
                    # Empty/corrupt index — wipe and rebuild below
                    import shutil
                    shutil.rmtree("./chroma_db", ignore_errors=True)
                else:
                    rag.initialize_qa_chain(OPENAI_API_KEY)
                    st.session_state.rag_pipeline = rag
                    st.session_state.recipes_processed = True
                    st.session_state.checked_existing_db = True
            except Exception as e:
                st.error(f"Failed to load existing recipe index: {e}")

        # If no existing index, build one from built-in + uploaded PDFs
        if OPENAI_API_KEY and not os.path.exists("./chroma_db"):
            with st.spinner("Indexing recipes..."):
                processor = RecipeProcessor()
                all_recipes = []

                # Built-in recipes
                for r in BUILT_IN_RECIPES:
                    all_recipes.append({
                        'title': r['title'],
                        'cuisine': r['cuisine'],
                        'dietary': r['dietary'] if r['dietary'] else ['None'],
                        'prep_time': r['prep_time'],
                        'cook_time': r['cook_time'],
                        'servings': r['servings'],
                        'ingredients': r['ingredients'],
                        'instructions': r['instructions'],
                    })

                # Uploaded files (kawaling pinoy, cookbook, etc.)
                if os.path.exists("./uploaded_recipes"):
                    for file in os.listdir("./uploaded_recipes"):
                        if file.endswith(('.pdf', '.txt', '.md')):
                            all_recipes.extend(processor.process_file(os.path.join("./uploaded_recipes", file)))

                if all_recipes:
                    docs = processor.create_recipe_documents(all_recipes)
                    rag = RAGPipeline()
                    rag.initialize_vectorstore(docs)
                    rag.initialize_qa_chain(OPENAI_API_KEY)
                    st.session_state.rag_pipeline = rag
                    st.session_state.recipes_processed = True
    
    # Chat button
    if st.button("🤖", key="chat_btn", type="primary", help="Chat with RecipeAI"):
        st.session_state.chat_open = not st.session_state.chat_open
    
    # Chat popup
    if st.session_state.chat_open:
        with st.container():
            st.markdown('<div class="assistant-header"><span class="assistant-icon">💬</span><h2>RecipeAI Assistant</h2></div>', unsafe_allow_html=True)

            # Check for existing vector store
            if not st.session_state.checked_existing_db and os.path.exists("./chroma_db"):
                try:
                    rag = RAGPipeline()
                    rag.initialize_vectorstore([])  # Load existing
                    rag.initialize_qa_chain(OPENAI_API_KEY)
                    st.session_state.rag_pipeline = rag
                    st.session_state.recipes_processed = True
                    st.session_state.checked_existing_db = True
                except:
                    st.session_state.checked_existing_db = True

            # Upload card
            with st.container(border=True):
                uploaded_files = st.file_uploader(
                    "Upload recipe files (PDF/text)",
                    type=['pdf', 'txt', 'md'],
                    accept_multiple_files=True,
                    key="popup_upload",
                )

                if st.button("Process Recipes", key="popup_process", type="primary"):
                    if uploaded_files:
                        with st.spinner("Processing..."):
                            os.makedirs("uploaded_recipes", exist_ok=True)
                            file_paths = []
                            for uf in uploaded_files:
                                fp = os.path.join("uploaded_recipes", uf.name)
                                with open(fp, "wb") as f: f.write(uf.getbuffer())
                                file_paths.append(fp)

                            processor = RecipeProcessor()
                            all_recipes = []
                            for fp in file_paths:
                                all_recipes.extend(processor.process_file(fp))

                            if all_recipes:
                                st.success(f"Processed {len(all_recipes)} recipes!")
                                docs = processor.create_recipe_documents(all_recipes)
                                rag = RAGPipeline()
                                rag.initialize_vectorstore(docs)
                                rag.initialize_qa_chain(OPENAI_API_KEY)
                                st.session_state.rag_pipeline = rag
                                st.session_state.recipes_processed = True
                                st.session_state.chat_history = []
                            else:
                                st.error("No recipes found. Your PDF might be in a format the parser doesn't recognize.")
                    else:
                        st.error("Please upload files.")

            # Chat section header
            st.markdown('<div class="chat-section-title"><span>💬</span><h3>Chat</h3></div>', unsafe_allow_html=True)

            # Chat area (real scrollable bordered container)
            chat_box = st.container(height=420, border=True)
            with chat_box:
                if not st.session_state.chat_history:
                    st.markdown('<div class="chat-placeholder">Start a conversation by asking about recipes...</div>', unsafe_allow_html=True)
                else:
                    for msg in st.session_state.chat_history:
                        if msg["role"] == "user":
                            st.chat_message("user").write(msg["content"])
                        else:
                            st.chat_message("assistant").write(msg["content"])

            # Chat input — always available
            if prompt := st.chat_input("Ask about recipes...", key="popup_chat"):
                if st.session_state.rag_pipeline is None:
                    if not OPENAI_API_KEY:
                        st.error("Recipe AI is not initialized: OPENAI_API_KEY is missing. Add it to .streamlit/secrets.toml or Streamlit Cloud Secrets, then restart the app.")
                    else:
                        st.error("Recipe index isn't ready yet. Refresh the page, or upload a recipe file and click 'Process Recipes'.")
                else:
                    st.session_state.chat_history.append({"role": "user", "content": prompt})
                    with st.spinner("Thinking..."):
                        result = st.session_state.rag_pipeline.chat(prompt)
                    st.session_state.chat_history.append({"role": "assistant", "content": result['answer']})
                    st.rerun()

            col_clear, col_close = st.columns([1, 1])
            with col_clear:
                if st.button("Clear Chat", key="popup_clear"):
                    if st.session_state.rag_pipeline is not None:
                        st.session_state.rag_pipeline.clear_memory()
                    st.session_state.chat_history = []
                    st.rerun()
            with col_close:
                if st.button("✕ Close", key="popup_close"):
                    st.session_state.chat_open = False
                    st.rerun()

# Footer
st.markdown("""
<div class="app-footer">
    <span class="footer-brand">🍳 RecipeAI</span>
    <span class="footer-sep">·</span>
    <span>Built with Streamlit · LangChain · ChromaDB · OpenAI</span>
    <div class="footer-copy">© 2026 RecipeAI. All rights reserved.</div>
</div>
""", unsafe_allow_html=True)
