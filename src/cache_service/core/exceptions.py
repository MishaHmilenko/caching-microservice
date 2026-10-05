"""Root of the application's exception hierarchy.

Every error the application raises on purpose derives from :class:`BaseError` and declares
its own HTTP status, so one handler can serve the whole tree and new errors need no extra
registration.
"""


class BaseError(Exception):
    """Base class of all intentional application errors.

    Subclasses override :attr:`status_code` and :attr:`default_detail`.
    """

    status_code: int = 500
    default_detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        """Create the error.

        :param detail: Client-facing message; :attr:`default_detail` when omitted.
        """
        self.detail = detail or self.default_detail
        super().__init__(self.detail)
