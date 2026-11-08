# Sources des diagrammes UML

Les diagrammes sont écrits sous forme de code (« diagram as code »), sans outil
externe : `svg.py` dessine les formes UML, chaque script produit un fichier SVG
dans `docs/uml/`.

```bash
cd docs/uml/source
python usecase.py   # 01_cas_utilisation.svg
python classes.py   # 02_classes.svg
python states.py    # 03_etats_deal.svg, 04_etats_paiement.svg, 05_etats_compte.svg
```

Le diagramme de classes reprend les modèles Django (`backend/apps/*/models.py`) ;
à modifier ici si un modèle change.
