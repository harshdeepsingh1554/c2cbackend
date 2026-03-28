# render-build.sh
#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install Chrome for Selenium
STORAGE_DIR=/opt/render/project/.render
if [ ! -d "$STORAGE_DIR/chrome" ]; then
  mkdir -p $STORAGE_DIR/chrome
  cd $STORAGE_DIR/chrome
  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  ar x google-chrome-stable_current_amd64.deb
  tar xvf data.tar.xz
fi