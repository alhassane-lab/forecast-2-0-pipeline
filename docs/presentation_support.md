# Support de presentation (plan conseille)

## Slide 1 - Contexte mission
- besoin metier
- sources de donnees
- objectifs qualite et disponibilite

## Slide 2 - Demarche technique
- collecte (Airbyte)
- transformation (scripts Python)
- stockage (MongoDB)
- tests et qualite

## Slide 3 - Architecture globale
- schema technique de bout en bout
- Airbyte -> S3 -> ETL -> MongoDB

## Slide 4 - Schema base MongoDB
- collection(s)
- champs clefs et index

## Slide 5 - Logigramme processus
- inserer `docs/process_flowchart.mmd` (ou export image)

## Slide 6 - Installation Airbyte (preuve)
- capture ecran UI Airbyte
- connexion JSON/Excel vers S3

## Slide 7 - Reporting qualite et performance
- taux d'erreurs post migration
- temps moyen d'accessibilite (requete MongoDB)

## Slide 8 - AWS installation (preuve)
- (optionnel) capture acces S3 / verification des fichiers bruts
- (optionnel) monitoring basique (logs pipeline)

## Slide 9 - Justification des choix
- pourquoi Airbyte
- pourquoi schema MongoDB cible
- choix d'indexation et de migration
