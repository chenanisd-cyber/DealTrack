# Raccourcis de développement. `make` seul affiche l'aide.

.DEFAULT_GOAL := help
.PHONY: help install migrate seed run test lint format demo audit dict postman i18n clean reset

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Installe les dépendances
	pip install -r backend/requirements.txt
	pip install ruff polib

migrate:  ## Applique les migrations
	cd backend && python3 manage.py migrate

seed:  ## Charge le jeu de données de démonstration
	cd backend && python3 manage.py seed_demo

run:  ## Lance le serveur de développement
	cd backend && python3 manage.py runserver

test:  ## Exécute les 162 tests
	cd backend && python3 manage.py test tests --settings=config.settings.test

lint:  ## Analyse statique
	ruff check .

format:  ## Reformate le code
	ruff format .
	ruff check --fix .

demo:  ## Démonstration API en direct (serveur requis)
	python3 backend/scripts/api_demo.py

softdelete:  ## Démonstration de la suppression logique
	cd backend && python3 manage.py demo_soft_delete --anonymise

audit:  ## Rapport d'audit d'activité
	cd backend && python3 manage.py audit_report --days 30

dict:  ## Régénère le dictionnaire de données
	cd backend && python3 manage.py data_dictionary > ../database/DATA_DICTIONARY.md

postman:  ## Régénère la collection Postman
	python3 backend/scripts/build_postman.py

i18n:  ## Extrait et compile les traductions
	python3 backend/manage.py makemessages -l nl -l de -i ".venv/*" -i "staticfiles/*" -i "backend/scripts/*"
	python3 backend/scripts/apply_translations.py

clean:  ## Supprime les fichiers temporaires
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .ruff_cache .coverage htmlcov

reset:  ## Base vierge + données de démonstration
	rm -f database/db.sqlite3
	$(MAKE) migrate seed
