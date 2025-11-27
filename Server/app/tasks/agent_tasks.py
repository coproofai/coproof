import logging
from app.extensions import celery, db
from app.models.async_job import AsyncJob
from app.services.integrations import ExplorationAgentClient, CompilerClient

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def run_agent_exploration(self, job_id, context, strategy, hint):
    """
    CDU-17: Ask Agent to solve a theorem.
    """
    job = AsyncJob.query.get(job_id)
    if not job:
        return

    try:
        job.status = 'processing'
        db.session.commit()
        
        # Call Black Box Agent
        result = ExplorationAgentClient.trigger_proof_search(context, strategy, hint)
        
        # Save Result
        job.status = 'completed'
        job.result_metadata = result # e.g. {"next_step": "apply lemma_1"}
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Agent Exploration failed: {e}")
        job.status = 'failed'
        job.error_log = str(e)
        db.session.commit()

@celery.task(bind=True)
def task_translate_nl(self, job_id, nl_text, context):
    """
    RF-002: Translate NL to Lean.
    Moved here because Translation is an AI/Agent capability.
    """
    job = AsyncJob.query.get(job_id)
    if not job:
        return

    try:
        job.status = 'processing'
        db.session.commit()
        
        # Call Translator (Compiler Client)
        result = CompilerClient.translate_nl_to_lean(nl_text, context)
        
        job.status = 'completed'
        job.result_metadata = result
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        job.status = 'failed'
        job.error_log = str(e)
        db.session.commit()