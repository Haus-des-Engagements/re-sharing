from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _

from re_sharing.providers.models import Manager

# Recovery codes alone are no second factor.
SECOND_FACTORS = [Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN]


def requires_mfa(user) -> bool:
    """Staff and managers see bank data of many organizations."""
    if user.is_staff or user.is_superuser:
        return True
    return Manager.objects.filter(user=user).exists()


class RequireStaffMFAMiddleware:
    """Sends staff and managers without two-factor authentication to its
    setup. Account pages stay reachable so they can set it up or log out."""

    EXEMPT_PREFIXES = ("/accounts/", "/hijack/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_set_up(request):
            setup_url = reverse("mfa_index")
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = setup_url
                return response
            messages.warning(
                request,
                _(
                    "Staff and managers must use two-factor authentication. "
                    "Set it up to continue."
                ),
            )
            return redirect(setup_url)
        return self.get_response(request)

    def _must_set_up(self, request) -> bool:
        if not settings.REQUIRE_STAFF_MFA:
            return False
        user = request.user
        if not user.is_authenticated or getattr(user, "is_hijacked", False):
            return False
        if self._is_exempt(request.path):
            return False
        return requires_mfa(user) and not is_mfa_enabled(user, types=SECOND_FACTORS)

    def _is_exempt(self, path: str) -> bool:
        prefixes = (*self.EXEMPT_PREFIXES, settings.STATIC_URL, settings.MEDIA_URL)
        return any(prefix and path.startswith(prefix) for prefix in prefixes)
