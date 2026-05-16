# Recipe Chatbot with Dietary RAG

A Streamlit-based chatbot that helps you find recipes based on ingredients, dietary needs, or cuisine type using RAG (Retrieval-Augmented Generation).

## Features

- Upload recipe collections (PDF or text files)
- Chat interface to find recipes by ingredients, dietary restrictions, or cuisine
- RAG-powered recipe search using vector embeddings
- Intelligent recipe recommendations

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your OpenAI API key:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

3. Run the application:
```bash
streamlit run app.py
```

## Usage

1. Upload recipe files (PDF or text) using the sidebar
2. Wait for recipes to be processed and indexed
3. Start chatting to find recipes based on your preferences
4. Ask for recipes by ingredients, dietary needs, or cuisine type
