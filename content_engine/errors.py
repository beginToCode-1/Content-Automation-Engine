class PipelineError(Exception):
    """Base class for all errors raised by a pipeline stage."""


class ConfigError(PipelineError):
    pass


class SearchFailedError(PipelineError):
    pass


class DownloadFailedError(PipelineError):
    pass


class NoTranscriptAvailableError(PipelineError):
    pass


class RenderFailedError(PipelineError):
    pass


class MetadataGenerationError(PipelineError):
    pass


class UploadFailedError(PipelineError):
    """Raised when a platform upload fails. `retryable` marks whether the
    failure looks transient (network blip, timeout, 5xx/429) and worth
    retrying, versus terminal (bad credentials, missing config, rejected
    content) where a retry would just fail again immediately."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class RunCancelledError(PipelineError):
    """Raised when a run is cancelled mid-flight via a cooperative
    cancellation check between pipeline stages."""
