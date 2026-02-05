"""
Entity deduplication service using fuzzy matching
"""
from typing import List, Dict, Optional
from loguru import logger
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from models import Person, Organization, Location

class DeduplicationService:
    """Service for deduplicating entities"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.similarity_threshold = 0.85  # 85% similarity

    def find_duplicate_people(self, name: str, min_similarity: float = None) -> List[Person]:
        """
        Find potential duplicate people by name similarity

        Args:
            name: Name to search for
            min_similarity: Minimum similarity threshold (default: 0.85)

        Returns:
            List of potential duplicate Person objects
        """
        if min_similarity is None:
            min_similarity = self.similarity_threshold

        duplicates = []
        all_people = self.db.query(Person).all()

        for person in all_people:
            similarity = self._calculate_similarity(name, person.full_name)
            if similarity >= min_similarity:
                duplicates.append((person, similarity))

        # Sort by similarity descending
        duplicates.sort(key=lambda x: x[1], reverse=True)

        return [dup[0] for dup in duplicates]

    def find_duplicate_organizations(self, org_name: str, min_similarity: float = None) -> List[Organization]:
        """Find potential duplicate organizations"""
        if min_similarity is None:
            min_similarity = self.similarity_threshold

        duplicates = []
        all_orgs = self.db.query(Organization).all()

        for org in all_orgs:
            similarity = self._calculate_similarity(org_name, org.organization_name)
            if similarity >= min_similarity:
                duplicates.append((org, similarity))

        duplicates.sort(key=lambda x: x[1], reverse=True)
        return [dup[0] for dup in duplicates]

    def merge_people(self, primary_id: int, duplicate_ids: List[int]) -> bool:
        """
        Merge duplicate people into a primary person

        Args:
            primary_id: ID of person to keep
            duplicate_ids: List of IDs to merge into primary

        Returns:
            Success status
        """
        try:
            primary = self.db.query(Person).get(primary_id)
            if not primary:
                logger.error(f"Primary person {primary_id} not found")
                return False

            for dup_id in duplicate_ids:
                duplicate = self.db.query(Person).get(dup_id)
                if not duplicate:
                    logger.warning(f"Duplicate person {dup_id} not found, skipping")
                    continue

                # Merge name variations
                if duplicate.name_variations:
                    primary.name_variations = list(set(
                        (primary.name_variations or []) + duplicate.name_variations
                    ))

                # Merge roles
                if duplicate.roles:
                    primary.roles = list(set(
                        (primary.roles or []) + duplicate.roles
                    ))

                # Merge contact info
                if duplicate.email_addresses:
                    primary.email_addresses = list(set(
                        (primary.email_addresses or []) + duplicate.email_addresses
                    ))

                if duplicate.phone_numbers:
                    primary.phone_numbers = list(set(
                        (primary.phone_numbers or []) + duplicate.phone_numbers
                    ))

                # Update all relationships to point to primary
                from models import Relationship, EventParticipant, MediaPerson

                self.db.query(Relationship).filter_by(person1_id=dup_id).update({'person1_id': primary_id})
                self.db.query(Relationship).filter_by(person2_id=dup_id).update({'person2_id': primary_id})
                self.db.query(EventParticipant).filter_by(person_id=dup_id).update({'person_id': primary_id})
                self.db.query(MediaPerson).filter_by(person_id=dup_id).update({'person_id': primary_id})

                # Delete duplicate
                self.db.delete(duplicate)

            self.db.commit()
            logger.info(f"Merged {len(duplicate_ids)} duplicates into person {primary_id}")
            return True

        except Exception as e:
            logger.error(f"Error merging people: {e}")
            self.db.rollback()
            return False

    def normalize_name(self, name: str) -> str:
        """
        Normalize name for comparison

        Args:
            name: Input name

        Returns:
            Normalized name
        """
        # Remove extra whitespace
        name = ' '.join(name.split())

        # Remove common suffixes
        suffixes = [' Jr.', ' Sr.', ' III', ' II', ' IV', ' Esq.']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]

        # Remove titles
        titles = ['Dr. ', 'Mr. ', 'Ms. ', 'Mrs. ', 'Prof. ']
        for title in titles:
            if name.startswith(title):
                name = name[len(title):]

        return name.strip()

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize both strings
        s1 = self.normalize_name(str1.lower())
        s2 = self.normalize_name(str2.lower())

        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, s1, s2).ratio()

        # Bonus for exact match after normalization
        if s1 == s2:
            similarity = 1.0

        return similarity

    def suggest_merges(self, entity_type: str = 'person') -> List[Dict]:
        """
        Suggest potential merges based on similarity

        Args:
            entity_type: 'person' or 'organization'

        Returns:
            List of merge suggestions
        """
        suggestions = []

        if entity_type == 'person':
            all_people = self.db.query(Person).all()

            # Compare all pairs
            for i, person1 in enumerate(all_people):
                for person2 in all_people[i+1:]:
                    similarity = self._calculate_similarity(
                        person1.full_name,
                        person2.full_name
                    )

                    if similarity >= self.similarity_threshold:
                        suggestions.append({
                            'primary_id': person1.person_id,
                            'primary_name': person1.full_name,
                            'duplicate_id': person2.person_id,
                            'duplicate_name': person2.full_name,
                            'similarity': similarity,
                            'entity_type': 'person'
                        })

        elif entity_type == 'organization':
            all_orgs = self.db.query(Organization).all()

            for i, org1 in enumerate(all_orgs):
                for org2 in all_orgs[i+1:]:
                    similarity = self._calculate_similarity(
                        org1.organization_name,
                        org2.organization_name
                    )

                    if similarity >= self.similarity_threshold:
                        suggestions.append({
                            'primary_id': org1.organization_id,
                            'primary_name': org1.organization_name,
                            'duplicate_id': org2.organization_id,
                            'duplicate_name': org2.organization_name,
                            'similarity': similarity,
                            'entity_type': 'organization'
                        })

        # Sort by similarity descending
        suggestions.sort(key=lambda x: x['similarity'], reverse=True)

        logger.info(f"Found {len(suggestions)} potential {entity_type} merges")
        return suggestions

    def auto_merge_high_confidence(self, min_similarity: float = 0.95) -> int:
        """
        Automatically merge entities with very high similarity

        Args:
            min_similarity: Minimum similarity for auto-merge (default: 0.95)

        Returns:
            Number of merges performed
        """
        merge_count = 0

        # Get suggestions
        people_suggestions = self.suggest_merges('person')

        # Auto-merge high confidence matches
        for suggestion in people_suggestions:
            if suggestion['similarity'] >= min_similarity:
                success = self.merge_people(
                    suggestion['primary_id'],
                    [suggestion['duplicate_id']]
                )
                if success:
                    merge_count += 1

        logger.info(f"Auto-merged {merge_count} entities")
        return merge_count


if __name__ == "__main__":
    # Test deduplication
    from config import SessionLocal

    db = SessionLocal()
    dedup_service = DeduplicationService(db)

    # Test name normalization
    test_names = [
        "Dr. John Smith Jr.",
        "John Smith",
        "Mr. John  Smith",
    ]

    print("Name Normalization Test:")
    for name in test_names:
        normalized = dedup_service.normalize_name(name)
        print(f"  '{name}' -> '{normalized}'")

    # Test similarity
    print("\nSimilarity Test:")
    pairs = [
        ("Jeffrey Epstein", "Jeffrey E. Epstein"),
        ("Maurene Comey", "Maureen Comey"),
        ("John Doe", "Jane Doe"),
    ]

    for name1, name2 in pairs:
        similarity = dedup_service._calculate_similarity(name1, name2)
        print(f"  '{name1}' vs '{name2}': {similarity:.2f}")

    db.close()
