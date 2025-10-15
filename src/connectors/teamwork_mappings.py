"""Teamwork ID-to-string mappings for people and tags."""
import json
import os
from typing import Dict, List, Any
from pathlib import Path

from src.logging_conf import logger

# Cache file paths
CACHE_DIR = Path("data")
PEOPLE_CACHE_FILE = CACHE_DIR / "teamwork_people.json"
TAGS_CACHE_FILE = CACHE_DIR / "teamwork_tags.json"


class TeamworkMappings:
    """Manager for Teamwork ID-to-string mappings."""
    
    def __init__(self):
        self._people_map: Dict[str, str] = {}
        self._tags_map: Dict[str, str] = {}
        self._load_caches()
    
    def _load_caches(self):
        """Load cached mappings from disk."""
        # Load people
        if PEOPLE_CACHE_FILE.exists():
            try:
                with open(PEOPLE_CACHE_FILE, "r", encoding="utf-8") as f:
                    self._people_map = json.load(f)
                logger.info(f"Loaded {len(self._people_map)} people mappings from cache")
            except Exception as e:
                logger.error(f"Error loading people cache: {e}")
        
        # Load tags
        if TAGS_CACHE_FILE.exists():
            try:
                with open(TAGS_CACHE_FILE, "r", encoding="utf-8") as f:
                    self._tags_map = json.load(f)
                logger.info(f"Loaded {len(self._tags_map)} tag mappings from cache")
            except Exception as e:
                logger.error(f"Error loading tags cache: {e}")
    
    def update_people(self, people_list: List[Dict[str, Any]]):
        """
        Update people mappings from API response.
        
        Args:
            people_list: List of people from Teamwork API
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Build ID -> name mapping
        for person in people_list:
            person_id = str(person.get("id", ""))
            if not person_id:
                continue
            
            # Build full name from firstName and lastName
            first_name = person.get("firstName", "")
            last_name = person.get("lastName", "")
            full_name = f"{first_name} {last_name}".strip()
            
            # Fallback to email if no name
            if not full_name:
                full_name = person.get("email", f"User {person_id}")
            
            self._people_map[person_id] = full_name
        
        # Save to disk
        try:
            with open(PEOPLE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._people_map, f, indent=2)
            logger.info(f"Saved {len(self._people_map)} people mappings to cache")
        except Exception as e:
            logger.error(f"Error saving people cache: {e}")
    
    def update_tags(self, tags_list: List[Dict[str, Any]]):
        """
        Update tag mappings from API response.
        
        Args:
            tags_list: List of tags from Teamwork API
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Build ID -> name mapping
        for tag in tags_list:
            tag_id = str(tag.get("id", ""))
            tag_name = tag.get("name", "")
            if tag_id and tag_name:
                self._tags_map[tag_id] = tag_name
        
        # Save to disk
        try:
            with open(TAGS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._tags_map, f, indent=2)
            logger.info(f"Saved {len(self._tags_map)} tag mappings to cache")
        except Exception as e:
            logger.error(f"Error saving tags cache: {e}")
    
    def get_person_name(self, person_id: Any) -> str:
        """
        Get person name by ID.
        
        Args:
            person_id: Person ID (int or string)
        
        Returns:
            Person name or the ID as fallback
        """
        person_id_str = str(person_id)
        return self._people_map.get(person_id_str, person_id_str)
    
    def get_tag_name(self, tag_id: Any) -> str:
        """
        Get tag name by ID.
        
        Args:
            tag_id: Tag ID (int or string)
        
        Returns:
            Tag name or the ID as fallback
        """
        tag_id_str = str(tag_id)
        return self._tags_map.get(tag_id_str, tag_id_str)


# Global singleton instance
_mappings_instance = None


def get_mappings() -> TeamworkMappings:
    """Get the global TeamworkMappings instance."""
    global _mappings_instance
    if _mappings_instance is None:
        _mappings_instance = TeamworkMappings()
    return _mappings_instance

