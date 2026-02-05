"""
Name cleaning and normalization utilities for entity extraction.
Handles OCR errors, malformed extractions, and normalizes names.
"""
import re
from typing import Optional, List, Tuple
from difflib import SequenceMatcher


class NameCleaner:
    """Clean and normalize person names extracted from documents."""

    # Common OCR errors for 'J' in Jeffrey
    OCR_J_ERRORS = ['F', 'I', 'l', '/', 'A']

    # Words that indicate this isn't a valid person name
    INVALID_PREFIXES = [
        'the ', 'this ', 'that ', 'a ', 'an ', 'no ', 'of', 'vs ', 'v. ',
        'inmate ', 'defendant ', 'plaintiff ', 'case ', 'matter ',
    ]

    # Suffixes to strip (possessives, punctuation artifacts)
    STRIP_SUFFIXES = ["'s", "'s", "'", ".", ",", "/", "-", ":", ";"]

    # Known important names and their canonical forms
    CANONICAL_NAMES = {
        'jeffrey epstein': 'Jeffrey Epstein',
        'epstein jeffrey': 'Jeffrey Epstein',
        'epstein jeffrey p': 'Jeffrey Epstein',
        'j epstein': 'Jeffrey Epstein',
        'j. epstein': 'Jeffrey Epstein',
        'ghislaine maxwell': 'Ghislaine Maxwell',
        'maxwell ghislaine': 'Ghislaine Maxwell',
        'virginia giuffre': 'Virginia Giuffre',
        'virginia roberts': 'Virginia Giuffre',
        'alan dershowitz': 'Alan Dershowitz',
        'prince andrew': 'Prince Andrew',
        'les wexner': 'Les Wexner',
        'leslie wexner': 'Leslie Wexner',
        'jean luc brunel': 'Jean-Luc Brunel',
    }

    # Additional patterns that should resolve to canonical names
    PATTERN_CANONICALS = [
        (r'jeffrey\s+e\.?\s+epstein', 'Jeffrey Epstein'),
        (r'j\.?\s*epstein', 'Jeffrey Epstein'),
        (r'epstein,?\s*jeffrey', 'Jeffrey Epstein'),
    ]

    def clean_name(self, name: str) -> Optional[str]:
        """
        Clean and normalize a person name.

        Args:
            name: Raw extracted name

        Returns:
            Cleaned name or None if invalid
        """
        if not name:
            return None

        # Remove newlines and normalize whitespace
        name = ' '.join(name.split())

        # Skip if too short
        if len(name) < 2:
            return None

        # Skip if it's just numbers or numbers with "Epstein"
        if re.match(r'^\d+\s+\w+$', name):
            return None

        # Remove invalid prefixes
        name_lower = name.lower()
        for prefix in self.INVALID_PREFIXES:
            if name_lower.startswith(prefix):
                name = name[len(prefix):].strip()
                name_lower = name.lower()

        # Strip possessives and punctuation artifacts
        for suffix in self.STRIP_SUFFIXES:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()

        # Remove email addresses concatenated with names
        name = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', name).strip()

        # Remove trailing artifacts like "(Recommended)", numbers, etc.
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name)
        name = re.sub(r'\s+\d+\s*$', '', name)

        # Skip if name is all uppercase and contains newline artifacts
        if '\n' in name or '\\n' in name:
            name = name.replace('\n', ' ').replace('\\n', ' ')
            name = ' '.join(name.split())

        # Skip common non-name patterns
        if self._is_invalid_name(name):
            return None

        # Check for canonical names
        canonical = self._get_canonical_name(name)
        if canonical:
            return canonical

        # Proper case if all uppercase
        if name.isupper():
            name = self._proper_case(name)

        return name.strip() if len(name.strip()) > 1 else None

    def _is_invalid_name(self, name: str) -> bool:
        """Check if name is likely not a valid person name."""
        name_lower = name.lower().strip()

        # Single word that's a common noun
        common_nouns = ['case', 'matter', 'defendant', 'plaintiff', 'witness',
                       'inmate', 'court', 'judge', 'returns', 'normal', 'plea',
                       'bald', 'founds', 'trustee', 'helper']
        if name_lower in common_nouns:
            return True

        # Contains only special characters or numbers
        if re.match(r'^[\d\W]+$', name):
            return True

        # Looks like a file path or URL
        if '/' in name and ('.' in name or ':' in name):
            return True

        # Multiple people concatenated (contains MAXWELL and EPSTEIN separately)
        if 'maxwell' in name_lower and 'epstein' in name_lower:
            # Unless it's clearly one or the other
            if name_lower.count('maxwell') > 1 or name_lower.count('epstein') > 1:
                return True

        return False

    def _get_canonical_name(self, name: str) -> Optional[str]:
        """
        Get canonical form if this is a known important name.
        Uses fuzzy matching to handle OCR errors.
        """
        name_lower = name.lower().strip()

        # Direct match
        if name_lower in self.CANONICAL_NAMES:
            return self.CANONICAL_NAMES[name_lower]

        # Pattern match
        for pattern, canonical in self.PATTERN_CANONICALS:
            if re.match(pattern, name_lower):
                return canonical

        # Fuzzy match for known names
        for canonical_lower, canonical in self.CANONICAL_NAMES.items():
            similarity = SequenceMatcher(None, name_lower, canonical_lower).ratio()
            if similarity >= 0.85:
                return canonical

        return None

    def _proper_case(self, name: str) -> str:
        """Convert ALL CAPS name to Proper Case."""
        words = name.split()
        result = []

        for word in words:
            if word.isupper():
                # Handle special cases
                if word in ['II', 'III', 'IV', 'JR', 'SR']:
                    result.append(word)
                elif len(word) <= 2:
                    result.append(word)  # Keep initials uppercase
                else:
                    result.append(word.capitalize())
            else:
                result.append(word)

        return ' '.join(result)

    def is_duplicate(self, name1: str, name2: str, threshold: float = 0.85) -> bool:
        """
        Check if two names are likely the same person.

        Args:
            name1: First name
            name2: Second name
            threshold: Similarity threshold (0-1)

        Returns:
            True if names are likely duplicates
        """
        # Clean both names
        clean1 = self.clean_name(name1)
        clean2 = self.clean_name(name2)

        if not clean1 or not clean2:
            return False

        # Normalize for comparison
        norm1 = clean1.lower().strip()
        norm2 = clean2.lower().strip()

        # Exact match
        if norm1 == norm2:
            return True

        # Fuzzy match
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        return similarity >= threshold

    def find_best_match(self, name: str, existing_names: List[str],
                       threshold: float = 0.85) -> Optional[Tuple[str, float]]:
        """
        Find the best matching existing name for a new name.

        Args:
            name: New name to match
            existing_names: List of existing names
            threshold: Minimum similarity threshold

        Returns:
            Tuple of (best_match, similarity) or None
        """
        clean_name = self.clean_name(name)
        if not clean_name:
            return None

        norm_name = clean_name.lower()
        best_match = None
        best_similarity = 0.0

        for existing in existing_names:
            clean_existing = self.clean_name(existing)
            if not clean_existing:
                continue

            norm_existing = clean_existing.lower()

            # Check for exact match first
            if norm_name == norm_existing:
                return (existing, 1.0)

            # Fuzzy match
            similarity = SequenceMatcher(None, norm_name, norm_existing).ratio()
            if similarity > best_similarity and similarity >= threshold:
                best_similarity = similarity
                best_match = existing

        if best_match:
            return (best_match, best_similarity)
        return None


# Singleton instance for easy import
name_cleaner = NameCleaner()


if __name__ == "__main__":
    # Test the name cleaner
    cleaner = NameCleaner()

    test_names = [
        "JEFFREY EPSTEIN",
        "Jeffrey Epstein's",
        "Jeffrey Epstein\nBALD",
        "ofJeffrey Epstein",
        "no Jeffrey Epstein",
        "FFFREY EPSTEIN",
        "AFFREY EPSTEIN",
        "jeffrey epstein",
        "Jeffrey EpsteinUeevacation@gmail.com",
        "GHISLAINE MAXWELL JEFFREY EPSTEIN",
        "11 Epstein",
        "Epstein.",
        "The Jeffrey Epstein",
        "EPSTEIN JEFFREY",
        "Jeffrey Epstein VI Founds",
    ]

    print("Name Cleaning Test Results:")
    print("-" * 60)
    for name in test_names:
        cleaned = cleaner.clean_name(name)
        print(f"'{name}'")
        print(f"  -> '{cleaned}'")
        print()
