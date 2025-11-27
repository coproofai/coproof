import logging
from app.extensions import celery, db
from app.models.graph_index import GraphNode
from app.services.integrations import ExplorationAgentClient
from app.schemas import GraphNodeSchema

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def sync_node_to_agent(self, node_id):
    """
    ETL: Postgres -> Agent Vector DB.
    Triggered after a Node is indexed/saved.
    """
    node = GraphNode.query.get(node_id)
    if not node:
        logger.warning(f"Node {node_id} not found for RAG sync")
        return

    try:
        # 1. Format Data for the Agent
        # We assume the agent needs the title, type, and the file content (if we had it).
        # Since content is in Git, ideally we passed it in, or we read it here.
        # For efficiency, we assume the 'indexer' passed the content or we send metadata.
        
        node_data = {
            "id": str(node.id),
            "project_id": str(node.project_id),
            "title": node.title,
            "type": node.node_type,
            "file_path": node.file_path,
            "commit_hash": node.commit_hash
            # "content": ... (Needs to be read from file if Agent requires full text)
        }
        
        # 2. Send to Agent
        success = ExplorationAgentClient.upsert_knowledge_node(node_data)
        
        # 3. Update Sync Timestamp in DB
        if success:
            node.rag_synced_at = db.func.now()
            db.session.commit()
            logger.info(f"Node {node.title} synced to RAG")
        else:
            logger.error(f"Failed to sync Node {node.title} to RAG")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"RAG Sync Exception: {e}")