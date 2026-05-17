import os
from typing import List, Dict, Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


class RAGPipeline:
    """RAG pipeline for recipe search and chat."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vectorstore = None
        self.retriever = None
        self.qa_chain = None
        self.chat_history = []
    
    def initialize_vectorstore(self, documents: List[Dict]):
        """Initialize vector store with recipe documents."""
        # Convert to LangChain Document format
        langchain_docs = [
            Document(
                page_content=doc['page_content'],
                metadata=doc['metadata']
            )
            for doc in documents
        ]
        
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        splits = text_splitter.split_documents(langchain_docs)
        
        # Create or load vector store
        if os.path.exists(self.persist_directory):
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
            # Only add documents if there are any (avoids empty-upsert error when just loading)
            if splits:
                self.vectorstore.add_documents(splits)
        else:
            if not splits:
                raise ValueError("Cannot create a new vector store with no documents.")
            self.vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
        
        # Note: Chroma 0.5+ auto-persists; .persist() was removed.

        
        # Create retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4}
        )
    
    def initialize_qa_chain(self, openai_api_key: str):
        """Initialize the conversational QA chain."""
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            api_key=openai_api_key
        )
        
        # Create a simple RAG chain using LCEL
        template = """You are a helpful recipe assistant. Use the following pieces of retrieved recipes to answer the question. 
        If the context contains relevant information, use it to answer. If the context doesn't contain the exact recipe but has related information, mention that.
        Be helpful and try to provide the best answer possible from what's available.
        If you truly cannot find any relevant information, say so politely.

Context:
{context}

Question: {question}

Answer:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)
        
        self.qa_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
    
    def search_recipes(self, query: str, k: int = 4) -> List[Dict]:
        """Search for recipes based on query."""
        if not self.retriever:
            return []
        
        docs = self.retriever.get_relevant_documents(query, k=k)
        
        results = []
        for doc in docs:
            results.append({
                'content': doc.page_content,
                'metadata': doc.metadata,
                'score': 0.0  # Chroma doesn't provide scores by default
            })
        
        return results
    
    def chat(self, question: str) -> Dict:
        """Chat with the recipe assistant."""
        if not self.qa_chain:
            return {
                'answer': 'Please upload recipe files first.',
                'source_documents': []
            }
        
        try:
            # Get relevant documents separately for display and debugging
            docs = self.retriever.invoke(question)
            
            # Debug: print what was retrieved
            print(f"Question: {question}")
            print(f"Retrieved {len(docs)} documents")
            for i, doc in enumerate(docs[:2]):
                print(f"Doc {i+1} preview: {doc.page_content[:200]}...")
            
            # Get answer from the chain
            answer = self.qa_chain.invoke(question)
            
            return {
                'answer': answer,
                'source_documents': docs
            }
        except Exception as e:
            return {
                'answer': f'Error processing your question: {str(e)}',
                'source_documents': []
            }
    
    def clear_memory(self):
        """Clear conversation history."""
        self.chat_history = []
