import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

Usuario = get_user_model()

class Command(BaseCommand):
    help = "Crea o actualiza el superusuario/administrador a partir de variables de entorno (útil en Render)."

    def handle(self, *args, **options):
        username = (os.getenv('DJANGO_SUPERUSER_USERNAME') or 'admin').strip()
        email = (os.getenv('DJANGO_SUPERUSER_EMAIL') or 'admin@pharmony.local').strip()
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "==> [Aviso] DJANGO_SUPERUSER_PASSWORD no configurada en las variables de entorno. "
                    "Se omite la creación/actualización del superusuario."
                )
            )
            return

        user = Usuario.objects.filter(username=username).first()
        if not user:
            user = Usuario.objects.filter(email=email).first()

        if user:
            user.username = username
            user.email = email
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.rol = 'admin'
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"==> [OK] Superusuario '{username}' actualizado con contraseña y rol 'admin'.")
            )
        else:
            Usuario.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                rol='admin'
            )
            self.stdout.write(
                self.style.SUCCESS(f"==> [OK] Superusuario '{username}' creado exitosamente con rol 'admin'.")
            )
