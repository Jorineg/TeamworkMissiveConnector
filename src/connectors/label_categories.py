"""Label and tag categorization based on configurable mappings."""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from src import settings
from src.logging_conf import logger


class LabelCategories:
    """
    Manages label/tag categorization based on configured mappings.
    
    Supports both exact matches and simple wildcard patterns:
    - * matches zero or more characters
    - ? matches exactly one character
    """
    
    def __init__(self, mapping_file: Optional[Path] = None):
        """
        Initialize label categories from a JSON mapping file.
        
        Args:
            mapping_file: Path to the JSON mapping file. If None, uses default location.
        """
        if mapping_file is None:
            mapping_file = settings.DATA_DIR / "label_categories.json"
        
        self.mapping_file = mapping_file
        self.categories: Dict[str, List[str]] = {}
        self._load_mappings()
    
    def _load_mappings(self) -> None:
        """Load category mappings from JSON file."""
        if not self.mapping_file.exists():
            logger.warning(f"Label categories file not found: {self.mapping_file}")
            logger.info("Label categorization will be disabled. Create the file to enable this feature.")
            self.categories = {}
            return
        
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Normalize data: convert string patterns to lists
            for category, patterns in data.items():
                if isinstance(patterns, str):
                    self.categories[category] = [patterns]
                elif isinstance(patterns, list):
                    self.categories[category] = patterns
                else:
                    logger.warning(f"Invalid pattern type for category '{category}': {type(patterns)}")
                    self.categories[category] = []
            
            logger.info(f"Loaded {len(self.categories)} label categories from {self.mapping_file}")
            logger.debug(f"Categories: {list(self.categories.keys())}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse label categories JSON: {e}", exc_info=True)
            self.categories = {}
        except Exception as e:
            logger.error(f"Failed to load label categories: {e}", exc_info=True)
            self.categories = {}
    
    def reload(self) -> None:
        """Reload mappings from file."""
        self._load_mappings()
    
    def get_category_names(self) -> List[str]:
        """Get list of all category names."""
        return list(self.categories.keys())
    
    def categorize(self, labels: List[str]) -> Dict[str, List[str]]:
        """
        Categorize a list of labels/tags based on configured patterns.
        
        Args:
            labels: List of label/tag strings
        
        Returns:
            Dictionary mapping category names to lists of matching labels
        """
        if not self.categories:
            return {}
        
        result: Dict[str, List[str]] = {category: [] for category in self.categories}
        
        for label in labels:
            for category, patterns in self.categories.items():
                if self._matches_any_pattern(label, patterns):
                    result[category].append(label)
        
        return result
    
    def _matches_any_pattern(self, label: str, patterns: List[str]) -> bool:
        """
        Check if a label matches any of the given patterns.
        
        Args:
            label: Label to check
            patterns: List of patterns (can include * and ? wildcards)
        
        Returns:
            True if label matches any pattern
        """
        for pattern in patterns:
            if self._matches_pattern(label, pattern):
                return True
        return False
    
    def _matches_pattern(self, label: str, pattern: str) -> bool:
        """
        Check if a label matches a pattern.
        
        Supports simple wildcards:
        - * matches zero or more characters
        - ? matches exactly one character
        - All other characters are matched literally (case-sensitive)
        
        Args:
            label: Label to check
            pattern: Pattern with optional wildcards
        
        Returns:
            True if label matches pattern
        """
        # Convert wildcard pattern to regex
        # Escape special regex characters except * and ?
        regex_pattern = re.escape(pattern)
        
        # Replace escaped wildcards with regex equivalents
        regex_pattern = regex_pattern.replace(r'\*', '.*')  # * -> .*
        regex_pattern = regex_pattern.replace(r'\?', '.')   # ? -> .
        
        # Anchor pattern to match entire string
        regex_pattern = f'^{regex_pattern}$'
        
        try:
            return bool(re.match(regex_pattern, label))
        except re.error as e:
            logger.error(f"Invalid regex pattern generated from '{pattern}': {e}")
            return False


# Global instance
_instance: Optional[LabelCategories] = None


def get_label_categories() -> LabelCategories:
    """Get the global LabelCategories instance."""
    global _instance
    if _instance is None:
        _instance = LabelCategories()
    return _instance


def reload_label_categories() -> None:
    """Reload the global LabelCategories instance from file."""
    global _instance
    if _instance is not None:
        _instance.reload()
    else:
        _instance = LabelCategories()

