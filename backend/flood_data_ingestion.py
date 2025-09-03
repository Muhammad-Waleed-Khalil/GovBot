import pandas as pd
import os
import json
from typing import List, Dict, Any
from pathlib import Path
import logging
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FloodDataProcessor:
    def __init__(self):
        self.embedding_model = SentenceTransformer("intfloat/e5-base-v2")
        self.qdrant_client = None
        self.collection_name = os.getenv("COLLECTION_NAME", "GovTech")
        self.flood_data_dir = Path("../floods data")
        
        # Initialize Qdrant client
        self._init_qdrant()
    
    def _init_qdrant(self):
        """Initialize Qdrant client connection."""
        try:
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            
            if not qdrant_url or not qdrant_api_key:
                raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in .env file")
            
            self.qdrant_client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
            )
            logger.info("Qdrant client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise
    
    def process_excel_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Process a single Excel file and extract structured data."""
        try:
            logger.info(f"Processing file: {file_path.name}")
            
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Clean and prepare data
            df = df.dropna(how='all')  # Remove completely empty rows
            df = df.fillna('')  # Fill NaN values with empty strings
            
            documents = []
            file_category = self._categorize_file(file_path.name)
            
            # Process each row as a document
            for index, row in df.iterrows():
                # Create a comprehensive text representation of the row
                content_parts = []
                metadata = {
                    'file_name': file_path.name,
                    'category': file_category,
                    'row_index': index,
                    'data_type': 'flood_2025'
                }
                
                # Add file category context
                content_parts.append(f"Flood 2025 Data - {file_category}:")
                
                # Process each column
                for col_name, value in row.items():
                    if pd.notna(value) and str(value).strip():
                        content_parts.append(f"{col_name}: {value}")
                        # Add structured metadata
                        metadata[col_name.lower().replace(' ', '_')] = str(value)
                
                # Create document content
                content = "\n".join(content_parts)
                
                if content.strip():  # Only add non-empty documents
                    documents.append({
                        'content': content,
                        'metadata': metadata,
                        'source': f"{file_path.name}_row_{index}"
                    })
            
            logger.info(f"Extracted {len(documents)} documents from {file_path.name}")
            return documents
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            return []
    
    def _categorize_file(self, filename: str) -> str:
        """Categorize file based on filename."""
        filename_lower = filename.lower()
        
        if 'human' in filename_lower and ('losses' in filename_lower or 'injuries' in filename_lower):
            return "Human Casualties and Displacement"
        elif 'infrastructure' in filename_lower and 'damages' in filename_lower:
            return "Infrastructure Damage Assessment"
        elif 'livestock' in filename_lower or 'agriculture' in filename_lower:
            return "Agricultural and Livestock Losses"
        elif 'relief' in filename_lower and 'operations' in filename_lower:
            return "Relief and Emergency Operations"
        elif 'services' in filename_lower and 'status' in filename_lower:
            return "Essential Services Status"
        else:
            return "General Flood Data"
    
    def create_embeddings(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create embeddings for documents."""
        logger.info(f"Creating embeddings for {len(documents)} documents")
        
        for doc in documents:
            try:
                # E5 models require a specific prefix for documents
                prefixed_text = f"passage: {doc['content']}"
                embedding = self.embedding_model.encode(prefixed_text, normalize_embeddings=True)
                doc['embedding'] = embedding.tolist()
            except Exception as e:
                logger.error(f"Error creating embedding for document: {e}")
                doc['embedding'] = None
        
        # Filter out documents without embeddings
        valid_documents = [doc for doc in documents if doc['embedding'] is not None]
        logger.info(f"Successfully created embeddings for {len(valid_documents)} documents")
        
        return valid_documents
    
    def index_to_qdrant(self, documents: List[Dict[str, Any]]) -> bool:
        """Index documents to Qdrant vector database."""
        try:
            logger.info(f"Indexing {len(documents)} documents to Qdrant collection: {self.collection_name}")
            
            # Prepare points for Qdrant
            points = []
            for doc in documents:
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=doc['embedding'],
                    payload={
                        'content': doc['content'],
                        'source': doc['source'],
                        **doc['metadata']
                    }
                )
                points.append(point)
            
            # Upload points in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
                logger.info(f"Uploaded batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1}")
            
            logger.info(f"Successfully indexed {len(documents)} documents to Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing to Qdrant: {e}")
            return False
    
    def process_all_flood_data(self) -> bool:
        """Process all Excel files in the floods data directory."""
        try:
            if not self.flood_data_dir.exists():
                logger.error(f"Flood data directory not found: {self.flood_data_dir}")
                return False
            
            # Find all Excel files
            excel_files = list(self.flood_data_dir.glob("*.xlsx")) + list(self.flood_data_dir.glob("*.xls"))
            
            if not excel_files:
                logger.error("No Excel files found in floods data directory")
                return False
            
            logger.info(f"Found {len(excel_files)} Excel files to process")
            
            all_documents = []
            
            # Process each Excel file
            for file_path in excel_files:
                documents = self.process_excel_file(file_path)
                all_documents.extend(documents)
            
            if not all_documents:
                logger.error("No documents extracted from Excel files")
                return False
            
            logger.info(f"Total documents extracted: {len(all_documents)}")
            
            # Create embeddings
            documents_with_embeddings = self.create_embeddings(all_documents)
            
            if not documents_with_embeddings:
                logger.error("No valid embeddings created")
                return False
            
            # Index to Qdrant
            success = self.index_to_qdrant(documents_with_embeddings)
            
            if success:
                logger.info("Flood data processing completed successfully!")
                return True
            else:
                logger.error("Failed to index data to Qdrant")
                return False
                
        except Exception as e:
            logger.error(f"Error in process_all_flood_data: {e}")
            return False
    
    def save_processed_data(self, documents: List[Dict[str, Any]], output_file: str = "processed_flood_data.json"):
        """Save processed documents to JSON file for backup."""
        try:
            # Remove embeddings for JSON serialization (they're large)
            documents_for_json = []
            for doc in documents:
                doc_copy = doc.copy()
                if 'embedding' in doc_copy:
                    del doc_copy['embedding']
                documents_for_json.append(doc_copy)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(documents_for_json, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Processed data saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving processed data: {e}")

def main():
    """Main function to run the flood data processing."""
    processor = FloodDataProcessor()
    
    logger.info("Starting flood data processing...")
    success = processor.process_all_flood_data()
    
    if success:
        logger.info("✅ Flood data processing completed successfully!")
        logger.info("Your flood data is now indexed and ready for analysis.")
    else:
        logger.error("❌ Flood data processing failed. Check the logs for details.")

if __name__ == "__main__":
    main()