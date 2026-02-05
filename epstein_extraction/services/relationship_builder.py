"""
Relationship inference service
Builds relationships between entities based on co-occurrence and context
"""
from typing import List, Dict, Tuple
from collections import defaultdict
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import Person, Event, EventParticipant, Relationship, Document, Communication

class RelationshipBuilder:
    """Service for inferring relationships between entities"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.min_co_occurrence = 3  # Minimum times people appear together

    def build_relationships_from_events(self) -> int:
        """
        Build relationships based on event co-participation

        Returns:
            Number of relationships created
        """
        relationship_count = 0

        # Get all events with participants
        events = self.db.query(Event).all()

        for event in events:
            participants = self.db.query(EventParticipant).filter_by(
                event_id=event.event_id
            ).all()

            person_ids = [p.person_id for p in participants if p.person_id]

            # Create relationships between all pairs of participants
            for i, person1_id in enumerate(person_ids):
                for person2_id in person_ids[i+1:]:
                    relationship_type = self._infer_relationship_type(
                        event.event_type,
                        participants
                    )

                    success = self._create_or_update_relationship(
                        person1_id,
                        person2_id,
                        relationship_type,
                        source_doc_id=event.source_document_id
                    )

                    if success:
                        relationship_count += 1

        logger.info(f"Built {relationship_count} relationships from events")
        return relationship_count

    def build_relationships_from_communications(self) -> int:
        """
        Build relationships from email and communication patterns

        Returns:
            Number of relationships created
        """
        relationship_count = 0

        # Get all communications
        communications = self.db.query(Communication).all()

        for comm in communications:
            if not comm.sender_person_id:
                continue

            # Get recipients
            recipients = self.db.query(CommunicationRecipient).filter_by(
                communication_id=comm.communication_id
            ).all()

            for recipient in recipients:
                if recipient.person_id:
                    success = self._create_or_update_relationship(
                        comm.sender_person_id,
                        recipient.person_id,
                        'correspondence',
                        source_doc_id=comm.source_document_id
                    )

                    if success:
                        relationship_count += 1

        logger.info(f"Built {relationship_count} relationships from communications")
        return relationship_count

    def build_relationships_from_co_occurrence(self) -> int:
        """
        Build relationships based on co-occurrence in documents

        Returns:
            Number of relationships created
        """
        relationship_count = 0

        # Get all documents
        documents = self.db.query(Document).all()

        for doc in documents:
            # Get all people mentioned in this document
            mentions = self.db.query(DocumentMention).filter_by(
                document_id=doc.document_id
            ).filter(DocumentMention.person_id.isnot(None)).all()

            person_ids = [m.person_id for m in mentions]

            if len(person_ids) < 2:
                continue

            # Track co-occurrence
            for i, person1_id in enumerate(person_ids):
                for person2_id in person_ids[i+1:]:
                    # Count how many times these two appear together
                    co_occurrence_count = self._count_co_occurrences(
                        person1_id,
                        person2_id
                    )

                    if co_occurrence_count >= self.min_co_occurrence:
                        success = self._create_or_update_relationship(
                            person1_id,
                            person2_id,
                            'associate',  # Generic relationship type
                            source_doc_id=doc.document_id
                        )

                        if success:
                            relationship_count += 1

        logger.info(f"Built {relationship_count} relationships from co-occurrence")
        return relationship_count

    def _infer_relationship_type(self, event_type: str, participants: List) -> str:
        """
        Infer relationship type based on event type and participant roles

        Args:
            event_type: Type of event
            participants: List of event participants

        Returns:
            Inferred relationship type
        """
        # Map event types to relationship types
        event_to_relationship = {
            'meeting': 'professional_associate',
            'flight': 'travel_companion',
            'court_hearing': 'legal_connection',
            'transaction': 'financial_connection',
            'communication': 'correspondence',
            'employment': 'employer_employee',
        }

        return event_to_relationship.get(event_type, 'associate')

    def _create_or_update_relationship(
        self,
        person1_id: int,
        person2_id: int,
        relationship_type: str,
        source_doc_id: int = None
    ) -> bool:
        """
        Create or update a relationship

        Args:
            person1_id: First person ID
            person2_id: Second person ID
            relationship_type: Type of relationship
            source_doc_id: Source document ID

        Returns:
            Success status
        """
        try:
            # Check if relationship already exists
            existing = self.db.query(Relationship).filter(
                and_(
                    Relationship.person1_id == person1_id,
                    Relationship.person2_id == person2_id,
                    Relationship.relationship_type == relationship_type
                )
            ).first()

            if existing:
                # Relationship already exists, update confidence
                existing.confidence_level = 'high'
                self.db.commit()
                return False

            # Create new relationship
            relationship = Relationship(
                person1_id=person1_id,
                person2_id=person2_id,
                relationship_type=relationship_type,
                source_document_id=source_doc_id,
                confidence_level='medium'
            )

            self.db.add(relationship)
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            self.db.rollback()
            return False

    def _count_co_occurrences(self, person1_id: int, person2_id: int) -> int:
        """
        Count how many documents both people appear in

        Args:
            person1_id: First person ID
            person2_id: Second person ID

        Returns:
            Co-occurrence count
        """
        from models import DocumentMention

        # Get all documents person1 appears in
        docs1 = set(
            dm.document_id for dm in
            self.db.query(DocumentMention).filter_by(person_id=person1_id).all()
        )

        # Get all documents person2 appears in
        docs2 = set(
            dm.document_id for dm in
            self.db.query(DocumentMention).filter_by(person_id=person2_id).all()
        )

        # Count intersection
        return len(docs1.intersection(docs2))

    def build_relationship_graph(self) -> Dict:
        """
        Build a graph representation of all relationships

        Returns:
            Dictionary representing the relationship graph
        """
        graph = defaultdict(list)

        relationships = self.db.query(Relationship).all()

        for rel in relationships:
            person1 = self.db.query(Person).get(rel.person1_id)
            person2 = self.db.query(Person).get(rel.person2_id)

            if person1 and person2:
                graph[person1.full_name].append({
                    'connected_to': person2.full_name,
                    'relationship_type': rel.relationship_type,
                    'confidence': rel.confidence_level
                })

                # Add reverse connection
                graph[person2.full_name].append({
                    'connected_to': person1.full_name,
                    'relationship_type': rel.relationship_type,
                    'confidence': rel.confidence_level
                })

        return dict(graph)

    def find_connection_path(
        self,
        person1_name: str,
        person2_name: str,
        max_depth: int = 3
    ) -> List[str]:
        """
        Find connection path between two people

        Args:
            person1_name: First person's name
            person2_name: Second person's name
            max_depth: Maximum degrees of separation

        Returns:
            List of names representing connection path
        """
        graph = self.build_relationship_graph()

        # BFS to find shortest path
        queue = [(person1_name, [person1_name])]
        visited = set([person1_name])

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            if current == person2_name:
                return path

            if current in graph:
                for connection in graph[current]:
                    next_person = connection['connected_to']
                    if next_person not in visited:
                        visited.add(next_person)
                        queue.append((next_person, path + [next_person]))

        return []  # No path found

    def get_relationship_statistics(self) -> Dict:
        """
        Get statistics about relationships

        Returns:
            Dictionary with relationship statistics
        """
        total_relationships = self.db.query(Relationship).count()

        # Count by type
        relationship_types = defaultdict(int)
        relationships = self.db.query(Relationship).all()

        for rel in relationships:
            relationship_types[rel.relationship_type] += 1

        # Find most connected people
        person_connections = defaultdict(int)
        for rel in relationships:
            person_connections[rel.person1_id] += 1
            person_connections[rel.person2_id] += 1

        # Get top 10 most connected
        top_connected = sorted(
            person_connections.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        top_connected_people = []
        for person_id, count in top_connected:
            person = self.db.query(Person).get(person_id)
            if person:
                top_connected_people.append({
                    'name': person.full_name,
                    'connection_count': count
                })

        return {
            'total_relationships': total_relationships,
            'relationship_types': dict(relationship_types),
            'top_connected_people': top_connected_people
        }


if __name__ == "__main__":
    # Test relationship builder
    from config import SessionLocal

    db = SessionLocal()
    builder = RelationshipBuilder(db)

    print("Building Relationships...")

    # Build relationships from different sources
    event_rels = builder.build_relationships_from_events()
    print(f"Created {event_rels} relationships from events")

    comm_rels = builder.build_relationships_from_communications()
    print(f"Created {comm_rels} relationships from communications")

    # Get statistics
    stats = builder.get_relationship_statistics()
    print(f"\nRelationship Statistics:")
    print(f"Total Relationships: {stats['total_relationships']}")
    print(f"Relationship Types: {stats['relationship_types']}")
    print(f"\nTop Connected People:")
    for person in stats['top_connected_people']:
        print(f"  {person['name']}: {person['connection_count']} connections")

    db.close()
