# app/services/graph_engine/indexer.py

import os
import git
import logging
from app.extensions import db
from app.models.project import Project
from app.models.graph_index import GraphNode
from app.services.graph_engine.lean_parser import LeanParser
from app.services.git_engine.repo_pool import RepoPool
from app.services.git_engine.file_service import FileService
from app.exceptions import CoProofError
import networkx as nx

logger = logging.getLogger(__name__)

class GraphIndexer:
    """
    Rebuilds the Canonical Graph (Postgres) from the Git Source of Truth.
    """

    @staticmethod
    def reindex_project(project_id: str):
        """
        Full Index Reconstruction.
        1. Checkout Main.
        2. Scan /statements/*.lean.
        3. Upsert Nodes.
        4. Resolve DAG (Imports).
        5. Resolve Tree (Parent IDs).
        6. Resolve Proofs (Closure Rule).
        """
        project = Project.query.get(project_id)
        if not project:
            raise CoProofError(f"Project {project_id} not found")

        bare_path = RepoPool.get_storage_path(project_id)
        if not os.path.exists(bare_path):
            logger.warning(f"Repo for {project_id} missing during reindex. Attempting to restore via next access.")
            return

        repo = git.Repo(bare_path)
        main_commit = repo.head.commit
        
        # 1. Scan Files (Source of Truth)
        try:
            statements_tree = main_commit.tree / FileService.STATEMENTS_DIR
        except KeyError:
            logger.info(f"No statements directory found. Clearing graph.")
            GraphNode.query.filter_by(project_id=project_id).delete()
            project.main_commit_sha = main_commit.hexsha
            db.session.commit()
            return

        parsed_nodes = []
        valid_statement_ids = set()

        for blob in statements_tree.blobs:
            if not blob.name.endswith('.lean'): continue
                
            content = blob.data_stream.read().decode('utf-8')
            rel_path = f"{FileService.STATEMENTS_DIR}/{blob.name}"
            
            # Use the robust parser
            meta = LeanParser.parse_file_content(content, rel_path)
            
            if meta['parse_error'] or not meta['statement_id']:
                logger.error(f"SKIPPING malformed file: {rel_path}. Missing/Invalid ID.")
                continue
                
            meta['lean_path'] = rel_path
            meta['latex_path'] = rel_path.replace('.lean', '.tex') # Assumption enforced by FileService
            
            parsed_nodes.append(meta)
            valid_statement_ids.add(meta['statement_id'])

        # 2. Upsert Nodes (Atomic Identity)
        # We assume one node per file (1:1 statement_id)
        
        # Cleanup Stale
        GraphNode.query.filter(
            GraphNode.project_id == project_id,
            GraphNode.statement_id.notin_(valid_statement_ids)
        ).delete(synchronize_session=False)
        
        # Upsert Active
        # Optimization: Bulk fetch existing to minimize queries
        existing_nodes = {
            str(n.statement_id): n 
            for n in GraphNode.query.filter_by(project_id=project_id).all()
        }
        
        for meta in parsed_nodes:
            sid = str(meta['statement_id'])
            node = existing_nodes.get(sid)
            
            if not node:
                node = GraphNode(project_id=project_id, statement_id=sid)
                db.session.add(node)
                existing_nodes[sid] = node # Add to map for linking later
            
            # Update Metadata
            node.title = meta['title']
            node.node_type = meta['node_type']
            node.lean_relative_path = meta['lean_path']
            node.latex_relative_path = meta['latex_path']
            # Default resolution status is based on textual 'sorry'. 
            # Will be overridden if children prove it.
            node.is_resolved = not meta['has_sorry']
            node.proven_by_statement_id = None # Reset for recalculation

        db.session.flush() # Ensure IDs are generated

        # 3. Topology & Validation (DAG/Tree)
        # We build a NetworkX graph to detect cycles before committing relations
        dag = nx.DiGraph()
        
        for meta in parsed_nodes:
            sid = str(meta['statement_id'])
            node = existing_nodes[sid]
            
            # A. Tree (Parent)
            pid_raw = meta['parent_statement_id']
            if pid_raw and pid_raw in existing_nodes:
                node.parent_id = existing_nodes[pid_raw].id
            else:
                node.parent_id = None # Root or Orphan (if parent missing)

            # B. DAG (Prerequisites)
            # "Ensure topological order respects actual Lean dependencies"
            prereqs = []
            for dep_uuid in meta['dependencies']:
                if dep_uuid in existing_nodes:
                    target = existing_nodes[dep_uuid]
                    prereqs.append(target)
                    # Add edge to ephemeral graph for cycle check: Dep -> Node
                    dag.add_edge(dep_uuid, sid)
                else:
                    logger.warning(f"Node {sid} has missing dependency {dep_uuid}")
            
            node.prerequisites = prereqs

        # Cycle Check
        try:
            if not nx.is_directed_acyclic_graph(dag):
                cycle = nx.find_cycle(dag)
                logger.error(f"Cycle detected in canonical graph during reindex! {cycle}")
                # We do NOT abort saving the nodes (to preserve data access), 
                # but we log heavily. The project is effectively broken logically.
        except Exception:
            pass 

        db.session.commit() # Save Topology

        # 4. Proof Closure Resolution (Deterministic Rule)
        # "Reject multiple proof closures for the same parent to avoid ambiguity"
        
        # Refresh state
        all_nodes = GraphNode.query.filter_by(project_id=project_id).all()
        nodes_by_id = {n.id: n for n in all_nodes}
        
        for node in all_nodes:
            # If already textually solved (no sorry), it's resolved.
            if node.is_resolved:
                continue
                
            # Find candidate children: Direct children that are 'theorem' or 'lemma'
            # and effectively "close" the parent's gap.
            # In this architecture, we assume ANY valid theorem child is an attempt to prove the parent goal.
            candidates = [
                c for c in node.children 
                if c.node_type in ('theorem', 'lemma')
            ]
            
            # Filter candidates: Must NOT contain 'sorry' themselves
            # (Note: This is textual check. Ideally we use 'is_resolved' but that creates recursive logic.
            # Simple rule: A child proves a parent only if the child ITSELF is resolved.)
            valid_candidates = []
            for cand in candidates:
                # If candidate textually has sorry, it can't prove parent.
                # If candidate is proven by ITS child, it IS resolved.
                # Since we iterate, we might need topological processing for deep chains.
                # For simplicity in this pass: We look at the 'is_resolved' flag of the child.
                # BUT 'is_resolved' for the child might not be set yet if we iterate in random order.
                pass 
                
        # Better Strategy for Closure: Topological processing from Leaves up to Roots.
        # We can use the Tree structure for this.
        
        # Build Tree Graph
        tree = nx.DiGraph()
        for n in all_nodes:
            tree.add_node(n.id, data=n)
            if n.parent_id:
                tree.add_edge(n.parent_id, n.id) # Parent -> Child
                
        # Iterate post-order (Leaves first, then parents)
        # This ensures children are resolved before we check if they resolve their parent.
        for nid in nx.dfs_postorder_nodes(tree):
            node = nodes_by_id[nid]
            
            # 1. Base Case: Textually resolved?
            # (Already set based on 'has_sorry' in Step 2)
            if node.is_resolved:
                continue
                
            # 2. Recursive Case: Proven by a resolved child?
            candidates = [
                c for c in node.children 
                if c.is_resolved and c.node_type in ('theorem', 'lemma')
            ]
            
            if len(candidates) == 1:
                # Success: Single, resolved child theorem
                proof = candidates[0]
                node.proven_by_statement_id = proof.statement_id
                node.is_resolved = True
                logger.info(f"Node {node.title} resolved by {proof.title}")
            elif len(candidates) > 1:
                logger.warning(f"Ambiguous proofs for {node.title}: {[c.title for c in candidates]}")
                # Remains unresolved

        # Update Project Snapshot
        project.main_commit_sha = main_commit.hexsha
        db.session.commit()