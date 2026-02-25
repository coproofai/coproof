import requests
import logging
import os
import time
from app.exceptions import CoProofError

logger = logging.getLogger(__name__)

class CompilerClient:
    """
    Interface for the External Lean Compiler & Translation Microservice.
    """
    
    # URL of your external microservice container
    BASE_URL = os.environ.get('COMPILER_SERVICE_URL', 'http://localhost:8002')



    @staticmethod
    def verify_project_content(full_source_code: str):
        """
        Sends the fully concatenated Lean project code for verification.
        
        Lean service must:
         - Wrap content in a temporary Lean project
         - Provide correct imports / lakefile context
        
        Make sure your compiler service:
         - Creates ephemeral project
         - Places main.lean inside
         - Runs lake build

        Returns:
        {
            "compile_success": bool,
            "contains_sorry": bool,
            "errors": str
        }
        """
        # We wrap the content in a JSON payload. 
        # Ensure the compiler service accepts "code" or "content".
        payload = {
            "code": full_source_code
        }


        try:
            # We use a specific endpoint for full package verification via content
            resp = requests.post(f"{CompilerClient.BASE_URL}/v1/verify/content", json=payload, timeout=120)
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "compile_success": data.get("compile_success", False),
                    "contains_sorry": data.get("contains_sorry", False),
                    "errors": data.get("errors", "")
                }
            else:
                logger.error(f"Compiler service returned {resp.status_code}: {resp.text}")
                return {
                    "compile_success": False,
                    "contains_sorry": False,
                    "errors": f"System Error: Compiler service returned {resp.status_code}"
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Compiler connection failed: {e}")
            raise CoProofError(f"Compiler Service Unavailable: {str(e)}", code=503)

    @staticmethod
    def translate_nl_to_lean(nl_text: str, context: str = ""):
        """
        Sends Natural Language -> Returns Lean Code.
        """
        payload = {
            "text": nl_text,
            "context": context # e.g., previous lemmas
        }
        try:
            resp = requests.post(f"{CompilerClient.BASE_URL}/v1/translate", json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json() # Expected: {"lean_code": "..."}
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise CoProofError(f"Translation Service Unavailable: {str(e)}", code=503)

    @staticmethod
    def verify_code_snippet(lean_code: str, dependencies: list = None):
        """
        Ephemeral Check: Sends raw code to check for syntax/type errors.
        Does NOT require a full Git repo sync.
        """
        payload = {
            "code": lean_code,
            "dependencies": dependencies or []
        }
        try:
            started = time.perf_counter()
            resp = requests.post(f"{CompilerClient.BASE_URL}/v1/verify/snippet", json=payload, timeout=10)
            resp.raise_for_status()
            elapsed = time.perf_counter() - started
            data = resp.json()

            if "processing_time_seconds" not in data:
                data["processing_time_seconds"] = round(elapsed, 6)
                data["timing_source"] = "backend_fallback"
            else:
                data["timing_source"] = "lean_server"

            data["roundtrip_time_seconds"] = round(elapsed, 6)
            return data # Expected: {"valid": Bool, "errors": []}
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise CoProofError(f"Compiler Service Unavailable: {str(e)}", code=503)

    @staticmethod
    def compile_project_repo(remote_url: str, commit_hash: str):
        """
        Full Project Check: Tells the compiler to pull the repo and build.
        """
        payload = {
            "repo_url": remote_url,
            "commit": commit_hash
        }
        # This is likely a long-running job, so we might get a Job ID back
        try:
            resp = requests.post(f"{CompilerClient.BASE_URL}/v1/verify/project", json=payload, timeout=5)
            resp.raise_for_status()
            return resp.json() # Expected: {"job_id": "..."}
        except Exception as e:
            raise CoProofError(f"Compiler Job Submission Failed: {str(e)}", code=503)