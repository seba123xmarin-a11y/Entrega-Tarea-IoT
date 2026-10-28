from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/sensors/latest/", views.api_latest_values, name="api-latest"),
    path("api/dashboard/order/", views.dashboard_order, name="dashboard-order"),
    path("devices/", views.device_list, name="device-list"),
    path("devices/add/", views.device_create, name="device-create"),
    path("devices/<int:pk>/provisioning/", views.device_provisioning, name="device-provisioning"),
    path("devices/<int:pk>/regenerate-token/", views.device_regenerate_token, name="device-regenerate-token"),
    path("sensors/<int:pk>/widget/", views.sensor_widget_edit, name="sensor-widget-edit"),
    path("sensors/<int:pk>/toggle-active/", views.sensor_toggle_active, name="sensor-toggle-active"),
    path("api/sensors/<int:pk>/command/", views.sensor_command, name="sensor-command"),
    path("users/", views.user_list, name="user-list"),
    path("users/add/", views.user_create, name="user-create"),
    path("users/<int:pk>/", views.user_detail, name="user-detail"),
    path("users/<int:pk>/toggle-active/", views.user_toggle_active, name="user-toggle-active"),
    path("devices/<int:pk>/location/", views.device_location, name="device-location"),
    path("map/", views.devices_map, name="devices-map"),
    path("profile/branding/", views.profile_branding_edit, name="profile-branding-edit"),
    path("branding/", views.site_branding_edit, name="site-branding-edit"),
    path("products/", views.product_list, name="product-list"),
    path("products/add/", views.product_create, name="product-create"),
    path("products/<int:pk>/", views.product_detail, name="product-detail"),
    path("products/<int:pk>/devices/add/", views.product_device_create, name="product-device-create"),
    path("products/<int:pk>/location/", views.product_location_edit, name="product-location-edit"),
    path("products/<int:pk>/icon/", views.product_icon_edit, name="product-icon-edit"),
    path("products/<int:pk>/toggle-active/", views.product_toggle_active, name="product-toggle-active"),
    path(
        "products/<int:pk>/manual-entry/add/",
        views.product_manual_entry_create,
        name="product-manual-entry-create",
    ),
    path("product-types/", views.product_type_list, name="product-type-list"),
    path("overview/", views.platform_overview, name="platform-overview"),
]
