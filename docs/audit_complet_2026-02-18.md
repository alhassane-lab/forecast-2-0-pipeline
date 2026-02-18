# Audit complet du projet - 18 fevrier 2026

## Perimetre

- Code Python ETL: `src/`
- Tests: `src/tests/`
- Runtime local: `Dockerfile`, `docker-compose*.yml`
- Infra AWS MongoDB: `infra/terraform/mongodb-ecs/`, `docker/mongodb-rs/`, `scripts/aws/`
- Documentation: `README.md`, `docs/`

## Resume executif

Le projet est globalement solide sur le pipeline ETL (code lisible, tests verts, flux de donnees clair) et dispose maintenant d'une base IaC pour MongoDB sur ECS.  
Les principaux risques se situent cote securite MongoDB et robustesse infra Terraform.

Points clefs:
- Les tests Python passent: `12 passed`.
- Replica set ECS 3 noeuds deployable (`rs0`) avec volumes EBS persistants.
- Risque critique: MongoDB fonctionne actuellement sans authentification active.
- Risque eleve: definition reseau Terraform incoherente pour le NAT.

## Constats detailles

### Critique

1. Auth MongoDB non active en runtime
- Preuve: message `Access control is not enabled for the database` observe dans `mongosh`/logs.
- Emplacement: `infra/terraform/mongodb-ecs/main.tf` (commande `mongod` sans `--auth` ni `--keyFile`), secret bootstrap non injecte dans le conteneur.
- Impact: acces non authentifie possible depuis le reseau autorise; secret root inutilise.
- Recommandation:
1. Injecter le secret ECS (`secrets` dans `container_definitions`).
2. Monter/creer un keyfile et lancer `mongod` avec `--auth --keyFile`.
3. Initialiser explicitement l'utilisateur admin puis verifier connexion authentifiee.

### Eleve

2. Topologie NAT/subnets a corriger
- Emplacement: `infra/terraform/mongodb-ecs/main.tf`.
- Constat: `private_subnet_ids` est utilise pour placer le NAT (`aws_nat_gateway.mongo.subnet_id`), alors qu'un NAT doit etre dans un subnet public.
- Impact: risque de routage sortant casse ou comportement non conforme selon le VPC cible.
- Recommandation:
1. Introduire une variable `public_subnet_id` dediee au NAT.
2. Garder les taches ECS sur subnets prives uniquement.

3. Variables Terraform ambiguës
- Emplacement: `infra/terraform/mongodb-ecs/variables.tf`.
- Constat: description de `private_subnet_ids` indique "Existing public subnet ids".
- Impact: forte probabilite d'erreur operateur.
- Recommandation: renommer/clarifier en `private_subnet_ids` + `public_subnet_id`.

### Moyen

4. Fichiers d'etat Terraform versionnes
- Emplacement: `infra/terraform/mongodb-ecs/terraform.tfstate`, `terraform.tfstate.backup`, `tfplan`.
- Impact: fuite potentielle de metadata sensible et conflits d'etat.
- Recommandation:
1. Passer sur backend distant (S3 + DynamoDB lock).
2. Ajouter ces fichiers au `.gitignore`.

5. Durcissement noyau manquant pour MongoDB
- Preuve: warning `vm.max_map_count is too low`.
- Impact: risque de perf/degradation selon charge.
- Recommandation: appliquer les prerequis kernel sur les hôtes ECS (ou valider les limites compatibles).

## Points positifs

- Couche ETL modulaire (extract/transform/validate/load) propre.
- Observabilite presente (logs structures + metriques EMF via `src/utils/monitoring.py`).
- Suite de tests existante et verte (`pytest -q src/tests` -> 12/12).
- Scripts d'ops utiles (`build_push_mongodb_rs_image.sh`, `deploy_mongodb_rs_terraform.sh`).

## Verification realisee

- `pytest -q src/tests`: OK, 12 tests passes.
- `terraform validate`: echec local de chargement plugins provider sur cette machine (probleme d'environnement/plugin), pas de validation semantique complete executable ici.

## Plan de remediations priorise

1. Activer l'auth MongoDB (`--auth`, keyfile, secret ECS) et retester `mongosh` avec credentials.
2. Corriger le design NAT/subnets Terraform (`public_subnet_id` explicite).
3. Sortir l'etat Terraform du repo (backend distant + nettoyage artefacts locaux).
4. Ajouter CI minimale: `pytest`, `terraform fmt -check`, `terraform validate` (en env propre).
