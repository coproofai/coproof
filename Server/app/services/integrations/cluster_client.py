from app.services.integrations.computation_client import ComputationClient


class ClusterClient(ComputationClient):
    """Compatibility alias for legacy callers still importing ClusterClient."""
