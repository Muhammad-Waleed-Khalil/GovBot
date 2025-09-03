from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Initialize FastAPI app
app = FastAPI(
    title="RAG Pipeline API",
    description="Retrieval-Augmented Generation API with Qdrant and Gemini",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Pydantic models
class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    query: str
    retrieval_count: Optional[int] = None  # Allow custom retrieval count per request
    conversation_history: Optional[List[ChatMessage]] = []  # Previous messages for context

class ChatResponse(BaseModel):
    answer: str
    documents_retrieved: int
    sources: List[Dict[str, str]] = []

class ActionRequest(BaseModel):
    query: str
    context: str
    action_type: str  # 'feasibility', 'case_study', 'executive_report'

class ActionResponse(BaseModel):
    result: str
    action_type: str

# Global variables for models and clients
embedding_model = None
qdrant_client = None
gemini_model = None

# Initialize models and clients
@app.on_event("startup")
async def startup_event():
    global embedding_model, qdrant_client, gemini_model
    
    try:
        # Initialize embedding model using configuration
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
        logger.error(f"Error during startup: {str(e)}")
        raise

def get_embedding(text: str) -> List[float]:
    """Generate E5-base-v2 embedding for the given text."""
    try:
        # E5 models require a specific prefix for queries
        prefixed_text = f"query: {text}"
        embedding = embedding_model.encode(prefixed_text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating embedding")

def search_qdrant(query_embedding: List[float], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    """Search Qdrant for similar documents with configurable retrieval count."""
    try:
        # Use provided top_k or default from configuration
        if top_k is None:
            top_k = rag_config.default_retrieval_count
        
        # Ensure top_k doesn't exceed maximum allowed
        top_k = min(top_k, rag_config.max_retrieval_count)
        
        logger.info(f"Searching Qdrant with top_k={top_k}")
        
        search_result = qdrant_client.search(
            collection_name=rag_config.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            with_vectors=False
        )
        
        # Debug logging: Log the raw search results
        logger.info(f"Qdrant search returned {len(search_result)} results")
        for i, point in enumerate(search_result):
            logger.info(f"Result {i+1}: Score={point.score}, ID={point.id}")
            logger.info(f"Result {i+1} payload: {point.payload}")
            if hasattr(point, 'payload') and point.payload:
                content = point.payload.get('content', '') or point.payload.get('text', '')
                logger.info(f"Result {i+1} content length: {len(content)}")
                logger.info(f"Result {i+1} content preview: {content[:200]}...")
            else:
                logger.warning(f"Result {i+1} has no payload or empty payload")
        
        documents = []
        for result in search_result:
            # Try both 'content' and 'text' fields as the actual data might use 'text'
            content = result.payload.get("content", "") or result.payload.get("text", "")
            doc_data = {
                "content": content,
                "source": result.payload.get("source", result.payload.get("activity_id", "Unknown")),
                "score": result.score,
                "metadata": result.payload
            }
            documents.append(doc_data)
            
        logger.info(f"Extracted {len(documents)} documents with content")
        return documents
        
    except Exception as e:
        logger.error(f"Error searching Qdrant: {str(e)}")
        raise HTTPException(status_code=500, detail="Error searching vector database")

def prepare_context_from_documents(retrieved_docs: List[Dict[str, Any]]) -> str:
    """Prepare context string from retrieved documents with full metadata."""
    retrieved_context = "\n\n".join([
        f"Document {i+1} (Source: {doc['source']}):\nContent: {doc['content']}\nMetadata: {doc['metadata']}"
        for i, doc in enumerate(retrieved_docs)
    ])
    return retrieved_context

def create_government_prompt(query: str, retrieved_context: str, conversation_history: Optional[List[ChatMessage]] = None) -> str:
    """Create the government chatbot prompt for KPK with ChatGPT-like responses and conversation context."""
    
    # Build conversation context if history exists
    conversation_context = ""
    if conversation_history and len(conversation_history) > 0:
        conversation_context = "\n\nPrevious Conversation Context:\n"
        for msg in conversation_history[-10:]:  # Include last 10 messages for context
            role_label = "User" if msg.role == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg.content}\n"
        conversation_context += "\nIMPORTANT: Use this conversation history to maintain context and provide relevant follow-up responses. When the user refers to previous data or asks follow-up questions, reference the appropriate information from our conversation.\n"
    
    refining_prompt = f"""You are a helpful AI assistant specializing in Government of Khyber Pakhtunkhwa (KPK), Pakistan information. Provide comprehensive, conversational responses about government policies, programs, and services.

Response Guidelines:
- Write in a natural, conversational tone like ChatGPT
- Use clear, accessible language that anyone can understand
- Provide detailed, comprehensive information covering all aspects
- Format using Markdown for better readability
- Include relevant statistics, dates, and specific details when available
- Explain technical terms in simple language
- Be thorough and informative without being overly formal
- Do NOT include any citations, sources, or document references
- Do NOT mention where the information comes from
- Present information as if you naturally know it
- MAINTAIN CONVERSATION CONTINUITY: Reference previous parts of our conversation when relevant
- ANALYZE DATA when asked for recommendations: If the user asks for recommendations, suggestions, or assessments based on data, carefully analyze the provided context data and make specific, data-driven recommendations
- PRIORITIZE BASED ON DATA: When making recommendations, rank them based on the metrics, indicators, and evidence present in the provided data
- CONTEXTUAL AWARENESS: When users ask follow-up questions or refer to "the data" or "that information", understand they're referring to previously discussed content

Formatting to use:
- **Bold text** for important headings and key points
- *Italic text* for policy names, document titles, and emphasis
- Tables using Markdown format for:
  * Statistical data and numbers
  * Comparisons between districts or regions
  * Budget information
  * Timeline of events
  * Program details and outcomes
- Bullet points for lists and key information
- Clear headings and sections for organization

Example table format:
| Category | Details | Status |
|----------|---------|--------|
| **Policy Name** | Description | *Implementation Status* |

Data Analysis Instructions:
When the user asks for recommendations, assessments, or data-driven suggestions, follow these steps:
1. Examine the provided context data thoroughly for relevant metrics, statistics, and indicators
2. Identify key patterns, trends, or priority areas based on the data
3. Consider multiple factors and variables present in the dataset
4. Provide specific recommendations with clear reasoning based on the analyzed data
5. Rank or prioritize suggestions from highest to lowest importance
6. Give concrete, actionable advice rather than asking for more information
7. Base all conclusions strictly on the available data in the context
8. Reference previous conversation when making recommendations to maintain continuity{conversation_context}

Context Information:
{retrieved_context}

User Question: {query}

Provide a comprehensive, natural response that covers all relevant aspects of the topic. Write as if you're having a helpful conversation, being thorough and informative while maintaining a friendly, accessible tone. Focus on giving complete information without any source attribution. If asked for recommendations, analyze the data thoroughly and provide specific, data-driven suggestions. Maintain awareness of our previous conversation and reference it when relevant."""
    return refining_prompt

def generate_ai_response(prompt: str) -> str:
    """Generate AI response using Gemini model."""
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating AI response")

def generate_refined_response(query: str, retrieved_docs: List[Dict[str, Any]], conversation_history: Optional[List[ChatMessage]] = None) -> str:
    """Generate refined response using modular approach with Gemini and conversation context."""
    try:
        # Step 1: Prepare context from documents
        retrieved_context = prepare_context_from_documents(retrieved_docs)
        
        # Step 2: Create government prompt with conversation history
        refining_prompt = create_government_prompt(query, retrieved_context, conversation_history)
        
        # Step 3: Generate AI response
        response_text = generate_ai_response(refining_prompt)
        
        return response_text
        
    except Exception as e:
        logger.error(f"Error in refined response generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating refined response")

def create_feasibility_prompt(query: str, context: str) -> str:
    """Create prompt for feasibility simulation analysis."""
    return f"""You are an expert policy analyst and feasibility consultant for the Government of Khyber Pakhtunkhwa (KPK). Conduct a comprehensive feasibility analysis based on the provided context.

**FEASIBILITY SIMULATION ENGINE**

Analyze the following query and provide a detailed feasibility assessment:

Query: {query}
Context: {context}

Provide a structured feasibility analysis covering:

# Executive Summary
## Overall feasibility rating (High/Medium/Low)
## Key findings and recommendations
## Financial viability summary

# Technical Feasibility
## Infrastructure requirements
## Technology needs
## Human resource capabilities
## Implementation complexity
## Development costs and technical resources

# Financial Feasibility
## Initial Investment Requirements
### Capital expenditure (CAPEX)
### Operational expenditure (OPEX)
### Working capital needs

## Revenue Projections
### Revenue streams identification
### 5-year revenue forecast
### Pricing strategy analysis

## Cost Analysis
### Direct costs breakdown
### Indirect costs assessment
### Variable vs fixed costs

## Financial Metrics
### Return on Investment (ROI) calculations
### Net Present Value (NPV) analysis
### Internal Rate of Return (IRR)
### Payback period estimation
### Break-even analysis

## Funding Requirements
### Total funding needed
### Funding sources (provincial budget, federal support, development partners)
### Funding timeline and milestones

## Financial Risk Assessment
### Sensitivity analysis
### Scenario planning (best/worst/most likely)
### Cash flow projections
### Financial contingency planning

# Operational Feasibility
## Administrative capacity
## Stakeholder readiness
## Implementation timeline
## Risk assessment
## Operational costs and efficiency

# Legal & Regulatory Feasibility
## Policy alignment
## Regulatory requirements
## Compliance considerations
## Legal framework adequacy

# Social & Political Feasibility
## Public acceptance
## Political support
## Community impact
## Stakeholder buy-in

# Risk Analysis
## Technical risks and mitigation strategies
## Market risks and contingency planning
## Financial risks and hedging strategies
## Operational risks and controls

# Recommendations
## Implementation roadmap
## Priority actions
## Success metrics
## Investment decision framework

Provide actionable insights with specific recommendations and financial metrics for KPK government implementation."""

def create_case_study_prompt(query: str, context: str) -> str:
    """Create prompt for comparative case study analysis."""
    return f"""You are an expert policy analyst. Based on the following query and context, create a detailed COMPARATIVE CASE STUDY analysis:
    
Query: {query}
Context: {context}
    
Please provide a comprehensive COMPARATIVE CASE STUDY covering:
    
# COMPARATIVE CASE STUDY Overview
## Background and context of multiple cases
## Key stakeholders involved across cases
## Timeline comparison of events
## Selection criteria for comparative analysis
    
# Problem Analysis Comparison
## Core issues identified in each case
## Root cause analysis comparison
## Impact assessment across different contexts
## Similarities and differences in problem manifestation
    
# Solutions Comparison
## Strategies adopted in different cases
## Implementation approach variations
## Resources utilized comparison
## Cost-effectiveness analysis across cases
    
# Results and Outcomes Comparison
## Measurable results achieved in each case
## Success metrics comparison
## Performance benchmarking
## Effectiveness ranking and analysis
    
# Best Practices Identification
## Key success factors across cases
## Replicable strategies comparison
## Context-specific vs universal practices
## Recommendations synthesis
    
# Challenges and Limitations Analysis
## Obstacles encountered in different cases
## Mitigation strategies comparison
## Failure factors analysis
## Areas for improvement across cases
    
# Comparative Analysis Matrix
## Side-by-side comparison table
## Strengths and weaknesses assessment
## Contextual factors influence
## Adaptability analysis for different settings
    
# Lessons Learned and Recommendations
## Cross-case insights
## Best practice recommendations
## Implementation guidelines
## Success factors for replication
    
Please ensure the comparative case study is detailed, evidence-based, and provides actionable insights through systematic comparison of multiple cases.
"""

def create_executive_report_prompt(query: str, context: str) -> str:
    """Create prompt for executive feasibility report."""
    return f"""You are a senior policy advisor preparing an executive briefing for the Chief Minister and Cabinet of Khyber Pakhtunkhwa. Create a comprehensive executive feasibility report.

# EXECUTIVE FEASIBILITY REPORT

Query: {query}
Context: {context}

---

# Executive Summary

## Recommendation: [APPROVE/APPROVE WITH CONDITIONS/DEFER/REJECT]

## Key Findings
- Critical findings summary
- Financial viability assessment
- Strategic impact overview

## Strategic Alignment
- Alignment with KPK government priorities
- Policy coherence assessment
- Strategic impact evaluation

---

# Detailed Analysis

## Strategic Context
- Current policy landscape
- Government priorities alignment
- Stakeholder expectations
- Public interest considerations

## Implementation Assessment

### Readiness Level: [High/Medium/Low]
- Administrative capacity
- Technical capabilities
- Resource availability
- Stakeholder alignment

### Implementation Timeline
| Phase | Duration | Key Milestones | Resources Required |
|-------|----------|--------------------|--------------------|\n| **Phase 1** | | | |
| **Phase 2** | | | |
| **Phase 3** | | | |

## Financial Implications

### Budget Requirements
- Initial investment: [Amount]
- Annual operational cost: [Amount]
- Total 5-year cost: [Amount]
- ROI projections and payback period

### Funding Strategy
- Provincial budget allocation
- Federal support opportunities
- Development partner funding
- Private sector involvement
- Financial sustainability plan

### Financial Risk Assessment
- Cost overrun risks
- Revenue shortfall scenarios
- Contingency funding requirements
- Financial mitigation strategies

## Risk Assessment

### High-Priority Risks
- Financial risks: [Description and mitigation]
- Implementation risks: [Description and mitigation]
- Political risks: [Description and mitigation]
- Operational risks: [Description and mitigation]

### Risk Mitigation Framework
- Monitoring mechanisms
- Contingency plans
- Success indicators
- Early warning systems

## Stakeholder Impact
- Beneficiary analysis
- Implementation partners
- Potential opposition
- Communication strategy needs

---

# Recommendations

## Primary Recommendation
- Detailed recommendation with rationale
- Financial justification
- Strategic benefits

## Implementation Roadmap
- Immediate Actions (0-3 months)
- Short-term Priorities (3-12 months)
- Medium-term Goals (1-3 years)
- Financial milestones and checkpoints

## Success Metrics
- Key Performance Indicators (KPIs)
- Financial performance metrics
- Monitoring framework
- Evaluation timeline

## Resource Requirements
- Human resources
- Financial resources
- Technical infrastructure
- Institutional support

---

**Prepared for**: Chief Minister & Cabinet, Government of Khyber Pakhtunkhwa
**Classification**: [Confidential/Restricted/Public]
**Next Steps**: [Specific actions required from leadership]

Provide executive-level insights with clear, actionable recommendations and comprehensive financial analysis suitable for high-level decision making."""

def generate_action_response(action_type: str, query: str, context: str) -> str:
    """Generate specialized response based on action type."""
    try:
        if action_type == "feasibility":
            prompt = create_feasibility_prompt(query, context)
        elif action_type == "case_study":
            prompt = create_case_study_prompt(query, context)
        elif action_type == "executive_report":
            prompt = create_executive_report_prompt(query, context)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
        
        response_text = generate_ai_response(prompt)
        return response_text
        
    except Exception as e:
        logger.error(f"Error generating action response: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating specialized response")

@app.get("/")
async def root():
    return {"message": "RAG Pipeline API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "embedding_model": "E5-base-v2" if embedding_model else "Not loaded",
        "qdrant_client": "Connected" if qdrant_client else "Not connected",
        "gemini_model": "Ready" if gemini_model else "Not ready"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint for RAG pipeline with configurable document retrieval."""
    try:
        logger.info(f"Processing query: {request.query[:100]}...")
        
        # Determine retrieval count
        retrieval_count = request.retrieval_count if request.retrieval_count is not None else rag_config.default_retrieval_count
        logger.info(f"Using retrieval count: {retrieval_count}")
        
        # Step 1: Generate embedding for the query
        query_embedding = get_embedding(request.query)
        logger.info("Query embedding generated")
        
        # Step 2: Search Qdrant for relevant documents with configurable count
        retrieved_docs = search_qdrant(query_embedding, top_k=retrieval_count)
        logger.info(f"Retrieved {len(retrieved_docs)} documents from Qdrant")
        
        if not retrieved_docs:
            return ChatResponse(
                answer="I apologize, but I couldn't find relevant information to answer your query. Please try rephrasing your question or contact support for assistance.",
                documents_retrieved=0
            )
        
        # Step 3: Extract source information from retrieved documents
        sources = []
        for i, doc in enumerate(retrieved_docs):
            source_info = {
                "id": str(i + 1),
                "title": doc.get('metadata', {}).get('title', f"Document {i + 1}"),
                "url": doc.get('metadata', {}).get('url', '#'),
                "snippet": doc.get('content', '')[:200] + "..." if len(doc.get('content', '')) > 200 else doc.get('content', '')
            }
            sources.append(source_info)
        
        # Step 4: Generate refined response using modular approach with conversation history
        refined_answer = generate_refined_response(request.query, retrieved_docs, request.conversation_history)
        logger.info("Refined response generated with conversation context")
        
        return ChatResponse(
            answer=refined_answer,
            documents_retrieved=len(retrieved_docs),
            sources=sources
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/action", response_model=ActionResponse)
async def action_endpoint(request: ActionRequest):
    """Endpoint for handling action button clicks."""
    try:
        logger.info(f"Received action request: {request.action_type} for query: {request.query}")
        
        # Generate specialized response based on action type
        response_text = generate_action_response(request.action_type, request.query, request.context)
        
        return ActionResponse(
            result=response_text,
            action_type=request.action_type
        )
        
    except Exception as e:
        logger.error(f"Error in action endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/ingest-flood-data")
async def ingest_flood_data():
    """Endpoint to trigger flood data ingestion from Excel files."""
    try:
        logger.info("Starting flood data ingestion process...")
        
        # Import the flood data processor
        from flood_data_ingestion import FloodDataProcessor
        
        # Create processor instance and run ingestion
        processor = FloodDataProcessor()
        success = processor.process_all_flood_data()
        
        if success:
            return {
                "status": "success",
                "message": "Flood data has been successfully processed and indexed into the vector database.",
                "details": "Your Excel flood data files have been converted to embeddings and stored in Qdrant for analysis."
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail="Failed to process flood data. Check server logs for details."
            )
            
    except ImportError as e:
        logger.error(f"Failed to import flood data processor: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Flood data processor module not found. Ensure flood_data_ingestion.py exists."
        )
    except Exception as e:
        logger.error(f"Error in flood data ingestion: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error during flood data ingestion: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)