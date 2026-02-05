"""
Named Entity Recognition (NER) using spaCy
"""
from typing import Dict, List, Set
from loguru import logger
import spacy
from config import SPACY_MODEL, MIN_NER_CONFIDENCE, ROLE_KEYWORDS

class NERProcessor:
    """Process text for named entity recognition"""

    def __init__(self):
        try:
            logger.info(f"Loading spaCy model: {SPACY_MODEL}")
            self.nlp = spacy.load(SPACY_MODEL)
            logger.info("spaCy model loaded successfully")
        except OSError:
            logger.error(f"spaCy model '{SPACY_MODEL}' not found. Run: python -m spacy download {SPACY_MODEL}")
            raise

    def process(self, text: str, max_length: int = 1000000) -> Dict:
        """
        Process text and extract named entities

        Args:
            text: Input text to process
            max_length: Maximum text length (spaCy has limits)

        Returns:
            Dictionary with extracted entities
        """
        if not text:
            return self._empty_result()

        # Truncate if too long
        if len(text) > max_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating to {max_length}")
            text = text[:max_length]

        entities = {
            'people': set(),
            'organizations': set(),
            'locations': set(),
            'dates': set(),
            'money': set(),
            'gpe': set(),  # Geo-political entities (countries, cities)
            'law': set(),  # Laws, statutes
            'events': set(),
            'person_roles': {},  # Person -> role mapping
        }

        try:
            doc = self.nlp(text)

            for ent in doc.ents:
                confidence = self._calculate_confidence(ent)

                if confidence < MIN_NER_CONFIDENCE:
                    continue

                entity_text = ent.text.strip()

                if ent.label_ == "PERSON":
                    entities['people'].add(entity_text)
                    # Try to detect role
                    role = self._detect_person_role(entity_text, text)
                    if role:
                        entities['person_roles'][entity_text] = role

                elif ent.label_ == "ORG":
                    entities['organizations'].add(entity_text)

                elif ent.label_ in ["LOC", "FAC"]:  # Location or Facility
                    entities['locations'].add(entity_text)

                elif ent.label_ == "GPE":  # Geo-political entity
                    entities['gpe'].add(entity_text)

                elif ent.label_ == "DATE":
                    entities['dates'].add(entity_text)

                elif ent.label_ == "MONEY":
                    entities['money'].add(entity_text)

                elif ent.label_ == "LAW":
                    entities['law'].add(entity_text)

                elif ent.label_ == "EVENT":
                    entities['events'].add(entity_text)

        except Exception as e:
            logger.error(f"NER processing failed: {e}")

        # Convert sets to sorted lists
        result = {
            'people': sorted(list(entities['people'])),
            'organizations': sorted(list(entities['organizations'])),
            'locations': sorted(list(entities['locations'])),
            'dates': sorted(list(entities['dates'])),
            'money': sorted(list(entities['money'])),
            'gpe': sorted(list(entities['gpe'])),
            'law': sorted(list(entities['law'])),
            'events': sorted(list(entities['events'])),
            'person_roles': entities['person_roles'],
        }

        logger.info(f"NER extracted: {len(result['people'])} people, "
                   f"{len(result['organizations'])} orgs, "
                   f"{len(result['locations'])} locations")

        return result

    def _calculate_confidence(self, entity) -> float:
        """
        Calculate confidence score for an entity

        Args:
            entity: spaCy entity

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # For now, use a simple heuristic based on entity length and capitalization
        text = entity.text
        confidence = 0.8  # Base confidence

        # Increase confidence for properly capitalized names
        if text[0].isupper():
            confidence += 0.1

        # Decrease confidence for very short entities
        if len(text) < 3:
            confidence -= 0.2

        # Decrease confidence for all caps (might be acronym or noise)
        if text.isupper() and len(text) > 3:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def _detect_person_role(self, person_name: str, text: str) -> str:
        """
        Detect the role of a person based on context

        Args:
            person_name: Name of the person
            text: Full document text

        Returns:
            Detected role or None
        """
        text_lower = text.lower()
        person_lower = person_name.lower()

        # Find context around person's name (±100 characters)
        person_index = text_lower.find(person_lower)
        if person_index == -1:
            return None

        start = max(0, person_index - 100)
        end = min(len(text_lower), person_index + len(person_lower) + 100)
        context = text_lower[start:end]

        # Check for role keywords in context
        for role, keywords in ROLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in context:
                    return role

        return None

    def extract_relationships(self, text: str) -> List[Dict]:
        """
        Extract relationships between entities using dependency parsing

        Args:
            text: Input text

        Returns:
            List of relationship dictionaries
        """
        if not text or len(text) > 100000:
            # Limit for performance
            text = text[:100000] if text else ""

        relationships = []

        try:
            doc = self.nlp(text)

            # Look for patterns like "X worked for Y", "X is Y's lawyer", etc.
            for sent in doc.sents:
                # Pattern: PERSON + VERB + PERSON/ORG
                for token in sent:
                    if token.pos_ == "VERB":
                        # Find subjects and objects
                        subjects = [child for child in token.children if child.dep_ in ["nsubj", "nsubjpass"]]
                        objects = [child for child in token.children if child.dep_ in ["dobj", "pobj", "attr"]]

                        for subj in subjects:
                            for obj in objects:
                                if subj.ent_type_ == "PERSON" and obj.ent_type_ in ["PERSON", "ORG"]:
                                    relationships.append({
                                        'person1': subj.text,
                                        'relationship_type': token.lemma_,
                                        'person2_or_org': obj.text,
                                        'entity2_type': obj.ent_type_,
                                        'confidence': 0.7,
                                    })

        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")

        logger.info(f"Extracted {len(relationships)} relationships")
        return relationships

    def extract_events(self, text: str) -> List[Dict]:
        """
        Extract events with dates and participants

        Args:
            text: Input text

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            doc = self.nlp(text)

            # Look for sentences with dates and verbs
            for sent in doc.sents:
                date_entities = [ent for ent in sent.ents if ent.label_ == "DATE"]
                person_entities = [ent for ent in sent.ents if ent.label_ == "PERSON"]
                location_entities = [ent for ent in sent.ents if ent.label_ in ["LOC", "GPE", "FAC"]]

                if date_entities:
                    # Find main verb
                    verbs = [token for token in sent if token.pos_ == "VERB"]

                    if verbs:
                        event = {
                            'event_date': date_entities[0].text,
                            'event_type': verbs[0].lemma_,
                            'description': sent.text,
                            'participants': [p.text for p in person_entities],
                            'locations': [l.text for l in location_entities],
                            'confidence': 0.6,
                        }
                        events.append(event)

        except Exception as e:
            logger.error(f"Event extraction failed: {e}")

        logger.info(f"Extracted {len(events)} potential events")
        return events

    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'people': [],
            'organizations': [],
            'locations': [],
            'dates': [],
            'money': [],
            'gpe': [],
            'law': [],
            'events': [],
            'person_roles': {},
        }


if __name__ == "__main__":
    # Test NER processing
    processor = NERProcessor()

    test_text = """
    On July 15, 2019, Jeffrey Epstein appeared before Judge Richard M. Berman
    at the United States District Court for the Southern District of New York.
    Assistant United States Attorney Maurene Comey argued for detention,
    citing Epstein's wealth of over $500 million and properties in Manhattan
    and Palm Beach, Florida. Defense attorney Martin Weinberg requested bail.
    """

    print("Testing NER Processor...\n")

    # Test entity extraction
    entities = processor.process(test_text)
    print("Extracted Entities:")
    for entity_type, values in entities.items():
        if values:
            print(f"  {entity_type}: {values}")

    # Test relationship extraction
    print("\nExtracted Relationships:")
    relationships = processor.extract_relationships(test_text)
    for rel in relationships[:5]:  # Show first 5
        print(f"  {rel}")

    # Test event extraction
    print("\nExtracted Events:")
    events = processor.extract_events(test_text)
    for event in events[:5]:  # Show first 5
        print(f"  {event}")
