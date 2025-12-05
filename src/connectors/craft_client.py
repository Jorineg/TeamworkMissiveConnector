"""Craft Multi-Document API client."""
import time
from typing import List, Dict, Any, Optional
import requests

from src import settings
from src.logging_conf import logger


class CraftClient:
    """Client for Craft Multi-Document API.
    
    This client uses the Craft Connect API for multi-document access.
    The base URL should be in the format:
    https://connect.craft.do/links/{linkId}/api/v1
    """
    
    def __init__(self):
        self.base_url = settings.CRAFT_BASE_URL
        self.session = requests.Session()
    
    def is_configured(self) -> bool:
        """Check if Craft API is configured."""
        return bool(self.base_url)
    
    def get_documents(self, fetch_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Get all documents accessible through the multi-document connection.
        
        Args:
            fetch_metadata: Whether to include metadata (lastModifiedAt, createdAt)
        
        Returns:
            List of document dictionaries with id, title, isDeleted, and optional metadata
        """
        if not self.is_configured():
            logger.warning("Craft API not configured. Skipping document fetch.")
            return []
        
        try:
            params = {"fetchMetadata": str(fetch_metadata).lower()}
            response = self._request("GET", "/documents", params=params)
            
            if response and "items" in response:
                docs = response["items"]
                logger.info(f"Fetched {len(docs)} documents from Craft")
                return docs
        except Exception as e:
            logger.error(f"Error fetching documents from Craft: {e}", exc_info=True)
        
        return []
    
    def get_document_content(self, document_id: str, fetch_metadata: bool = True) -> Optional[str]:
        """
        Get document content as markdown.
        
        Args:
            document_id: The document ID (same as root block ID)
            fetch_metadata: Whether to include metadata for blocks
        
        Returns:
            Document content as markdown string, or None if error
        """
        if not self.is_configured():
            return None
        
        try:
            params = {
                "id": document_id,
                "fetchMetadata": str(fetch_metadata).lower()
            }
            
            # Request markdown format
            response = self._request(
                "GET", 
                "/blocks", 
                params=params,
                accept="text/markdown"
            )
            
            # Response is raw markdown text when using text/markdown accept header
            if response is not None:
                return response
                
        except Exception as e:
            logger.error(f"Error fetching document content {document_id} from Craft: {e}", exc_info=True)
        
        return None
    
    def get_document_json(self, document_id: str, fetch_metadata: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get document content as structured JSON.
        
        Args:
            document_id: The document ID (same as root block ID)
            fetch_metadata: Whether to include metadata for blocks
        
        Returns:
            Document as structured JSON, or None if error
        """
        if not self.is_configured():
            return None
        
        try:
            params = {
                "id": document_id,
                "fetchMetadata": str(fetch_metadata).lower()
            }
            
            response = self._request("GET", "/blocks", params=params)
            
            if response:
                return response
                
        except Exception as e:
            logger.error(f"Error fetching document JSON {document_id} from Craft: {e}", exc_info=True)
        
        return None
    
    def get_all_documents_with_content(self, fetch_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Get all documents with their full markdown content.
        
        This is the main method for polling - fetches document list and then
        retrieves full content for each document.
        
        Args:
            fetch_metadata: Whether to include metadata
        
        Returns:
            List of document dicts with 'markdown_content' added
        """
        documents = self.get_documents(fetch_metadata=fetch_metadata)
        
        if not documents:
            return []
        
        # Fetch content for each non-deleted document
        for doc in documents:
            if doc.get("isDeleted", False):
                doc["markdown_content"] = None
                continue
            
            doc_id = doc.get("id")
            if doc_id:
                markdown_content = self.get_document_content(doc_id, fetch_metadata=fetch_metadata)
                doc["markdown_content"] = markdown_content
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
        
        logger.info(f"Fetched content for {len(documents)} documents from Craft")
        return documents
    
    def search_documents(
        self, 
        include: Optional[str] = None,
        regexps: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        fetch_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search across all documents.
        
        Args:
            include: Search terms to include
            regexps: Regex patterns to search for
            document_ids: Filter to specific document IDs
            fetch_metadata: Include document metadata in results
        
        Returns:
            List of search result matches
        """
        if not self.is_configured():
            return []
        
        try:
            params = {"fetchMetadata": str(fetch_metadata).lower()}
            
            if include:
                params["include"] = include
            if regexps:
                params["regexps"] = regexps
            if document_ids:
                params["documentIds"] = ",".join(document_ids)
            
            response = self._request("GET", "/documents/search", params=params)
            
            if response and "items" in response:
                return response["items"]
        except Exception as e:
            logger.error(f"Error searching Craft documents: {e}", exc_info=True)
        
        return []
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
        retry_count: int = 0
    ) -> Optional[Any]:
        """
        Make an API request with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON body
            accept: Accept header value
            retry_count: Current retry attempt
        
        Returns:
            Response JSON/text or None
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            headers = {"Accept": accept}
            
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=60  # Longer timeout for potentially large documents
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited by Craft API. Waiting {retry_after}s...")
                time.sleep(retry_after)
                return self._request(method, endpoint, params, json_data, accept, retry_count)
            
            # Handle server errors with exponential backoff
            if response.status_code >= 500 and retry_count < 3:
                wait_time = 2 ** retry_count
                logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._request(method, endpoint, params, json_data, accept, retry_count + 1)
            
            # Log errors
            if response.status_code >= 400:
                body_preview = response.text[:2000] if response.text else "<no body>"
                logger.error(f"Craft API error {response.status_code} for {url}: {body_preview}")
            
            response.raise_for_status()
            
            # Return appropriate format based on accept header
            if accept == "text/markdown":
                return response.text
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Craft API request failed: {e}", exc_info=True)
            
            # Retry on connection errors
            if retry_count < 3 and isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                wait_time = 2 ** retry_count
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._request(method, endpoint, params, json_data, accept, retry_count + 1)
            
            return None

