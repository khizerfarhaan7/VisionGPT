import os
import json
import logging
import traceback
from pathlib import Path
import httpx
import faiss
from typing import Any, Optional, List, Dict
from fastapi import HTTPException, status
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)

async def rewrite_query(question: str, history: list) -> str:
    """
    Rewrite the user's question into a standalone question based on recent conversation history.
    Resolves pronouns (it, he, she, they, this, that, its) to the correct subject context.
    If the question is already standalone, returns it unchanged.
    """
    if not history:
        return question

    # Keep only the last 4 turns to avoid context overflow and focus on immediate context
    recent_history = history[-4:]
    history_str = ""
    for msg in recent_history:
        role = "User" if msg.role == "user" else "Assistant"
        history_str += f"{role}: {msg.content}\n"

    system_prompt = (
        "You are an expert query rewriter. Your task is to analyze the conversation history and the user's latest follow-up question,\n"
        "then rewrite it into a single standalone question that can be understood without the conversation history.\n"
        "Follow these rules strictly:\n"
        "1. Resolve any pronouns (such as 'he', 'she', 'it', 'they', 'this', 'that', 'its') to the specific subjects mentioned in the history.\n"
        "2. Preserve the core intent and meaning of the user's question.\n"
        "3. Do not answer the question. Only output the rewritten question.\n"
        "4. If the question is already standalone and does not reference context or pronouns from the history, output it exactly as is.\n"
        "5. Output ONLY the rewritten question text. Do not add introductions, explanations, quotes, or notes."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Conversation History:\n{history_str}\nFollow-up Question: {question}\n\nRewritten Standalone Question:"}
    ]

    try:
        ollama_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        ollama_payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(ollama_url, json=ollama_payload)
            if response.status_code == 200:
                res_data = response.json()
                rewritten = res_data.get("message", {}).get("content", "").strip()
                # Clean up any potential surrounding quotes
                if rewritten.startswith('"') and rewritten.endswith('"'):
                    rewritten = rewritten[1:-1].strip()
                if rewritten.startswith("'") and rewritten.endswith("'"):
                    rewritten = rewritten[1:-1].strip()
                logger.info(f"Original Query: '{question}' -> Standalone Query: '{rewritten}'")
                return rewritten if rewritten else question
            else:
                logger.warning(f"Ollama query rewriter returned status code {response.status_code}, using original question.")
                return question
    except Exception as e:
        logger.error(f"Failed to rewrite query: {str(e)}, using original question.")
        return question

from app.core.model_manager import model_manager

def get_embedding_model():
    """
    Retrieves the shared SentenceTransformer embedding model via ModelManager.
    """
    return model_manager.get_embedding_model()

def exclude_embeddings(data):
    if isinstance(data, dict):
        return {
            k: exclude_embeddings(v) 
            for k, v in data.items() 
            if "embed" not in k.lower()
        }
    elif isinstance(data, list):
        return [exclude_embeddings(item) for item in data]
    return data

def log_http_exception_details(e: Exception, ollama_url: str, model_name: str, payload: dict):
    tb = traceback.format_exc()
    exc_type = type(e).__name__
    exc_msg = getattr(e, "detail", str(e))
    cleaned_payload = exclude_embeddings(payload)
    logger.error(
        f"Local LLM Error Details:\n"
        f"Exception Type: {exc_type}\n"
        f"Exception Message: {exc_msg}\n"
        f"Ollama URL: {ollama_url}\n"
        f"Model Name: {model_name}\n"
        f"Request Payload: {cleaned_payload}\n"
        f"Traceback:\n{tb}"
    )

def merge_and_filter_chunks(retrieved_items: list, distance_threshold: float = 1.3) -> list:
    """
    Filters retrieved chunks by distance threshold (L2 distance), deduplicates them,
    sorts them chronologically (by chunk index), and merges consecutive neighbouring chunks.
    """
    # 1. Filter by distance threshold
    filtered_items = [item for item in retrieved_items if item["similarity_score"] <= distance_threshold]
    
    # 2. Deduplicate by chunk_id
    seen_ids = set()
    deduped_items = []
    for item in filtered_items:
        cid = item["chunk_id"]
        if cid not in seen_ids:
            seen_ids.add(cid)
            deduped_items.append(item)
            
    if not deduped_items:
        return []
        
    # 3. Parse chunk indexes and sort chronologically/consecutively
    def get_chunk_index(item):
        cid = item["chunk_id"]
        try:
            return int(cid.split("_")[1])
        except (IndexError, ValueError):
            return 999999
            
    # Sort deduped items by their sequential chunk index
    deduped_items.sort(key=get_chunk_index)
    
    # 4. Merge consecutive neighbouring chunks
    merged_items = []
    current_group = []
    
    for item in deduped_items:
        idx = get_chunk_index(item)
        if not current_group:
            current_group.append((idx, item))
        else:
            last_idx, last_item = current_group[-1]
            # Consecutive check (index difference is exactly 1)
            if idx == last_idx + 1:
                current_group.append((idx, item))
            else:
                # Finalize current group
                merged_items.append(compile_merged_group(current_group))
                current_group = [(idx, item)]
                
    if current_group:
        merged_items.append(compile_merged_group(current_group))
        
    # 5. Rerank final merged items by their best similarity score (L2 distance ascending)
    merged_items.sort(key=lambda x: x["similarity_score"])
    
    return merged_items

def compile_merged_group(group: list) -> dict:
    """
    Compiles a group of consecutive chunks into a single merged chunk.
    """
    if len(group) == 1:
        return group[0][1]
        
    items = [g[1] for g in group]
    
    # Merge text contents
    merged_text = " ".join([item["text"].strip() for item in items])
    
    # Merge identifiers
    merged_id = f"chunk_{group[0][0]}-{group[-1][0]}"
    
    # Merge similarity scores (best match score)
    best_score = min(item["similarity_score"] for item in items)
    
    merged_chunk = {
        "chunk_id": merged_id,
        "page": items[0]["page"],
        "similarity_score": best_score,
        "text": merged_text
    }
    
    # Merge start and end times if they exist (audio chunks)
    start_times = [item["start_time"] for item in items if "start_time" in item]
    end_times = [item["end_time"] for item in items if "end_time" in item]
    
    if start_times:
        merged_chunk["start_time"] = min(start_times)
    if end_times:
        merged_chunk["end_time"] = max(end_times)
        
    return merged_chunk

async def execute_local_rag(vector_store_dir: Path, question: str, history: list, system_prompt: str, k: int = 3, session_id: Any = None):
    # 0. Rewrite the query if history exists to resolve pronouns and produce standalone query
    standalone_question = await rewrite_query(question, history)

    # 1. Load FAISS index and metadata
    index_path = vector_store_dir / "faiss.index"
    metadata_path = vector_store_dir / "metadata.json"
    
    if not index_path.exists() or not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Knowledge base is not indexed. Please build it first."
        )
        
    try:
        index = faiss.read_index(str(index_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load vector store or metadata: {str(e)}"
        )
        
    # 2. Generate embedding for query
    try:
        model = get_embedding_model()
        query_vector = model.encode([standalone_question], convert_to_numpy=True).astype("float32")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}"
        )

    # Validate vector index dimension compatibility
    if hasattr(index, "d") and index.d != query_vector.shape[1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Incompatible vector store index. The FAISS index dimension ({index.d}d) "
                f"does not match active embedding model '{settings.EMBEDDING_MODEL}' ({query_vector.shape[1]}d). "
                "Please re-index this document or set VISIONGPT_PROFILE=local."
            )
        )
        
    # 3. Search FAISS index (increase retrieve depth to get potential consecutive chunks to merge)
    try:
        search_k = max(k * 2, 6)
        distances, indices = index.search(query_vector, search_k)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FAISS search execution failed: {str(e)}"
        )
        
    # 4. Retrieve chunks, filter by similarity threshold, deduplicate, merge consecutive, and construct prompt context
    raw_retrieved = []
    for rank, idx_val in enumerate(indices[0]):
        if idx_val == -1 or idx_val >= len(metadata):
            continue
        chunk_info = metadata[idx_val]
        dist = float(distances[0][rank])
        
        item = {
            "chunk_id": chunk_info["chunk_id"],
            "page": str(chunk_info["page"]),
            "similarity_score": dist,
            "text": chunk_info["text"]
        }
        if "start_time" in chunk_info:
            item["start_time"] = chunk_info["start_time"]
        if "end_time" in chunk_info:
            item["end_time"] = chunk_info["end_time"]
        raw_retrieved.append(item)
        
    # Merge and filter using L2 distance threshold = 1.3
    merged_retrieved = merge_and_filter_chunks(raw_retrieved, distance_threshold=1.3)
    
    sources = []
    context_blocks = []
    
    # Take only the top-k merged results to avoid overflowing context window
    for item in merged_retrieved[:k]:
        source_item = {
            "chunk_id": item["chunk_id"],
            "page": item["page"],
            "similarity_score": item["similarity_score"]
        }
        if "start_time" in item:
            source_item["start_time"] = item["start_time"]
        if "end_time" in item:
            source_item["end_time"] = item["end_time"]
        sources.append(source_item)
        context_blocks.append(f"Source: {item['chunk_id']} (Page {item['page']})\n{item['text']}")
        
    rag_context = "\n\n---\n\n".join(context_blocks)
    
    # 5. Formulate instructions and messages list for Ollama
    messages = [{"role": "system", "content": system_prompt}]
    
    # Feed conversation history (keep only the last 1 user and last 2 assistant messages from history)
    history_messages = []
    user_count = 0
    assistant_count = 0
    for msg in reversed(history or []):
        if msg.role == "user":
            if user_count < 1:
                history_messages.append(msg)
                user_count += 1
        elif msg.role == "assistant":
            if assistant_count < 2:
                history_messages.append(msg)
                assistant_count += 1
                
    history_messages.reverse()
    
    for msg in history_messages:
        role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})
        
    # Add final query turn incorporating RAG context
    final_content = (
        f"Context from document:\n{rag_context}\n\n"
        f"Question: {standalone_question}"
    )
    messages.append({"role": "user", "content": final_content})
    
    # Query Ollama model
    ollama_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    ollama_payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }
    
    # Log prompt statistics
    total_messages = len(messages)
    total_chars = sum(len(msg["content"]) for msg in messages)
    estimated_tokens = int(total_chars / 4)
    logger.info(
        f"Prompt stats for Ollama query:\n"
        f"Total messages sent to Ollama: {total_messages}\n"
        f"Total characters in the prompt: {total_chars}\n"
        f"Estimated token count: {estimated_tokens}"
    )
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(ollama_url, json=ollama_payload)
            if response.status_code != 200:
                logger.error(
                    f"Ollama returned a non-200 response:\n"
                    f"Status Code: {response.status_code}\n"
                    f"Response Body: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Local LLM service returned status code {response.status_code}. Please verify Ollama is running and has model {settings.OLLAMA_MODEL} loaded."
                )
            
            res_data = response.json()
            logger.info(f"Ollama raw JSON response: {res_data}")
            answer = res_data.get("message", {}).get("content", "").strip()

            if session_id:
                try:
                    import uuid
                    valid_sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
                    from app.services.workspace_service import WorkspaceService
                    from app.core.database import SessionLocal
                    async with SessionLocal() as db:
                        await WorkspaceService.persist_chat_message(db, valid_sid, "user", question)
                        await WorkspaceService.persist_chat_message(db, valid_sid, "assistant", answer, sources=sources)
                except Exception as p_err:
                    logger.warning(f"Failed to persist chat turn for session '{session_id}': {p_err}")

            return {
                "success": True,
                "answer": answer,
                "sources": sources
            }
    except HTTPException as e:
        log_http_exception_details(e, ollama_url, settings.OLLAMA_MODEL, ollama_payload)
        raise e
    except httpx.RequestError as e:
        log_http_exception_details(e, ollama_url, settings.OLLAMA_MODEL, ollama_payload)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Local LLM service (Ollama) is unavailable: {str(e)}. Please verify Ollama is running on {settings.OLLAMA_BASE_URL}."
        )
