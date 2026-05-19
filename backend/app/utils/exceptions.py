from fastapi import HTTPException


class SessionNotFoundError(HTTPException):
    def __init__(self, session_id: str = ""):
        super().__init__(status_code=404, detail=f"Session not found: {session_id}")


class SessionExpiredError(HTTPException):
    def __init__(self):
        super().__init__(status_code=410, detail="Session has expired")


class NoFilesUploadedError(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="No MATLAB files have been uploaded for this session")


class InferenceNotCompleteError(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="Inference has not completed yet")


class InvalidFileTypeError(HTTPException):
    def __init__(self, filename: str, expected: str):
        super().__init__(
            status_code=422,
            detail=f"Invalid file type for '{filename}'. Expected: {expected}",
        )


class FileTooLargeError(HTTPException):
    def __init__(self, filename: str, max_mb: int):
        super().__init__(
            status_code=413,
            detail=f"File '{filename}' exceeds maximum size of {max_mb}MB",
        )


class MissingColumnsError(HTTPException):
    def __init__(self, filename: str, missing: list):
        super().__init__(
            status_code=422,
            detail=f"File '{filename}' missing required columns: {missing}",
        )


class ModelNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=503, detail="ML model not loaded. Please ensure model file exists.")


class StorageError(HTTPException):
    def __init__(self, detail: str = "Storage operation failed"):
        super().__init__(status_code=500, detail=detail)


class TaskAlreadyRunningError(HTTPException):
    def __init__(self, task: str):
        super().__init__(status_code=409, detail=f"A {task} task is already running for this session")
