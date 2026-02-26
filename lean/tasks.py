from celery_service import celery
from lean_service import (
    to_compiler_content_response,
    to_compiler_snippet_response,
    translate_nl_to_lean,
    verify_project,
)


@celery.task(name="tasks.verify_content")
def verify_content(lean_code: str, filename: str = "Main.lean"):
    return to_compiler_content_response(lean_code, filename)


@celery.task(name="tasks.verify_snippet")
def verify_snippet(lean_code: str, filename: str = "snippet.lean"):
    return to_compiler_snippet_response(lean_code, filename)


@celery.task(name="tasks.translate")
def translate(text: str, context: str = ""):
    return translate_nl_to_lean(text)


@celery.task(name="tasks.verify_project")
def verify_project_task(repo_url: str, commit: str):
    return verify_project(repo_url, commit)
