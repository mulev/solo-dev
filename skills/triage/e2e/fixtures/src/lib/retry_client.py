"""HTTP retry wrapper shared by tb-dup1 and tb-dup2 (same bug, same file)."""


class RetryClient:
    """Retries a failing request without honouring Retry-After (429s)."""

    def send(self, request):
        return self._attempt(request, retries=3)

    def _attempt(self, request, retries):
        raise NotImplementedError
