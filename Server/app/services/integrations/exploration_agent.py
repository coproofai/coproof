import os
import requests
import logging
from config import Config
from app.exceptions import AgentTimeoutError, CoProofError

logger = logging.getLogger(__name__)

class ExplorationAgentClient:
    """
    Client for the External AI Agent Service (Black Box).
    """
    
    BASE_URL = os.environ.get('AGENT_API_URL', 'http://localhost:8001')

    @staticmethod
    def trigger_proof_search(node_context: dict, strategy: str, hint: str = None):
        """
        Asks the agent to solve a theorem.
        """
        payload = {
            "context": node_context, # content of the node, dependencies
            "strategy": strategy,
            "hint": hint
        }
        
        try:
            # In a real scenario, this might be a long-polling request or 
            # the agent callbacks. For now, we assume a sync start or fast response.
            resp = requests.post(f"{ExplorationAgentClient.BASE_URL}/v1/solve", json=payload, timeout=5)
            resp.raise_for_status()
            return resp.json() # Returns job_id or immediate step
            
        except requests.exceptions.Timeout:
            raise AgentTimeoutError("Agent service did not respond in time.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Agent connection failed: {e}")
            raise CoProofError(f"Agent Service Error: {str(e)}", code=502)

    @staticmethod
    def upsert_knowledge_node(node_data: dict):
        """
        RAG Sync: Sends a node to the Agent's Vector DB.
        """
        try:
            resp = requests.put(f"{ExplorationAgentClient.BASE_URL}/v1/knowledge", json=node_data, timeout=3)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"RAG Sync failed: {e}")
            return False