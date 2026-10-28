from django.conf import settings

from .models import SiteBranding
from .permissions import get_profile, is_admin_or_global


def role_context(request):
    branding = SiteBranding.get_solo()
    site_logo_url = branding.logo.url if branding.logo else None
    site_background_url = branding.background_image.url if branding.background_image else None

    context = {
        "platform_name": settings.SITE_NAME,
        "site_branding": branding,
        "effective_logo_url": site_logo_url,
        "effective_background_url": site_background_url,
    }

    if not request.user.is_authenticated:
        return context

    profile = get_profile(request.user)
    context.update(
        {
            "user_role": profile.role,
            "user_is_admin_or_global": is_admin_or_global(request.user),
            "user_profile": profile,
            "effective_logo_url": (profile.logo.url if profile.logo else None) or site_logo_url,
            "effective_background_url": (profile.background_image.url if profile.background_image else None)
            or site_background_url,
        }
    )
    return context
