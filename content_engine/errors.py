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
    pass
