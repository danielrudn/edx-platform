"""Helper methods for CORS and CSRF checks. """


import contextlib
import logging
import urllib.parse

from django.conf import settings

log = logging.getLogger(__name__)


def is_cross_domain_request_allowed(request):
    """Check whether we should allow the cross-domain request.

    We allow a cross-domain request only if:

    1) The request is made securely and the referer has "https://" as the protocol.
    2) The referer domain has been whitelisted.

    Arguments:
        request (HttpRequest)

    Returns:
        bool

    """
    referer = request.META.get('HTTP_REFERER')
    referer_parts = urllib.parse.urlparse(referer) if referer else None
    referer_hostname = referer_parts.hostname if referer_parts is not None else None

    # Use CORS_ALLOW_INSECURE *only* for development and testing environments;
    # it should never be enabled in production.
    if not getattr(settings, 'CORS_ALLOW_INSECURE', False):
        if not request.is_secure():
            log.debug(
                "Request is not secure, so we cannot send the CSRF token. "
                "For testing purposes, you can disable this check by setting "
                "`CORS_ALLOW_INSECURE` to True in the settings"
            )
            return False

        if not referer:
            log.debug("No referer provided over a secure connection, so we cannot check the protocol.")
            return False

        if not referer_parts.scheme == 'https':
            log.debug("Referer '%s' must have the scheme 'https'")
            return False

    scheme_with_host = referer
    # if url is like `https://www.foo.bar/baz/` following check will return `https://www.foo.bar`
    if referer and referer_parts.scheme and referer_parts.path:
        scheme_with_host = referer.replace(referer_parts.path, '')

    domain_is_whitelisted = (
        getattr(settings, 'CORS_ORIGIN_ALLOW_ALL', False) or
        scheme_with_host in getattr(settings, 'CORS_ORIGIN_WHITELIST', [])
    )
    if not domain_is_whitelisted:
        if referer_hostname is None:
            # If no referer is specified, we can't check if it's a cross-domain
            # request or not.
            log.debug("Referrer hostname is `None`, so it is not on the whitelist.")
        elif referer_hostname != request.get_host():
            log.info(
                (
                    "Domain '%s' is not on the cross domain whitelist.  "
                    "Add the domain to `CORS_ORIGIN_WHITELIST` or set "
                    "`CORS_ORIGIN_ALLOW_ALL` to True in the settings."
                ), referer_hostname
            )
            log.info("Request host is '%s' and referer is '%s'", request.get_host(), referer)
        else:
            log.debug(
                (
                    "Domain '%s' is the same as the hostname in the request, "
                    "so we are not going to treat it as a cross-domain request."
                ), referer_hostname
            )
        return False

    return True


@contextlib.contextmanager
def skip_cross_domain_referer_check(request):
    """Skip the cross-domain CSRF referer check.

    Django's CSRF middleware performs the referer check
    only when the request is made over a secure connection.
    To skip the check, we patch `request.is_secure()` to
    False.
    """
    is_secure_default = request.is_secure
    request.is_secure = lambda: False
    try:
        yield
    finally:
        request.is_secure = is_secure_default
