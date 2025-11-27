from app.models.async_job import AsyncJob

def test_job_persistence(init_db):
    job = AsyncJob(
        celery_task_id="abc-123",
        job_type="agent_exploration",
        status="processing",
        result_metadata={"steps": 5}
    )
    init_db.session.add(job)
    init_db.session.commit()
    
    retrieved = AsyncJob.query.first()
    assert retrieved.celery_task_id == "abc-123"
    assert retrieved.result_metadata['steps'] == 5