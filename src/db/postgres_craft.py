"""PostgreSQL operations for Craft documents."""
from typing import Dict, Any, List, Optional
from psycopg2.extras import Json

from src.logging_conf import logger


class PostgresCraftOps:
    """Craft document database operations."""
    
    def upsert_craft_document(self, doc_data: Dict[str, Any]) -> None:
        """
        Upsert a Craft document.
        
        Args:
            doc_data: Document data with keys:
                - id: Document ID
                - title: Document title
                - markdown_content: Full markdown content (optional)
                - isDeleted: Whether document is deleted
                - lastModifiedAt: Last modification timestamp (optional)
                - createdAt: Creation timestamp (optional)
        """
        try:
            doc_id = doc_data.get("id")
            if not doc_id:
                logger.warning("Craft document missing ID, skipping")
                return
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO craft_documents (
                        id, title, markdown_content, is_deleted,
                        craft_created_at, craft_last_modified_at, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        markdown_content = EXCLUDED.markdown_content,
                        is_deleted = EXCLUDED.is_deleted,
                        craft_created_at = COALESCE(EXCLUDED.craft_created_at, craft_documents.craft_created_at),
                        craft_last_modified_at = EXCLUDED.craft_last_modified_at,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    doc_id,
                    doc_data.get("title"),
                    doc_data.get("markdown_content"),
                    doc_data.get("isDeleted", False),
                    self._parse_dt(doc_data.get("createdAt")),
                    self._parse_dt(doc_data.get("lastModifiedAt")),
                    Json(doc_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted Craft document {doc_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert Craft document: {e}", exc_info=True)
    
    def upsert_craft_documents_batch(self, documents: List[Dict[str, Any]]) -> None:
        """
        Upsert multiple Craft documents in a batch.
        
        Args:
            documents: List of document data dicts
        """
        if not documents:
            return
        
        try:
            with self.conn.cursor() as cur:
                for doc_data in documents:
                    doc_id = doc_data.get("id")
                    if not doc_id:
                        continue
                    
                    cur.execute("""
                        INSERT INTO craft_documents (
                            id, title, markdown_content, is_deleted,
                            craft_created_at, craft_last_modified_at, raw_data
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            markdown_content = EXCLUDED.markdown_content,
                            is_deleted = EXCLUDED.is_deleted,
                            craft_created_at = COALESCE(EXCLUDED.craft_created_at, craft_documents.craft_created_at),
                            craft_last_modified_at = EXCLUDED.craft_last_modified_at,
                            raw_data = EXCLUDED.raw_data,
                            db_updated_at = NOW()
                    """, (
                        doc_id,
                        doc_data.get("title"),
                        doc_data.get("markdown_content"),
                        doc_data.get("isDeleted", False),
                        self._parse_dt(doc_data.get("createdAt")),
                        self._parse_dt(doc_data.get("lastModifiedAt")),
                        Json(doc_data)
                    ))
                
                self.conn.commit()
                logger.info(f"Batch upserted {len(documents)} Craft documents")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to batch upsert Craft documents: {e}", exc_info=True)
    
    def mark_craft_document_deleted(self, doc_id: str) -> None:
        """
        Mark a Craft document as deleted.
        
        Args:
            doc_id: Document ID to mark as deleted
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE craft_documents
                    SET is_deleted = TRUE, db_updated_at = NOW()
                    WHERE id = %s
                """, (doc_id,))
                self.conn.commit()
                logger.debug(f"Marked Craft document {doc_id} as deleted")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to mark Craft document as deleted: {e}", exc_info=True)
    
    def get_craft_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a Craft document by ID.
        
        Args:
            doc_id: Document ID
        
        Returns:
            Document data dict or None if not found
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, markdown_content, is_deleted,
                           craft_created_at, craft_last_modified_at,
                           db_created_at, db_updated_at
                    FROM craft_documents
                    WHERE id = %s
                """, (doc_id,))
                row = cur.fetchone()
                
                if row:
                    return {
                        "id": row[0],
                        "title": row[1],
                        "markdown_content": row[2],
                        "is_deleted": row[3],
                        "craft_created_at": row[4],
                        "craft_last_modified_at": row[5],
                        "db_created_at": row[6],
                        "db_updated_at": row[7]
                    }
        except Exception as e:
            logger.error(f"Failed to get Craft document {doc_id}: {e}", exc_info=True)
        
        return None
    
    def get_all_craft_document_ids(self) -> List[str]:
        """
        Get all Craft document IDs currently in the database.
        
        Returns:
            List of document IDs
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id FROM craft_documents")
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get Craft document IDs: {e}", exc_info=True)
        
        return []
    
    def search_craft_documents(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Full-text search across Craft documents.
        
        Args:
            query: Search query
            limit: Maximum results to return
        
        Returns:
            List of matching document dicts with relevance ranking
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, 
                           ts_headline('english', markdown_content, plainto_tsquery('english', %s),
                                      'MaxWords=50, MinWords=20, StartSel=<<, StopSel=>>') as snippet,
                           ts_rank(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(markdown_content, '')),
                                   plainto_tsquery('english', %s)) as rank
                    FROM craft_documents
                    WHERE is_deleted = FALSE
                      AND to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(markdown_content, '')) 
                          @@ plainto_tsquery('english', %s)
                    ORDER BY rank DESC
                    LIMIT %s
                """, (query, query, query, limit))
                
                results = []
                for row in cur.fetchall():
                    results.append({
                        "id": row[0],
                        "title": row[1],
                        "snippet": row[2],
                        "rank": float(row[3])
                    })
                return results
        except Exception as e:
            logger.error(f"Failed to search Craft documents: {e}", exc_info=True)
        
        return []


