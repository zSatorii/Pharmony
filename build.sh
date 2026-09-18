#!/usr/bin/env bash
set -o errexit

if [ -d "Pharmony" ]; then
  cd Pharmony
fi

./build.sh
