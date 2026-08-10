from django import forms
from .models import Turno


class SolicitarTurnoForm(forms.ModelForm):
    ciudad_envio = forms.ChoiceField(label='Ciudad de entrega', choices=[])

    class Meta:
        model = Turno
        fields = ['formula_medica', 'cedula_ciudadania', 'ciudad_envio', 'direccion_envio']
        widgets = {
            'formula_medica': forms.ClearableFileInput(attrs={'accept': '.pdf,.docx,.jpg,.jpeg,.png,.webp'}),
            'cedula_ciudadania': forms.ClearableFileInput(attrs={'accept': '.pdf,.docx,.jpg,.jpeg,.png,.webp'}),
            'direccion_envio': forms.TextInput(attrs={
                'placeholder': 'Calle, carrera, número, barrio...'
            }),
        }

    def __init__(self, *args, ciudades_permitidas=None, **kwargs):
        super().__init__(*args, **kwargs)
        ciudades_permitidas = ciudades_permitidas or []
        self.fields['ciudad_envio'].choices = [(c, c) for c in ciudades_permitidas]

    def clean_formula_medica(self):
        archivo = self.cleaned_data['formula_medica']
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('La fórmula médica no debe superar 5MB.')
        return archivo

    def clean_cedula_ciudadania(self):
        archivo = self.cleaned_data['cedula_ciudadania']
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('La cédula no debe superar 5MB.')
        return archivo