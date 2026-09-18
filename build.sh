#!/usr/bin/env bash
set -o errexit

if [ -d "Pharmony" ]; then
  cd Pharmony
fi

python manage.py createsuperuser --noinput || true
./build.sh
