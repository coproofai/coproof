# app/services/verification_service.py

import networkx as nx
import logging
from app.models.graph_index import GraphNode
from app.models.proposed_node import ProposedNode
from app.services.graph_engine.lean_parser import LeanParser
from app.exceptions import CoProofError

logger = logging.getLogger(__name__)

class VerificationService:

    @staticmethod
    def validate_topology(project_id, target_statement_id, parent_id, dependency_ids):
        """
        Pre-flight check for Immutability and Orphans.
        Ensures:
        1. Target ID does not already exist (Immutability).
        2. Parent ID exists (if not root).
        3. All Dependency IDs exist.
        """
        # 1. Immutability Check
        if GraphNode.query.filter_by(project_id=project_id, statement_id=target_statement_id).first():
            raise CoProofError(f"Statement {target_statement_id} already exists. Cannot overwrite canonical nodes.", code=409)

        # 2. Parent Existence
        if parent_id:
            if not GraphNode.query.filter_by(project_id=project_id, statement_id=parent_id).first():
                raise CoProofError(f"Parent node {parent_id} does not exist in canonical graph.", code=400)

        # 3. Dependency Existence
        if dependency_ids:
            # Check for missing dependencies in batch
            existing_count = GraphNode.query.filter(
                GraphNode.project_id == project_id,
                GraphNode.statement_id.in_(dependency_ids)
            ).count()
            
            if existing_count != len(set(dependency_ids)):
                # Identify which one is missing for better error message
                existing_ids = {str(n.statement_id) for n in GraphNode.query.filter(
                    GraphNode.project_id == project_id,
                    GraphNode.statement_id.in_(dependency_ids)
                ).all()}
                missing = set(dependency_ids) - existing_ids
                raise CoProofError(f"Missing dependencies in canonical graph: {missing}", code=400)


    @staticmethod
    def validate_and_order(project_id, target_proposal: ProposedNode):
        """
        Orchestrator for Structural Verification.
        1. Builds Ephemeral DAG.
        2. Checks for Cycles.
        3. Checks Parent Resolution status.
        4. Returns Topological Order.
        """
        # 1. Build DAG
        try:
            dag = VerificationService._build_ephemeral_dag(project_id, target_proposal)
        except Exception as e:
            logger.error(f"DAG Construction failed: {e}")
            raise CoProofError(f"Structural Error: {e}", code=400)

        # 2. Cycle Detection
        try:
            cycle = nx.find_cycle(dag, orientation='original')
            cycle_path = " -> ".join([f"{u}" for u, v in cycle])
            raise CoProofError(f"Cycle detected: {cycle_path}", code=400)
        except nx.NetworkXNoCycle:
            pass

        # 3. Parent Resolution Check
        # Warning if we are adding a child to an already resolved parent
        if target_proposal.parent_statement_id:
            parent = GraphNode.query.filter_by(
                project_id=project_id, 
                statement_id=target_proposal.parent_statement_id
            ).first()
            if parent and parent.is_resolved:
                logger.info(f"Note: Parent node {parent.title} is already resolved.")
                # We do not block this, as it might be an alternative proof, 
                # but we log it for the UI/Author.

        # 4. Topological Sort
        try:
            # Return list of file paths
            ordered_ids = list(nx.topological_sort(dag))
            paths = []
            for nid in ordered_ids:
                data = dag.nodes[nid]['data']
                # Distinguish between Canonical (GraphNode) and Proposal (ProposedNode)
                if isinstance(data, GraphNode):
                    paths.append(data.lean_relative_path)
                elif isinstance(data, ProposedNode):
                    paths.append(data.lean_file_path)
            return paths
        except nx.NetworkXUnfeasible:
            raise CoProofError("Critical: Topological sort failed despite no cycle detected.", code=500)



    
    @staticmethod
    def check_immutability(project_id, statement_id):
        """
        Ensures a statement_id does not already exist in the Canonical Graph.
        """
        exists = GraphNode.query.filter_by(
            project_id=project_id, 
            statement_id=statement_id
        ).first()
        
        if exists:
            raise CoProofError(
                f"Immutable Violation: Statement {statement_id} already exists in canonical graph. "
                "You cannot modify verified nodes. Create a new statement instead.",
                code=409
            )

    @staticmethod
    def parse_proposal_content(content: str):
        """
        Extracts metadata using the Parser.
        """
        # Note: We pass a dummy path because we only need logical metadata here
        results = LeanParser.parse_file_content(content, "dummy.lean")
        if results['parse_error']:
            raise CoProofError("Failed to parse generated scaffold content.")
            
        return results

    @staticmethod
    def _build_ephemeral_dag(project_id, target_proposal: ProposedNode):
        """
        Internal builder using strict UUIDs.
        """
        dag = nx.DiGraph()
        
        # A. Load Canonical Graph
        canonical_nodes = GraphNode.query.filter_by(project_id=project_id).all()
        canonical_map = {str(n.statement_id): n for n in canonical_nodes}

        for node in canonical_nodes:
            nid = str(node.statement_id)
            dag.add_node(nid, data=node)
            
            # Parent Edge
            if node.parent_statement_id:
                pid = str(node.parent_statement_id)
                if pid in canonical_map:
                    dag.add_edge(pid, nid)

            # Prerequisite Edges
            for prereq in node.prerequisites:
                dag.add_edge(str(prereq.statement_id), nid)

        # B. Add Proposal
        # We use a temporary ID if the proposal isn't fully persisted with a statement_id, 
        # but in this flow, we assume we generated one.
        # Ideally, we pass the new statement_id explicitly or store it on the model.
        # For now, we assume the caller ensures dependencies are UUIDs.
        
        # We need the statement_id associated with this proposal. 
        # Since it's not in the DB model `statement_id` field yet (it's in the file),
        # we assume it's passed or stored in `proposed_parent_title` field temporarily if reused,
        # or we generate a placeholder key.
        # Better approach: The Proposal DB object should imply the node.
        prop_id = "PROPOSAL_TARGET" 
        dag.add_node(prop_id, data=target_proposal)

        # Parent Edge
        if target_proposal.parent_statement_id:
            pid = str(target_proposal.parent_statement_id)
            if pid not in canonical_map:
                raise CoProofError(f"Invalid Parent ID: {pid}")
            dag.add_edge(pid, prop_id)

        # Dependency Edges (UUIDs from JSONB)
        if target_proposal.proposed_dependencies:
            for dep_id in target_proposal.proposed_dependencies:
                if dep_id not in canonical_map:
                    raise CoProofError(f"Invalid Dependency ID: {dep_id}")
                dag.add_edge(dep_id, prop_id)

        return dag