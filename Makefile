# Shortcuts for the Docker setups. See docs/DEPLOYMENT.md ("Run with Docker").
PROD  = docker compose -f docker-compose.prod.yml
LOCAL = docker compose -f docker-compose.prod.yml -f docker-compose.localdb.yml

.PHONY: dev prod prod-local kb-load kb-load-local logs down

dev:        ## development stack (hot reload, local db on :5432)
	docker compose up --build

prod:       ## production stack against the database in backend/.env (Supabase)
	$(PROD) up -d --build

prod-local: ## production stack with its own local Postgres (demo)
	$(LOCAL) up -d --build

kb-load:    ## load the college knowledge base into the database in backend/.env
	$(PROD) --profile tools run --rm kb-load

kb-load-local: ## load the knowledge base into the prod-local database
	$(LOCAL) --profile tools run --rm kb-load

logs:       ## follow prod logs
	$(LOCAL) logs -f --tail=100

down:       ## stop the prod stack (keeps volumes)
	$(LOCAL) down
