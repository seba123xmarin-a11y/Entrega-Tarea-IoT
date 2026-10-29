import json

from django.conf import settings
from django.contrib import messages
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    DeviceRegistrationForm,
    ManualEntryForm,
    ProductForm,
    ProductIconForm,
    ProductTypeIconForm,
    ProfileBrandingForm,
    SiteBrandingForm,
    UserCreateForm,
    WidgetForm,
)
from .models import Device, ManualEntry, Product, ProductType, Profile, Sensor, SiteBranding
from .mqtt_publish import publish_command
from .permissions import (
    admin_or_global_required,
    devices_for,
    get_profile,
    get_role,
    global_required,
    is_admin_or_global,
    is_global,
    products_for,
)

SEED_READINGS_COUNT = 50


@login_required
def dashboard(request):
    devices = devices_for(request.user).filter(is_active=True).prefetch_related("sensors").order_by("name")

    seed_data = {}
    for device in devices:
        for sensor in device.sensors.filter(is_active=True):
            readings = list(sensor.readings.order_by("-timestamp")[:SEED_READINGS_COUNT])
            readings.reverse()
            seed_data[sensor.id] = [{"t": r.timestamp.isoformat(), "v": r.value} for r in readings]

    context = {
        "devices": devices,
        "seed_data": seed_data,
    }
    return render(request, "monitoring/dashboard.html", context)


@login_required
def api_latest_values(request):
    visible_devices = devices_for(request.user)
    sensors = Sensor.objects.filter(
        is_active=True, device__is_active=True, device__in=visible_devices
    ).select_related("device")

    sensor_payload = []
    for sensor in sensors:
        latest = sensor.readings.first()
        sensor_payload.append(
            {
                "id": sensor.id,
                "device_slug": sensor.device.slug,
                "variable": sensor.variable,
                "unit": sensor.unit,
                "value": latest.value if latest else None,
                "timestamp": latest.timestamp.isoformat() if latest else None,
            }
        )

    device_payload = [
        {
            "id": device.id,
            "slug": device.slug,
            "name": device.name,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        }
        for device in visible_devices.filter(is_active=True)
    ]

    return JsonResponse(
        {
            "server_time": timezone.now().isoformat(),
            "sensors": sensor_payload,
            "devices": device_payload,
        }
    )


DEVICE_SORT_CHOICES = {
    "name": "Nombre (A-Z)",
    "-name": "Nombre (Z-A)",
    "-created_at": "Fecha de alta (más reciente)",
    "created_at": "Fecha de alta (más antigua)",
    "-last_seen_at": "Últ. lectura (más reciente)",
    "last_seen_at": "Últ. lectura (más antigua)",
}


@login_required
def device_list(request):
    devices = devices_for(request.user).select_related("product")

    status = request.GET.get("status", "")
    if status == "active":
        devices = devices.filter(is_active=True)
    elif status == "inactive":
        devices = devices.filter(is_active=False)

    assignment = request.GET.get("assignment", "")
    if assignment == "assigned":
        devices = devices.filter(product__isnull=False)
    elif assignment == "unassigned":
        devices = devices.filter(product__isnull=True)

    sort = request.GET.get("sort", "name")
    if sort not in DEVICE_SORT_CHOICES:
        sort = "name"
    devices = devices.order_by(sort)

    context = {
        "devices": devices,
        "sort_choices": DEVICE_SORT_CHOICES,
        "selected_sort": sort,
        "selected_status": status,
        "selected_assignment": assignment,
    }
    return render(request, "monitoring/device_list.html", context)


@login_required
def device_create(request):
    if request.method == "POST":
        form = DeviceRegistrationForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.owner = request.user
            device.save()
            messages.success(request, f"Dispositivo «{device.name}» registrado. Programa el token en el hardware.")
            return redirect("monitoring:device-provisioning", pk=device.pk)
    else:
        form = DeviceRegistrationForm()
    return render(request, "monitoring/device_form.html", {"form": form})


@login_required
def device_provisioning(request, pk):
    device = get_object_or_404(devices_for(request.user), pk=pk)
    suggested_ap_name = f"{device.slug}-{device.tag}" if device.tag else device.slug
    context = {
        "device": device,
        "suggested_ap_name": suggested_ap_name,
        "mqtt_topic_example": f"{settings.MQTT_TOPIC_PREFIX}/{device.slug}/<variable>",
    }
    return render(request, "monitoring/device_provisioning.html", context)


@login_required
def device_regenerate_token(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    device = get_object_or_404(devices_for(request.user), pk=pk)
    device.regenerate_token()
    messages.success(request, "Token regenerado. Actualiza el firmware del dispositivo con el nuevo token.")
    return redirect("monitoring:device-provisioning", pk=device.pk)


@login_required
def sensor_widget_edit(request, pk):
    sensor = get_object_or_404(Sensor.objects.filter(device__in=devices_for(request.user)), pk=pk)
    widget = sensor.get_widget()

    if request.method == "POST":
        form = WidgetForm(request.POST, instance=widget)
        if form.is_valid():
            form.save()
            messages.success(request, f"Gadget de «{sensor}» actualizado.")
            return redirect("monitoring:dashboard")
    else:
        form = WidgetForm(instance=widget)

    context = {
        "sensor": sensor,
        "form": form,
        "command_topic_example": f"{settings.MQTT_TOPIC_PREFIX}/{sensor.device.slug}/{sensor.variable}/set",
    }
    return render(request, "monitoring/widget_form.html", context)


@login_required
@require_POST
def sensor_command(request, pk):
    sensor = get_object_or_404(Sensor.objects.filter(device__in=devices_for(request.user)), pk=pk)
    widget = sensor.get_widget()

    if not widget.is_control:
        return JsonResponse({"error": "Este sensor no acepta comandos."}, status=400)

    try:
        body = json.loads(request.body)
        value = float(body["value"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Valor inválido."}, status=400)

    ok = publish_command(sensor.device, sensor.variable, value)
    if not ok:
        return JsonResponse({"error": "No se pudo publicar el comando (broker MQTT no disponible)."}, status=502)

    return JsonResponse({"published": True, "value": value})


USER_SORT_CHOICES = {
    "username": "Usuario (A-Z)",
    "-username": "Usuario (Z-A)",
    "-date_joined": "Alta (más reciente)",
    "date_joined": "Alta (más antigua)",
}


@admin_or_global_required
def user_list(request):
    role_labels = dict(Profile.ROLE_CHOICES)
    users = User.objects.select_related("profile")

    role = request.GET.get("role", "")
    if role in role_labels:
        users = users.filter(profile__role=role)

    status = request.GET.get("status", "")
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    sort = request.GET.get("sort", "username")
    if sort not in USER_SORT_CHOICES:
        sort = "username"
    users = users.order_by(sort)

    rows = [{"user": u, "role_label": role_labels[get_role(u)]} for u in users]
    context = {
        "rows": rows,
        "role_choices": Profile.ROLE_CHOICES,
        "sort_choices": USER_SORT_CHOICES,
        "selected_role": role,
        "selected_status": status,
        "selected_sort": sort,
    }
    return render(request, "monitoring/user_list.html", context)


@admin_or_global_required
def user_create(request):
    creator_role = get_role(request.user)
    if request.method == "POST":
        form = UserCreateForm(request.POST, creator_role=creator_role)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuario «{user.username}» creado.")
            return redirect("monitoring:user-list")
    else:
        form = UserCreateForm(creator_role=creator_role)
    return render(request, "monitoring/user_form.html", {"form": form})


@admin_or_global_required
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    next_url = request.POST.get("next") or "monitoring:user-list"

    if target == request.user:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return redirect(next_url)

    if target.is_active and is_global(target):
        other_active_globals = (
            User.objects.filter(is_active=True, profile__role=Profile.ROLE_GLOBAL).exclude(pk=target.pk).count()
        )
        if other_active_globals == 0:
            messages.error(request, "No puedes desactivar al último usuario Global activo.")
            return redirect(next_url)

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    state = "activado" if target.is_active else "desactivado"
    messages.success(request, f"Usuario «{target.username}» {state}.")
    return redirect(next_url)


@admin_or_global_required
def user_detail(request, pk):
    target = get_object_or_404(User, pk=pk)
    products = Product.objects.filter(owner=target).select_related("product_type").order_by("name")
    sensors = Sensor.objects.filter(device__owner=target).select_related("device").order_by("device__name", "variable")

    context = {
        "target": target,
        "role_label": dict(Profile.ROLE_CHOICES)[get_role(target)],
        "products": products,
        "sensors": sensors,
        "products_count": products.count(),
        "sensors_count": sensors.count(),
        "sensors_active_count": sensors.filter(is_active=True).count(),
    }
    return render(request, "monitoring/user_detail.html", context)


@login_required
def device_location(request, pk):
    device = get_object_or_404(devices_for(request.user), pk=pk)

    if request.method == "POST":
        try:
            lat = float(request.POST["latitude"])
            lng = float(request.POST["longitude"])
        except (KeyError, ValueError):
            messages.error(request, "Coordenadas inválidas.")
        else:
            device.latitude = lat
            device.longitude = lng
            device.save(update_fields=["latitude", "longitude"])
            messages.success(request, f"Ubicación de «{device.name}» actualizada.")
            return redirect("monitoring:device-location", pk=device.pk)

    context = {
        "device": device,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, "monitoring/device_location.html", context)


def _generic_map_icon_url():
    branding = SiteBranding.get_solo()
    if branding.map_icon:
        return branding.map_icon.url
    return static("monitoring/img/ecs-mark.svg")


def _sensor_payload_for(device):
    payload = []
    for sensor in device.sensors.filter(is_active=True):
        latest = sensor.readings.first()
        payload.append(
            {
                "variable": sensor.variable,
                "unit": sensor.unit,
                "value": latest.value if latest else None,
            }
        )
    return payload


@login_required
def devices_map(request):
    generic_icon_url = _generic_map_icon_url()
    markers = []

    products = products_for(request.user).filter(is_active=True).select_related("product_type")
    for p in products:
        if not p.has_location:
            continue
        sensors_payload = []
        for device in p.devices.filter(is_active=True):
            sensors_payload.extend(_sensor_payload_for(device))

        manual_entries_payload = []
        if not p.devices.exists():
            manual_entries_payload = [
                {
                    "note": entry.note,
                    "variable": entry.variable,
                    "value": entry.value,
                    "unit": entry.unit,
                    "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                for entry in p.manual_entries.all()[:5]
            ]

        markers.append(
            {
                "kind": "product",
                "id": p.id,
                "name": p.name,
                "product_type": p.product_type.name,
                "owner": p.owner.username,
                "lat": p.latitude,
                "lng": p.longitude,
                "sensors": sensors_payload,
                "manual_entries": manual_entries_payload,
                "icon_url": p.map_icon.url if p.map_icon else generic_icon_url,
            }
        )

    standalone_devices = devices_for(request.user).filter(is_active=True, product__isnull=True)
    for d in standalone_devices:
        if not d.has_location:
            continue
        markers.append(
            {
                "kind": "device",
                "id": d.id,
                "name": d.name,
                "slug": d.slug,
                "owner": d.owner.username,
                "lat": d.latitude,
                "lng": d.longitude,
                "sensors": _sensor_payload_for(d),
                "manual_entries": [],
                "icon_url": generic_icon_url,
            }
        )

    total_items = products.count() + standalone_devices.count()

    context = {
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "markers": markers,
        "markers_json": json.dumps(markers),
        "total_devices": total_items,
        "located_devices": len(markers),
    }
    return render(request, "monitoring/map.html", context)


@login_required
def profile_branding_edit(request):
    profile = get_profile(request.user)

    if request.method == "POST":
        form = ProfileBrandingForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Tu proyecto se actualizó.")
            return redirect("monitoring:dashboard")
    else:
        form = ProfileBrandingForm(instance=profile)

    return render(request, "monitoring/profile_branding_form.html", {"form": form})


@global_required
def site_branding_edit(request):
    branding = SiteBranding.get_solo()

    if request.method == "POST":
        form = SiteBrandingForm(request.POST, request.FILES, instance=branding)
        if form.is_valid():
            form.save()
            messages.success(request, "Marca del sitio actualizada.")
            return redirect("monitoring:site-branding-edit")
    else:
        form = SiteBrandingForm(instance=branding)

    return render(request, "monitoring/site_branding_form.html", {"form": form})


PRODUCT_SORT_CHOICES = {
    "name": "Nombre (A-Z)",
    "-name": "Nombre (Z-A)",
    "-created_at": "Fecha de alta (más reciente)",
    "created_at": "Fecha de alta (más antigua)",
}


@login_required
def product_list(request):
    visible_products = products_for(request.user)

    products = visible_products.select_related("product_type", "owner")

    type_slug = request.GET.get("type", "")
    if type_slug:
        products = products.filter(product_type__slug=type_slug)

    status = request.GET.get("status", "")
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)

    sort = request.GET.get("sort", "name")
    if sort not in PRODUCT_SORT_CHOICES:
        sort = "name"
    products = products.order_by(sort)

    product_types = ProductType.objects.annotate(
        product_count=Count("products", filter=Q(products__in=visible_products))
    )

    context = {
        "products": products,
        "product_types": product_types,
        "total_count": visible_products.count(),
        "sort_choices": PRODUCT_SORT_CHOICES,
        "selected_type": type_slug,
        "selected_status": status,
        "selected_sort": sort,
        "can_view_user_detail": is_admin_or_global(request.user),
    }
    return render(request, "monitoring/product_list.html", context)


@login_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.owner = request.user
            product.save()
            messages.success(request, f"Producto «{product.name}» creado.")
            return redirect("monitoring:product-detail", pk=product.pk)
    else:
        form = ProductForm()
    return render(request, "monitoring/product_form.html", {"form": form})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(products_for(request.user), pk=pk)
    devices = product.devices.filter(is_active=True).prefetch_related("sensors")
    manual_entries = product.manual_entries.all()[:20]
    context = {
        "product": product,
        "devices": devices,
        "manual_entries": manual_entries,
        "manual_entry_form": ManualEntryForm(),
        "is_global": is_global(request.user),
        "icon_form": ProductIconForm(instance=product) if is_global(request.user) else None,
    }
    return render(request, "monitoring/product_detail.html", context)


@global_required
def product_icon_edit(request, pk):
    """Ícono de mapa exclusivo de este producto. Solo el rol Global puede editarlo."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        form = ProductIconForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Ícono de «{product.name}» actualizado.")
        else:
            messages.error(request, "No se pudo guardar el ícono: revisa el archivo.")

    return redirect("monitoring:product-detail", pk=product.pk)


@login_required
def product_device_create(request, pk):
    product = get_object_or_404(products_for(request.user), pk=pk)
    if request.method == "POST":
        form = DeviceRegistrationForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.owner = request.user
            device.product = product
            device.save()
            messages.success(request, f"Dispositivo «{device.name}» agregado a «{product.name}».")
            return redirect("monitoring:device-provisioning", pk=device.pk)
    else:
        form = DeviceRegistrationForm()
    return render(request, "monitoring/device_form.html", {"form": form, "product": product})


@login_required
def product_location_edit(request, pk):
    product = get_object_or_404(products_for(request.user), pk=pk)

    if request.method == "POST":
        try:
            lat = float(request.POST["latitude"])
            lng = float(request.POST["longitude"])
        except (KeyError, ValueError):
            messages.error(request, "Coordenadas inválidas.")
        else:
            product.latitude = lat
            product.longitude = lng
            product.save(update_fields=["latitude", "longitude"])
            messages.success(request, f"Ubicación de «{product.name}» actualizada.")
            return redirect("monitoring:product-location-edit", pk=product.pk)

    context = {
        "product": product,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, "monitoring/product_location.html", context)


@login_required
@require_POST
def product_toggle_active(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not (is_admin_or_global(request.user) or product.owner_id == request.user.id):
        raise PermissionDenied

    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    state = "activado" if product.is_active else "desactivado"
    messages.success(request, f"Producto «{product.name}» {state}.")
    return redirect(request.POST.get("next") or "monitoring:product-list")


@login_required
@require_POST
def sensor_toggle_active(request, pk):
    sensor = get_object_or_404(Sensor, pk=pk)
    if not (is_admin_or_global(request.user) or sensor.device.owner_id == request.user.id):
        raise PermissionDenied

    sensor.is_active = not sensor.is_active
    sensor.save(update_fields=["is_active"])
    state = "activado" if sensor.is_active else "desactivado"
    messages.success(request, f"Sensor «{sensor}» {state}.")
    return redirect(request.POST.get("next") or "monitoring:device-list")


@login_required
@require_POST
def product_manual_entry_create(request, pk):
    product = get_object_or_404(products_for(request.user), pk=pk)
    form = ManualEntryForm(request.POST)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.product = product
        entry.created_by = request.user
        entry.save()
        messages.success(request, "Entrada registrada.")
    else:
        messages.error(request, "No se pudo guardar la entrada: revisa los datos.")
    return redirect("monitoring:product-detail", pk=product.pk)


@global_required
def product_type_list(request):
    product_types = list(ProductType.objects.all())
    forms_by_id = {pt.id: ProductTypeIconForm(instance=pt) for pt in product_types}

    if request.method == "POST":
        pt = get_object_or_404(ProductType, pk=request.POST.get("product_type_id"))
        form = ProductTypeIconForm(request.POST, request.FILES, instance=pt)
        if form.is_valid():
            form.save()
            messages.success(request, f"Ícono de «{pt.name}» actualizado.")
            return redirect("monitoring:product-type-list")
        forms_by_id[pt.id] = form

    rows = [{"product_type": pt, "form": forms_by_id[pt.id]} for pt in product_types]
    return render(request, "monitoring/product_type_list.html", {"rows": rows})


@global_required
def platform_overview(request):
    role_labels = dict(Profile.ROLE_CHOICES)
    users = list(User.objects.order_by("username"))
    product_types = list(ProductType.objects.all())

    role_counts = {role: 0 for role, _ in Profile.ROLE_CHOICES}
    for u in users:
        role_counts[get_role(u)] += 1

    rows = []
    for u in users:
        products_qs = Product.objects.filter(owner=u)
        devices_qs = Device.objects.filter(owner=u)
        sensors_qs = Sensor.objects.filter(device__owner=u)
        rows.append(
            {
                "user": u,
                "role_label": role_labels[get_role(u)],
                "product_counts": [products_qs.filter(product_type=pt).count() for pt in product_types],
                "devices_active": devices_qs.filter(is_active=True).count(),
                "devices_inactive": devices_qs.filter(is_active=False).count(),
                "sensors_active": sensors_qs.filter(is_active=True).count(),
                "sensors_inactive": sensors_qs.filter(is_active=False).count(),
            }
        )

    context = {
        "role_counts": role_counts,
        "total_users": len(users),
        "product_types": product_types,
        "rows": rows,
    }
    return render(request, "monitoring/overview.html", context)
