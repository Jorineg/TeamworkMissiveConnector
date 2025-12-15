"""Craft API client supporting both Multi-Document and Full Space APIs."""
import time
from typing import List, Dict, Any, Optional
import requests

from src import settings
from src.logging_conf import logger
from src.connectors.craft_markdown_parser import parse_craft_markdown


class CraftClient:
    """Client for Craft Connect API.
    
    Supports two modes:
    - multi_document: Free tier, limited to shared documents
    - full_space: Paid tier, full space access with folders
    
    The base URL should be in the format:
    https://connect.craft.do/links/{linkId}/api/v1
    """
    
    def __init__(self):
        self.base_url = settings.CRAFT_BASE_URL
        self.api_mode = settings.CRAFT_API_MODE
        self.session = requests.Session()
    
    def is_configured(self) -> bool:
        """Check if Craft API is configured."""
        return bool(self.base_url)
    
    def is_full_space_mode(self) -> bool:
        """Check if using full space API mode."""
        return self.api_mode == "full_space"
    
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
    
    # ========== Full Space API Methods (Paid Tier) ==========
    
    def get_folders(self) -> List[Dict[str, Any]]:
        """
        Get all folders in the space (Full Space API only).
        
        Returns folder tree including built-in locations (unsorted, trash, templates).
        """
        if not self.is_configured():
            return []
        
        try:
            response = self._request("GET", "/folders")
            if response and "items" in response:
                folders = response["items"]
                logger.info(f"Fetched {len(folders)} top-level folders from Craft")
                return folders
        except Exception as e:
            logger.error(f"Error fetching folders from Craft: {e}", exc_info=True)
        
        return []
    
    def get_documents_by_location(
        self, 
        location: Optional[str] = None, 
        folder_id: Optional[str] = None,
        fetch_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get documents in a specific location or folder (Full Space API).
        
        Args:
            location: Built-in location ('unsorted', 'templates', 'daily_notes')
            folder_id: Specific folder ID
            fetch_metadata: Include metadata
        """
        if not self.is_configured():
            return []
        
        try:
            params = {"fetchMetadata": str(fetch_metadata).lower()}
            if location:
                params["location"] = location
            if folder_id:
                params["folderId"] = folder_id
            
            response = self._request("GET", "/documents", params=params)
            if response and "items" in response:
                return response["items"]
        except Exception as e:
            logger.error(f"Error fetching documents by location: {e}", exc_info=True)
        
        return []
    
    def get_document_list_with_paths(self, fetch_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Get document list with folder paths but WITHOUT content (Full Space API).
        
        Fast operation - only fetches document metadata + paths.
        Use this for backfill, then fetch content per-document in worker.
        
        Each document gets: folder_path, folder_id, location, daily_note_date
        """
        if not self.is_configured():
            return []
        
        all_documents = []
        
        # 1. Fetch from built-in locations
        for location in ['unsorted', 'templates', 'daily_notes']:
            docs = self.get_documents_by_location(location=location, fetch_metadata=fetch_metadata)
            for doc in docs:
                doc['folder_path'] = f'/{location}'
                doc['folder_id'] = None
                doc['location'] = location
                doc['daily_note_date'] = doc.get('dailyNoteDate')
            all_documents.extend(docs)
            logger.debug(f"Fetched {len(docs)} documents from /{location}")
        
        # 2. Get folder tree and traverse recursively
        folders = self.get_folders()
        
        def traverse_folder(folder: Dict, path: str = ""):
            folder_id = folder.get('id')
            folder_name = folder.get('name', 'Unknown')
            
            # Skip built-in locations (already handled above via location param)
            if folder_id in ('unsorted', 'trash', 'templates', 'daily_notes'):
                return
            
            current_path = f"{path}/{folder_name}"
            
            # Fetch documents in this folder
            docs = self.get_documents_by_location(folder_id=folder_id, fetch_metadata=fetch_metadata)
            for doc in docs:
                doc['folder_path'] = current_path
                doc['folder_id'] = folder_id
                doc['location'] = None
                doc['daily_note_date'] = doc.get('dailyNoteDate')
            all_documents.extend(docs)
            logger.debug(f"Fetched {len(docs)} documents from {current_path}")
            
            # Small delay to avoid rate limiting
            if docs:
                time.sleep(0.1)
            
            # Recurse into subfolders
            for subfolder in folder.get('folders', []):
                traverse_folder(subfolder, current_path)
        
        for folder in folders:
            traverse_folder(folder)
        
        logger.info(f"Fetched {len(all_documents)} document metadata from Craft (Full Space)")
        return all_documents
    
    def get_document_with_content(self, doc_id: str, path_info: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Get a single document with its content, optionally with pre-fetched path info.
        
        Args:
            doc_id: Document ID
            path_info: Optional dict with folder_path, folder_id, location, daily_note_date
        
        Returns:
            Document dict with markdown_content, or None if failed
        """
        if not self.is_configured():
            return None
        
        # Get metadata if not provided
        if path_info:
            doc = dict(path_info)
            doc['id'] = doc_id
        else:
            # Fallback: fetch from API (less efficient)
            if self.is_full_space_mode():
                docs = self.get_document_list_with_paths(fetch_metadata=True)
            else:
                docs = self.get_documents(fetch_metadata=True)
            
            doc = next((d for d in docs if d.get('id') == doc_id), None)
            if not doc:
                logger.warning(f"Document {doc_id} not found")
                return None
        
        # Fetch content
        raw_content = self.get_document_content(doc_id, fetch_metadata=True)
        doc['markdown_content'] = parse_craft_markdown(raw_content) if raw_content else None
        
        return doc
    
    def get_document_list(self, fetch_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Get document list based on API mode (without content).
        
        - full_space mode: Returns docs with folder paths
        - multi_document mode: Returns docs without paths
        
        Use for backfill enumeration, then fetch content per-doc in worker.
        """
        if self.is_full_space_mode():
            return self.get_document_list_with_paths(fetch_metadata=fetch_metadata)
        else:
            docs = self.get_documents(fetch_metadata=fetch_metadata)
            # Add empty path fields for consistency
            for doc in docs:
                doc.setdefault('folder_path', None)
                doc.setdefault('folder_id', None)
                doc.setdefault('location', None)
                doc.setdefault('daily_note_date', None)
            return docs
    
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


