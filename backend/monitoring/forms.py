from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Device, ManualEntry, Product, ProductType, Profile, SiteBranding, Widget


class DeviceRegistrationForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["name", "slug", "tag", "location"]
        labels = {
            "name": "Nombre",
            "slug": "ID del dispositivo",
            "tag": "Etiqueta",
            "location": "Ubicación",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "ej. Sensor de caudal"}),
            "slug": forms.TextInput(attrs={"placeholder": "ej. esp32-caudal"}),
            "tag": forms.TextInput(attrs={"placeholder": "ej. esp32"}),
            "location": forms.TextInput(attrs={"placeholder": "ej. Laboratorio, estanque 1"}),
        }


class WidgetForm(forms.ModelForm):
    class Meta:
        model = Widget
        fields = [
            "widget_type",
            "min_value",
            "max_value",
            "led_on_threshold",
            "button_on_value",
            "button_off_value",
            "slider_step",
            "setpoint_sensor",
            "featured",
            "position",
        ]
        labels = {
            "widget_type": "Tipo de gadget",
            "min_value": "Valor mínimo",
            "max_value": "Valor máximo",
            "led_on_threshold": "Umbral de encendido (LED)",
            "button_on_value": "Valor al encender (Botón)",
            "button_off_value": "Valor al apagar (Botón)",
            "slider_step": "Incremento (Slider)",
            "setpoint_sensor": "Sensor de consigna (Estanque)",
            "featured": "Mostrar en indicadores",
            "position": "Posición",
        }

    def __init__(self, *args, setpoint_sensors=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo se puede elegir como consigna un sensor que el usuario ya ve.
        if setpoint_sensors is not None:
            self.fields["setpoint_sensor"].queryset = setpoint_sensors


class UserCreateForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electrónico")
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, label="Rol")

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, creator_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        if creator_role != Profile.ROLE_GLOBAL:
            self.fields["role"].choices = [
                choice for choice in Profile.ROLE_CHOICES if choice[0] != Profile.ROLE_GLOBAL
            ]

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Profile.objects.update_or_create(user=user, defaults={"role": self.cleaned_data["role"]})
        return user


class ProfileBrandingForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["project_name", "logo", "background_image"]
        labels = {
            "project_name": "Nombre de tu proyecto/empresa",
            "logo": "Tu logo",
            "background_image": "Tu imagen de fondo",
        }
        widgets = {
            "project_name": forms.TextInput(attrs={"placeholder": "ej. Constructora Temuco Ltda."}),
        }


class SiteBrandingForm(forms.ModelForm):
    class Meta:
        model = SiteBranding
        fields = ["logo", "background_image", "map_icon"]
        labels = {
            "logo": "Logo de la plataforma (login y dashboard)",
            "background_image": "Imagen de fondo",
            "map_icon": "Ícono del mapa (exclusivo)",
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "product_type"]
        labels = {
            "name": "Nombre",
            "product_type": "Tipo",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "ej. Malla a tierra - Subestación Norte"}),
        }


class ManualEntryForm(forms.ModelForm):
    class Meta:
        model = ManualEntry
        fields = ["note", "variable", "value", "unit"]
        labels = {
            "note": "Nota",
            "variable": "Variable (opcional)",
            "value": "Valor (opcional)",
            "unit": "Unidad (opcional)",
        }
        widgets = {
            "note": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Ej. Medición trimestral con telurómetro: 4.2 Ω, dentro de norma."}
            ),
            "variable": forms.TextInput(attrs={"placeholder": "ej. resistencia_tierra"}),
            "unit": forms.TextInput(attrs={"placeholder": "ej. Ω"}),
        }


class ProductTypeIconForm(forms.ModelForm):
    class Meta:
        model = ProductType
        fields = ["icon"]
        labels = {"icon": ""}


class ProductIconForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["icon"]
        labels = {"icon": ""}
