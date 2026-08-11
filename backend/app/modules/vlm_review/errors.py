class VlmProcessingFailed(Exception):
    """VLM technical processing failed without producing a semantic review."""

    code = "VLM_PROCESSING_FAILED"

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.attempts = attempts
