from dk_common.correlation import get_correlation_id, get_request_id


def correlation_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    correlation_id = get_correlation_id()
    request_id = get_request_id()
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers
