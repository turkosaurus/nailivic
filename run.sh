#!/usr/bin/env bash

if ! apt install python3-pip -y; then
  echo "Error installing pip"
  exit 1
fi

if ! pip install -r requirements.txt; then
  echo "Error installing requirements.txt"
  exit 2
fi
