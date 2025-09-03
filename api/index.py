from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from typing import List, Optional, Dict, Any
import logging
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration class for RAG pipeline
class RAGConfig:
    def __init__(self):
        self.default_retrieval_count = int(os.getenv("DEFAULT_RETRIEVAL_COUNT", "20"))
        self.max_retrieval_count = int(os.getenv("MAX_RETRIEVAL_COUNT", "50"))
        self.collection_name = os.getenv("COLLECTION_NAME", "GovTech")
        self.embedding_model_name = "intfloat/e5-base-v2"
        self.gemini_model_name = "gemini-1.5-flash"

# Global configuration instance
rag_config = RAGConfig()

# Data models for request/response
class ChatMessage:
    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp

class ChatRequest:
    def __init__(self, query: str, retrieval_count: Optional[int] = None, conversation_history: Optional[List[Dict]] = None):
        self.query = query
        self.retrieval_count = retrieval_count
        self.conversation_history = conversation_history or []

class ChatResponse:
    def __init__(self, answer: str, documents_retrieved: int, sources: List[Dict[str, str]] = None):
        self.answer = answer
        self.documents_retrieved = documents_retrieved
        self.sources = sources or []
    
    def to_dict(self):
        return {
            "answer": self.answer,
            "documents_retrieved": self.documents_retrieved,
            "sources": self.sources
        }

# Global variables for models and clients
embedding_model = None
qdrant_client = None
gemini_model = None

def initialize_models():
    """Initialize models and clients on first request"""
    global embedding_model, qdrant_client, gemini_model
    
    if embedding_model is None:
        try:
            # Initialize embedding model
            logger.info(f"Loading {rag_config.embedding_model_name} embedding model...")
            embedding_model = SentenceTransformer(rag_config.embedding_model_name)
            logger.info(f"{rag_config.embedding_model_name} model loaded successfully")
            
            # Initialize Qdrant client
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            
            if not qdrant_url or not qdrant_api_key:
                raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set")
                
            logger.info(f"Connecting to Qdrant at {qdrant_url}")
            qdrant_client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
            )
            logger.info("Qdrant client initialized successfully")
            
            # Initialize Gemini
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                raise ValueError("GEMINI_API_KEY must be set")
                
            genai.configure(api_key=gemini_api_key)
            gemini_model = genai.GenerativeModel(rag_config.gemini_model_name)
            logger.info(f"Gemini model ({rag_config.gemini_model_name}) initialized successfully")
            
        except Exception as e:
            logger.error(f"Error during initialization: {str(e)}")
            raise

def get_embedding(text: str) -> List[float]:
    """Generate E5-base-v2 embedding for the given text."""
    try:
        initialize_models()
        prefixed_text = f"query: {text}"
        embedding = embedding_model.encode(prefixed_text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise Exception(f"Error generating embedding: {str(e)}")

def search_qdrant(query_embedding: List[float], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    """Search Qdrant for similar documents with configurable retrieval count."""
    try:
        initialize_models()
        if top_k is None:
            top_k = rag_config.default_retrieval_count
        
        top_k = min(top_k, rag_config.max_retrieval_count)
        
        logger.info(f"Searching Qdrant with top_k={top_k}")
        
        search_result = qdrant_client.search(
            collection_name=rag_config.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            with_vectors=False
        )
        
        documents = []
        for result in search_result:
            content = result.payload.get("content", "") or result.payload.get("text", "")
            doc_data = {
                "content": content,
                "source": result.payload.get("source", result.payload.get("activity_id", "Unknown")),
                "score": result.score,
                "metadata": result.payload
            }
            documents.append(doc_data)
            
        return documents
        
    except Exception as e:
        logger.error(f"Error searching Qdrant: {str(e)}")
        raise Exception(f"Error searching vector database: {str(e)}")

def prepare_context_from_documents(retrieved_docs: List[Dict[str, Any]]) -> str:
    """Prepare context string from retrieved documents with full metadata."""
    retrieved_context = "\n\n".join([
        f"Document {i+1} (Source: {doc['source']}):\nContent: {doc['content']}\nMetadata: {doc['metadata']}"
        for i, doc in enumerate(retrieved_docs)
    ])
    return retrieved_context

def create_government_prompt(query: str, retrieved_context: str, conversation_history: Optional[List[ChatMessage]] = None) -> str:
    """Create the government chatbot prompt for KPK with ChatGPT-like responses and conversation context."""
    
    conversation_context = ""
    if conversation_history and len(conversation_history) > 0:
        conversation_context = "\n\nPrevious Conversation Context:\n"
        for msg in conversation_history[-10:]:
            role_label = "User" if msg.role == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg.content}\n"
        conversation_context += "\nIMPORTANT: Use this conversation history to maintain context and provide relevant follow-up responses.\n"
    
    refining_prompt = f"""You are a helpful AI assistant specializing in Government of Khyber Pakhtunkhwa (KPK), Pakistan information. Provide comprehensive, conversational responses about government policies, programs, and services.

Response Guidelines:
- Be conversational and helpful like ChatGPT
- Provide detailed, accurate information based on the retrieved context
- If information is not available in the context, clearly state this
- Use bullet points and structured formatting when appropriate
- Be respectful and professional
- Focus on KPK government services and policies

{conversation_context}

Retrieved Context:
{retrieved_context}

User Query: {query}

Response:"""
    
    return refining_prompt

def handle_chat_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle chat request for RAG pipeline"""
    try:
        initialize_models()
        
        # Parse request data
        query = request_data.get('query', '')
        retrieval_count = request_data.get('retrieval_count')
        conversation_history = request_data.get('conversation_history', [])
        
        if not query:
            return {
                "error": "Query is required",
                "status_code": 400
            }
        
        # Generate embedding for the query
        query_embedding = get_embedding(query)
        
        # Search for relevant documents
        retrieved_docs = search_qdrant(query_embedding, retrieval_count)
        
        if not retrieved_docs:
            response = ChatResponse(
                answer="I couldn't find relevant information to answer your question. Please try rephrasing your query.",
                documents_retrieved=0,
                sources=[]
            )
            return response.to_dict()
        
        # Prepare context from retrieved documents
        retrieved_context = prepare_context_from_documents(retrieved_docs)
        
        # Create conversation history objects
        chat_history = []
        for msg in conversation_history:
            if isinstance(msg, dict):
                chat_history.append(ChatMessage(msg.get('role', ''), msg.get('content', '')))
        
        # Create the prompt
        prompt = create_government_prompt(query, retrieved_context, chat_history)
        
        # Generate response using Gemini
        gemini_response = gemini_model.generate_content(prompt)
        
        # Prepare sources
        sources = [
            {
                "source": doc["source"],
                "score": str(doc["score"]),
                "content_preview": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"]
            }
            for doc in retrieved_docs[:5]  # Top 5 sources
        ]
        
        response = ChatResponse(
            answer=gemini_response.text,
            documents_retrieved=len(retrieved_docs),
            sources=sources
        )
        
        return response.to_dict()
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return {
            "error": f"Error processing request: {str(e)}",
            "status_code": 500
        }

def handler(request, response):
    """Vercel serverless function handler"""
    # Set CORS headers
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    # Handle preflight OPTIONS request
    if request.get('method') == 'OPTIONS':
        response['statusCode'] = 200
        return ''
    
    # Parse URL path
    path = request.get('url', '').split('?')[0]
    method = request.get('method', 'GET')
    
    try:
        if path == '/' and method == 'GET':
            # Root endpoint
            result = {"message": "RAG Pipeline API is running", "status": "healthy"}
            response['statusCode'] = 200
            response['headers'] = {'Content-Type': 'application/json'}
            return json.dumps(result)
            
        elif path == '/health' and method == 'GET':
            # Health check endpoint
            result = {"status": "healthy", "message": "API is running"}
            response['statusCode'] = 200
            response['headers'] = {'Content-Type': 'application/json'}
            return json.dumps(result)
            
        elif path == '/chat' and method == 'POST':
            # Chat endpoint
            body = request.get('body', '{}')
            if isinstance(body, str):
                request_data = json.loads(body)
            else:
                request_data = body
                
            result = handle_chat_request(request_data)
            
            if 'error' in result:
                response['statusCode'] = result.get('status_code', 500)
            else:
                response['statusCode'] = 200
                
            response['headers'] = {'Content-Type': 'application/json'}
            return json.dumps(result)
            
        else:
            # Not found
            response['statusCode'] = 404
            response['headers'] = {'Content-Type': 'application/json'}
            return json.dumps({"error": "Not found"})
            
    except Exception as e:
        logger.error(f"Handler error: {str(e)}")
        response['statusCode'] = 500
        response['headers'] = {'Content-Type': 'application/json'}
        return json.dumps({"error": f"Internal server error: {str(e)}"})