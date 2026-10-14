"""Extraction errors carrying only public, fixed messages."""


class ExtractionError(Exception):
    status_code = 502
    public_message = "CV extraction failed."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class ExtractionNotConfiguredError(ExtractionError):
    status_code = 503
    public_message = "CV extraction service is not configured."


class ProviderUnavailableError(ExtractionError):
    status_code = 503
    public_message = "CV extraction provider is unavailable."


class ExtractionTimeoutError(ExtractionError):
    status_code = 504
    public_message = "CV extraction provider timed out."


class InvalidExtractionError(ExtractionError):
    public_message = "CV extraction provider returned an invalid response."


class ExtractionRefusedError(ExtractionError):
    public_message = "CV extraction was refused by the provider."
