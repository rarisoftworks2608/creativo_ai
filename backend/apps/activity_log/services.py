from .models import ActivityLog


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_activity(*, module, action, description='', user=None, company=None,
                  old_value=None, new_value=None, request=None):
    """Records one audit trail entry. The single write path for ActivityLog (Epic 18).

    Pass `request` when available - it fills in the acting user (if not given
    explicitly) and the IP address for free.
    """
    ip_address = None
    if request is not None:
        ip_address = _client_ip(request)
        if user is None and getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user

    return ActivityLog.objects.create(
        user=user,
        company=company,
        module=module,
        action=action,
        description=description,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
