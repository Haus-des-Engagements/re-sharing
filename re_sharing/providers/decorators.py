from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest


def manager_required(view_func):
    """
    Decorator for views that checks that the user is a manager.
    """

    @wraps(view_func)
    @login_required
    def _wrapped_view(request: HttpRequest, *args, **kwargs):
        if not request.user.is_manager():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped_view
