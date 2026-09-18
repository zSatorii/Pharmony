#!/usr/bin/env bash
# Script de construcción para Render
set -o errexit

echo "==> Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Recopilando archivos estáticos..."
python manage.py collectstatic --no-input

echo "==> Aplicando migraciones de base de datos..."
python manage.py migrate

echo "==> Verificando / Creando superusuario..."
python manage.py crear_superusuario || echo "Aviso: No se pudo verificar o crear el superusuario automáticamente."

echo "==> Sincronizando datos desde Firebase Firestore..."
python manage.py sync_from_firestore || echo "Aviso: sync_from_firestore finalizó con advertencias o faltan credenciales temporales."

echo "==> Build finalizado con éxito."
