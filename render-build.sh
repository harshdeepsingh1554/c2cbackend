#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install Python dependencies
# Make sure 'spacy', 'flask', and 'flask-cors' are in your requirements.txt
pip install --upgrade pip
pip install -r requirements.txt

# 2. Download the spaCy model used in your app.py
# Your code explicitly calls for "en_core_web_md"
python -m spacy download en_core_web_md

# 3. Install Chrome for Selenium
# This logic extracts Chrome into a persistent folder for Render
STORAGE_DIR=/opt/render/project/.render
if [ ! -d "$STORAGE_DIR/chrome" ]; then
  echo "...Downloading and Installing Chrome..."
  mkdir -p $STORAGE_DIR/chrome
  cd $STORAGE_DIR/chrome
  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  ar x google-chrome-stable_current_amd64.deb
  tar xvf data.tar.xz
  
  # Go back to the project root directory
  cd -
  echo "✅ Chrome installation complete."
else
  echo "✅ Chrome is already present in cache."
fi
