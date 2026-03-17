import os
from pathlib import Path
import array
import logging
from typing import Any
from langchain_oci import ChatOCIGenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_oci.embeddings import OCIGenAIEmbeddings

from database.connections import RAGDBConnection

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
KNOWLEDGE_ROOT = (Path(__file__).resolve().parents[1] / "knowledge").resolve()
EMBED_MODEL = "cohere.embed-v4.0"
DEFAULT_CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "700"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "120"))
DEFAULT_EMBED_BATCH_SIZE = int(os.getenv("KNOWLEDGE_EMBED_BATCH_SIZE", "192"))
DEFAULT_INSERT_BATCH_SIZE = int(os.getenv("KNOWLEDGE_INSERT_BATCH_SIZE", "200"))


def _normalize_embedding_source(raw_source: str) -> str:
    metadata_source = raw_source
    try:
        raw_path = Path(raw_source).resolve()
        if KNOWLEDGE_ROOT in raw_path.parents:
            metadata_source = str(raw_path.relative_to(KNOWLEDGE_ROOT)).replace("\\", "/")
    except Exception:
        metadata_source = raw_source.replace("\\", "/")
    return metadata_source


class GenAIProvider:
    """Singleton provider for OCI GenAI LLM clients."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        pass

    def build_oci_client(self, model_id:str="xai.grok-4-fast-non-reasoning", model_kwargs:dict[str,Any] = {}):
        client = ChatOCIGenAI(
            model_id=model_id,
            service_endpoint=os.getenv("SERVICE_ENDPOINT"),
            compartment_id=os.getenv("COMPARTMENT_ID"),
            model_kwargs=model_kwargs,
            auth_profile="API-USER",
        )

        return client
    
    def update_oci_client(
        self, 
        client:ChatOCIGenAI, 
        model_id:str="xai.grok-4-fast-non-reasoning", 
        model_kwargs:dict[str,Any] = {}
    ):
        client.model_id=model_id
        client.model_kwargs=model_kwargs

class GenAIEmbedProvider:
    """Singleton provider for OCI GenAI Embeddings with optional PDF processing capabilities."""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if GenAIEmbedProvider._initialized:
            return
        GenAIEmbedProvider._initialized = True
        
        self.embed_client = OCIGenAIEmbeddings(
            model_id=EMBED_MODEL,
            service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
            compartment_id=os.getenv("COMPARTMENT_ID"),
            auth_profile=os.getenv("AUTH_PROFILE")
        )
        # PDF processing attributes - initialized when load_pdf is called
        self.docs = None
        self.splits = None
        self.texts = None
        self.embed_response = None
    
    def load_pdf(self, pdf_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        """Load and process a PDF file for embedding.

        Args:
            pdf_path: Path to the PDF file to load.
            chunk_size: Size of text chunks for splitting.
            chunk_overlap: Overlap between chunks.

        Returns:
            List of embeddings for the document chunks.
        """
        logger.info(f"Loading PDF from {pdf_path}")
        loader = PyPDFLoader(pdf_path)
        self.docs = loader.load()
        logger.info(f"Loaded {len(self.docs)} pages from PDF")

        logger.info(f"Splitting documents (chunk_size={chunk_size}, overlap={chunk_overlap})")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True
        )
        self.splits = text_splitter.split_documents(self.docs)
        self.texts = [chunk.page_content for chunk in self.splits]
        logger.info(f"Created {len(self.splits)} text chunks")

        logger.info(f"Generating embeddings for {len(self.texts)} chunks using {EMBED_MODEL}")
        self.embed_response = self.embed_client.embed_documents(self.texts)
        logger.info(f"Generated {len(self.embed_response)} embeddings")

        return self.embed_response

    def load_and_insert_pdf(self, pdf_path: str, db_conn: RAGDBConnection, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        """Load PDF, generate embeddings, and insert into database."""
        logger.info(f"Starting load_and_insert_pdf for {pdf_path}")
        try:
            embeddings = self.load_pdf(pdf_path, chunk_size, chunk_overlap)

            logger.info(f"Inserting {len(embeddings)} embeddings into database")
            with db_conn.get_connection() as conn:
                db_conn.insert_embedding(conn, embeddings, self.texts, self.splits)
            logger.info(f"Successfully inserted embeddings for {pdf_path}")

            return embeddings
        except Exception as e:
            logger.exception(f"Error in load_and_insert_pdf for {pdf_path}: {e}")
            raise

    def load_and_insert_pdf_with_progress(
        self,
        pdf_path: str,
        db_conn: RAGDBConnection,
        progress_callback=None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        embed_batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
        insert_batch_size: int = DEFAULT_INSERT_BATCH_SIZE,
    ):
        """Load PDF, generate embeddings, and insert with detailed progress updates.
        
        Args:
            pdf_path: Path to PDF file
            db_conn: Database connection
            progress_callback: Optional callable(stage, percent, message) for progress updates
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap
            embed_batch_size: Number of chunks to embed per API call
        """
        def report(stage: str, pct: int, msg: str):
            if progress_callback:
                progress_callback(stage, pct, msg)
            logger.info(f"[{stage}] {pct}% - {msg}")

        try:
            # Stage 1: Extract & chunk (0-30%)
            report("extract", 5, "Loading PDF pages")
            loader = PyPDFLoader(pdf_path)
            self.docs = loader.load()
            num_pages = len(self.docs)
            report("extract", 10, f"Loaded {num_pages} pages")

            report("chunk", 15, f"Splitting into chunks (size={chunk_size}, overlap={chunk_overlap})")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                add_start_index=True
            )
            self.splits = text_splitter.split_documents(self.docs)
            self.texts = [chunk.page_content for chunk in self.splits]
            num_chunks = len(self.texts)
            report("chunk", 30, f"Created {num_chunks} chunks")

            # Stage 2: Embed in batches (30-80%)
            self.embed_response = []
            total_batches = (num_chunks + embed_batch_size - 1) // embed_batch_size
            for batch_idx in range(0, num_chunks, embed_batch_size):
                batch_texts = self.texts[batch_idx:batch_idx + embed_batch_size]
                batch_num = (batch_idx // embed_batch_size) + 1
                report("embed", 30 + int((batch_idx / num_chunks) * 50), f"Embedding batch {batch_num}/{total_batches} ({len(batch_texts)} chunks)")
                
                batch_embeddings = self.embed_client.embed_documents(batch_texts)
                self.embed_response.extend(batch_embeddings)

            report("embed", 80, f"Generated {len(self.embed_response)} embeddings")

            # Stage 3: Insert into DB (80-100%)
            report("insert", 82, f"Inserting {len(self.embed_response)} embeddings into database")
            insert_sql = (
                f"INSERT INTO {db_conn.table_prefix}_embedding "
                f"(text, embedding_vector, chapter, section, source) VALUES (:1, :2, :3, :4, :5)"
            )
            with db_conn.get_connection() as conn:
                with conn.cursor() as cur:
                    batch_rows: list[list[Any]] = []
                    inserted = 0
                    total_embeddings = len(self.embed_response)

                    for i, emb in enumerate(self.embed_response):
                        split = self.splits[i]
                        raw_source = str(split.metadata.get("source", "pdf-doc"))
                        batch_rows.append(
                            [
                                self.texts[i][:3900],
                                array.array("f", emb),
                                raw_source[:100] if raw_source else "unknown",
                                int(split.metadata.get("page", 0) or 0),
                                _normalize_embedding_source(raw_source),
                            ]
                        )

                        should_flush = len(batch_rows) >= insert_batch_size or i == total_embeddings - 1
                        if not should_flush:
                            continue

                        cur.executemany(insert_sql, batch_rows)
                        conn.commit()
                        inserted += len(batch_rows)
                        batch_rows = []

                        insert_pct = 82 + int((inserted / total_embeddings) * 18)
                        report("insert", insert_pct, f"Inserted {inserted}/{total_embeddings} chunks")

            report("done", 100, f"Completed embedding for {num_chunks} chunks")
            return self.embed_response

        except Exception as e:
            logger.exception(f"Error in load_and_insert_pdf_with_progress for {pdf_path}: {e}")
            raise

    def load_all_rag_documents(self, db_conn: RAGDBConnection, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        """Load all PDF documents from the rag_docs directory and insert into database."""
        import os
        rag_docs_dir = "./core/rag_docs/"

        # Create table if it doesn't exist
        with db_conn.get_connection() as conn:
            db_conn.create_table(conn)

        pdf_files = [f for f in os.listdir(rag_docs_dir) if f.endswith('.pdf')]
        loaded_count = 0

        for pdf_file in pdf_files:
            pdf_path = os.path.join(rag_docs_dir, pdf_file)
            print(f"Loading and indexing {pdf_file}...")
            try:
                self.load_and_insert_pdf(pdf_path, db_conn, chunk_size, chunk_overlap)
                loaded_count += 1
            except Exception as e:
                print(f"Error loading {pdf_file}: {e}")

        print(f"Successfully loaded and indexed {loaded_count} documents.")
