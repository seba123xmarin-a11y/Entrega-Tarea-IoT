from django.contrib import admin

from .models import (
    Device,
    ManualEntry,
    Product,
    ProductType,
    Profile,
    Sensor,
    SensorReading,
    UnregisteredReading,
    Widget,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ManualEntryInline(admin.TabularInline):
    model = ManualEntry
    extra = 0
    fields = ("note", "variable", "value", "unit", "created_by", "created_at")
    readonly_fields = ("created_by", "created_at")


class DeviceInline(admin.TabularInline):
    model = Device
    extra = 0
    fields = ("name", "slug", "owner", "is_active")
    readonly_fields = ("name", "slug", "owner", "is_active")
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "owner", "is_active", "created_at")
    list_filter = ("product_type", "is_active")
    search_fields = ("name", "owner__username")
    inlines = [DeviceInline, ManualEntryInline]


class SensorInline(admin.TabularInline):
    model = Sensor
    extra = 0
    fields = ("variable", "unit", "is_active", "created_at")
    readonly_fields = ("created_at",)


class WidgetInline(admin.StackedInline):
    model = Widget
    extra = 0
    max_num = 1
    fields = (
        "widget_type",
        "min_value",
        "max_value",
        "led_on_threshold",
        "button_on_value",
        "button_off_value",
        "slider_step",
    )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "product", "tag", "location", "is_active", "last_seen_at", "created_at")
    list_filter = ("is_active", "owner", "product")
    search_fields = ("name", "slug", "location", "tag", "owner__username")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("auth_token", "created_at", "last_seen_at")
    inlines = [SensorInline]
    actions = ["regenerate_token"]

    @admin.action(description="Regenerar token de autenticación")
    def regenerate_token(self, request, queryset):
        for device in queryset:
            device.regenerate_token()
        self.message_user(request, f"Token regenerado para {queryset.count()} dispositivo(s).")


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ("device", "variable", "unit", "is_active", "created_at")
    list_filter = ("is_active", "variable")
    search_fields = ("device__name", "device__slug", "variable")
    readonly_fields = ("created_at",)
    inlines = [WidgetInline]


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ("sensor", "value", "timestamp")
    list_filter = ("sensor__device", "sensor__variable")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        # Readings only ever arrive via the MQTT listener.
        return False


@admin.register(UnregisteredReading)
class UnregisteredReadingAdmin(admin.ModelAdmin):
    list_display = ("topic", "reason", "received_at")
    list_filter = ("reason",)
    ordering = ("-received_at",)
    readonly_fields = ("topic", "raw_payload", "reason", "received_at")

    def has_add_permission(self, request):
        return False
