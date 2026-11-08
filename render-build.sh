#!/usr/bin/env bash
# Construction du site sur Render (appelé par render.yaml à chaque déploiement).
set -o errexit

pip install --upgrade pip
pip install -r backend/requirements.txt

cd backend
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Données de démonstration au premier déploiement seulement : les suivants
# gardent ce que les visiteurs ont publié, voté ou payé.
if python manage.py shell -c "import sys; from apps.deals.models import Deal; sys.exit(0 if Deal.objects.exists() else 1)"; then
    echo "Base déjà remplie : pas de nouvelles données de démonstration."
else
    python manage.py seed_demo
fi
python manage.py setup_roles
