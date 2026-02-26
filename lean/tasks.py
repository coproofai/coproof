from celery_service import celery
from lean_service import (
    to_compiler_snippet_response,
    to_compiler_project_response,
)


@celery.task(name="tasks.verify_snippet")
def verify_snippet(lean_code: str, filename: str = "snippet.lean"):
    return to_compiler_snippet_response(lean_code, filename)


@celery.task(name="tasks.verify_project_files")
def verify_project_files(file_map: dict, entry_file: str):
    return to_compiler_project_response(file_map, entry_file)

