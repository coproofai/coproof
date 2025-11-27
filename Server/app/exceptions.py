class CoProofError(Exception):
    """Base exception for all CoProof custom errors."""
    def __init__(self, message, code=500, payload=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['error_code'] = self.code
        return rv

# --- Git Engine Exceptions ---

class GitResourceError(CoProofError):
    """Raised when a repo or file cannot be found/accessed."""
    def __init__(self, message="Git resource error", payload=None):
        super().__init__(message, code=404, payload=payload)

class GitLockError(CoProofError):
    """Raised when a Redis lock cannot be acquired (concurrency)."""
    def __init__(self, message="Resource is currently locked by another process", payload=None):
        super().__init__(message, code=409, payload=payload)

class GitOperationError(CoProofError):
    """Raised when a git command (commit, push, merge) fails."""
    def __init__(self, message="Git operation failed", payload=None):
        super().__init__(message, code=500, payload=payload)

# --- Agent/AI Exceptions ---

class AgentTimeoutError(CoProofError):
    """Raised when the external Black Box agent does not respond."""
    def __init__(self, message="Exploration agent timed out", payload=None):
        super().__init__(message, code=504, payload=payload)