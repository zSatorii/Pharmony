from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Usuario
from epsinventario.models import Eps


class UsuarioAdminCreationForm(UserCreationForm):
    """
    Formulario para creación de usuarios en el Django Admin.
    Todos los campos son estrictamente obligatorios,
    excepto 'firebase_uid' y 'face_encoding'.
    """
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre(s)",
        help_text="Requerido. Ingresa el nombre del usuario."
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Apellido(s)",
        help_text="Requerido. Ingresa el apellido del usuario."
    )
    email = forms.EmailField(
        required=True,
        label="Correo Electrónico",
        help_text="Requerido. Correo único para notificaciones y acceso."
    )
    telefono = forms.CharField(
        max_length=20,
        required=True,
        label="Teléfono",
        help_text="Requerido. Número telefónico o móvil de contacto."
    )
    cedula = forms.CharField(
        max_length=20,
        required=True,
        label="Cédula / Documento",
        help_text="Requerido. Número de identificación oficial."
    )
    direccion = forms.CharField(
        max_length=200,
        required=True,
        label="Dirección",
        help_text="Requerido. Dirección de residencia o sede."
    )
    rol = forms.ChoiceField(
        choices=Usuario.ROLES,
        required=True,
        label="Rol",
        help_text="Requerido. Selecciona el rol asignado al usuario."
    )
    eps = forms.ModelChoiceField(
        queryset=Eps.objects.filter(estado=True),
        required=True,
        label="EPS Asignada",
        help_text="Requerido. Selecciona la entidad promotora de salud asociada."
    )
    firebase_uid = forms.CharField(
        max_length=255,
        required=False,
        label="Firebase UID",
        help_text="Opcional. Se genera automáticamente al sincronizar con Firebase."
    )
    face_encoding = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Face Encoding",
        help_text="Opcional. Vector biométrico facial registrado."
    )

    class Meta:
        model = Usuario
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'telefono',
            'cedula',
            'direccion',
            'rol',
            'eps',
            'firebase_uid',
            'face_encoding',
        )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("El correo electrónico es obligatorio.")
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo electrónico.")
        return email

    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula', '').strip()
        if not cedula:
            raise forms.ValidationError("El número de cédula/documento es obligatorio.")
        return cedula

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono', '').strip()
        if not telefono:
            raise forms.ValidationError("El teléfono de contacto es obligatorio.")
        return telefono

    def clean_direccion(self):
        direccion = self.cleaned_data.get('direccion', '').strip()
        if not direccion:
            raise forms.ValidationError("La dirección es obligatoria.")
        return direccion

    def clean_firebase_uid(self):
        uid = (self.cleaned_data.get('firebase_uid') or '').strip()
        return uid if uid else None

    def clean_face_encoding(self):
        fe = (self.cleaned_data.get('face_encoding') or '').strip()
        return fe if fe else None


class UsuarioAdminChangeForm(UserChangeForm):
    """
    Formulario para edición de usuarios en el Django Admin.
    Garantiza que todos los datos sigan siendo obligatorios excepto firebase_uid y face_encoding.
    """
    first_name = forms.CharField(max_length=150, required=True, label="Nombre(s)")
    last_name = forms.CharField(max_length=150, required=True, label="Apellido(s)")
    email = forms.EmailField(required=True, label="Correo Electrónico")
    telefono = forms.CharField(max_length=20, required=True, label="Teléfono")
    cedula = forms.CharField(max_length=20, required=True, label="Cédula / Documento")
    direccion = forms.CharField(max_length=200, required=True, label="Dirección")
    rol = forms.ChoiceField(choices=Usuario.ROLES, required=True, label="Rol")
    eps = forms.ModelChoiceField(queryset=Eps.objects.all(), required=True, label="EPS Asignada")
    firebase_uid = forms.CharField(max_length=255, required=False, label="Firebase UID")
    face_encoding = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label="Face Encoding")

    class Meta:
        model = Usuario
        fields = '__all__'

    def clean_firebase_uid(self):
        uid = (self.cleaned_data.get('firebase_uid') or '').strip()
        return uid if uid else None

    def clean_face_encoding(self):
        fe = (self.cleaned_data.get('face_encoding') or '').strip()
        return fe if fe else None

