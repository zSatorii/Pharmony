from django.db import migrations


def actualizar_roles(apps, schema_editor):
    Usuario = apps.get_model('Farmacia', 'Usuario')
    Usuario.objects.filter(rol='farmaceutico').update(rol='eps')


def revertir_roles(apps, schema_editor):
    Usuario = apps.get_model('Farmacia', 'Usuario')
    Usuario.objects.filter(rol='eps').update(rol='farmaceutico')


class Migration(migrations.Migration):

    dependencies = [
        ('Farmacia', '0004_alter_usuario_rol'),
    ]

    operations = [
        migrations.RunPython(actualizar_roles, revertir_roles),
    ]