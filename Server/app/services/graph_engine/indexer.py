import logging
from app.extensions import db
from app.models.graph_index import GraphNode, dependencies
from app.services.graph_engine.lean_parser import LeanParser

logger = logging.getLogger(__name__)

class GraphIndexer:
    """
    Syncs parsed file content into the PostgreSQL Graph Index.
    """

    @staticmethod
    def index_file_content(project_id, file_path, commit_hash, content):
        """
        Parses content and updates/creates nodes in the DB.
        """
        # 1. Parse content
        parsed_nodes = LeanParser.parse_file_content(content)
        
        indexed_nodes = []
        
        # 2. Upsert Nodes
        for node_data in parsed_nodes:
            # Check if node exists by (project_id, title)
            node = GraphNode.query.filter_by(
                project_id=project_id, 
                title=node_data['title']
            ).first()
            
            if not node:
                node = GraphNode(
                    project_id=project_id,
                    title=node_data['title']
                )
                db.session.add(node)
            
            # Update Metadata
            node.node_type = node_data['node_type']
            node.file_path = file_path
            node.start_line = node_data['line_number']
            # We don't calculate end_line strictly yet without a complex parser
            node.commit_hash = commit_hash
            
            # Reset RAG sync status because content changed
            node.rag_synced_at = None 
            
            indexed_nodes.append((node, node_data['dependencies']))
        
        # Flush to get IDs for new nodes
        db.session.flush()
        
        # 3. Resolve Dependencies (Edges)
        # This is complex: Deps are strings ("lemma_1"), we need UUIDs.
        # We search for them in the SAME project.
        for node, dep_names in indexed_nodes:
            # Clear old dependencies? Or append? 
            # For a strict sync, we often want to match exactly what is in the file.
            # Strategy: Clear existing prerequisites and re-add found ones.
            # Note: This is expensive. Optimization: Compare sets.
            
            current_deps = set(dep_names)
            
            if current_deps:
                # Find target nodes
                targets = GraphNode.query.filter(
                    GraphNode.project_id == project_id,
                    GraphNode.title.in_(current_deps)
                ).all()
                
                # Update relation
                node.prerequisites = targets

        try:
            db.session.commit()
            logger.info(f"Indexed {len(indexed_nodes)} nodes for {file_path}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Indexing failed: {e}")
            raise e