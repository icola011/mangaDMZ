#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python << END
from app import app, db
with app.app_context():
    db.create_all()
END
