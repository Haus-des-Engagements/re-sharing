from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_http_methods

from re_sharing.emails.forms import EmailLogFilterForm
from re_sharing.emails.models import EmailLog
from re_sharing.emails.selectors import get_email_logs
from re_sharing.emails.services import resend_emails
from re_sharing.providers.decorators import manager_required

EMAILS_PER_PAGE = 50


@manager_required
@require_http_methods(["GET"])
def list_emails_view(request: HttpRequest) -> HttpResponse:
    form = EmailLogFilterForm(request.GET)
    # an invalid filter value is ignored, the others still apply
    form.is_valid()
    filters = {name: value for name, value in form.cleaned_data.items() if value}
    page = Paginator(get_email_logs(**filters), EMAILS_PER_PAGE).get_page(
        request.GET.get("page")
    )
    # page links keep the active filters
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "emails/list_emails.html",
        {"form": form, "page": page, "filter_query": query.urlencode()},
    )


@manager_required
@require_http_methods(["GET"])
def show_email_view(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(
        EmailLog.objects.select_related("organization", "booking", "user"), pk=pk
    )
    return render(request, "emails/show_email.html", {"entry": entry})


def _report_scheduled(request: HttpRequest, count: int) -> None:
    messages.success(
        request,
        ngettext(
            "%(count)d email is scheduled to be sent again.",
            "%(count)d emails are scheduled to be sent again.",
            count,
        )
        % {"count": count},
    )


@manager_required
@require_http_methods(["POST"])
def resend_email_view(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(EmailLog, pk=pk)
    _report_scheduled(request, resend_emails([entry]))
    return redirect(entry)


@manager_required
@require_http_methods(["POST"])
def resend_selected_emails_view(request: HttpRequest) -> HttpResponse:
    selected = [pk for pk in request.POST.getlist("selected") if pk.isdigit()]
    entries = EmailLog.objects.filter(pk__in=selected).order_by("created", "id")
    if entries:
        _report_scheduled(request, resend_emails(entries))
    else:
        messages.warning(request, _("Please select at least one email."))
    return redirect("emails:list-emails")
