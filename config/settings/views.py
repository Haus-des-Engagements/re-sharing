from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.static import serve

from config.settings.base import MEDIA_ROOT
from roomsharing.organizations.models import Organization
from roomsharing.organizations.services import user_has_admin_bookingpermission


@login_required
def protected_media(request, path):
    """
    When trying to access media, check if it is a protected file.
    """
    access_granted = False

    user = request.user
    if not path.startswith("protected/") or user.is_staff:
        access_granted = True
    else:
        organization = get_object_or_404(Organization, usage_agreement=path)
        if user_has_admin_bookingpermission(user, organization):
            access_granted = True

    if access_granted:
        return serve(request, path, document_root=MEDIA_ROOT, show_indexes=False)

    return HttpResponseForbidden("Not authorized to access this media.")
