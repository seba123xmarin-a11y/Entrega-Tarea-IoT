from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Device, Product, Profile


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={"role": Profile.ROLE_GLOBAL if user.is_superuser else Profile.ROLE_OWNER},
    )
    return profile


def get_role(user):
    return get_profile(user).role


def is_global(user):
    return get_role(user) == Profile.ROLE_GLOBAL


def is_admin_or_global(user):
    return get_role(user) in (Profile.ROLE_ADMIN, Profile.ROLE_GLOBAL)


def is_viewer(user):
    return get_role(user) == Profile.ROLE_VIEWER


def devices_for(user):
    """Devices visible to this user: all of them for Global and Visualizador, only owned ones otherwise."""
    if get_role(user) in (Profile.ROLE_GLOBAL, Profile.ROLE_VIEWER):
        return Device.objects.all()
    return Device.objects.filter(owner=user)


def products_for(user):
    """Products visible to this user: all of them for Global, only owned ones otherwise."""
    if is_global(user):
        return Product.objects.all()
    return Product.objects.filter(owner=user)


def admin_or_global_required(view_func):
    """Gate for user-management views: requires login AND role admin/global (403 otherwise)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin_or_global(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)


def global_required(view_func):
    """Gate for platform-wide settings (site branding): requires login AND role global."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_global(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)
