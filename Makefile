DOCKER_COMPOSE_FILE = ./docker/docker-compose.yml

all: check_env load
	@echo "Starting containers..."
	docker compose -f $(DOCKER_COMPOSE_FILE) up -d

check_env:
	@echo "Checking environment variables..."
	chmod +x check_env.sh
	bash check_env.sh

build: check_env
	@echo "Building and starting containers..."
	docker compose -f $(DOCKER_COMPOSE_FILE) up --build -d

load:
	@docker load -i docker/images/docker-backend.tar
	@docker load -i docker/images/docker-blockchain.tar
	@docker load -i docker/images/docker-nginx.tar
	@docker load -i docker/images/postgres-15.4.tar
	@docker load -i docker/images/redis-7.0.tar	

down:
	@echo "Stopping containers..."
	docker compose -f $(DOCKER_COMPOSE_FILE) down

fclean: down
	docker system prune -f -a
	@if [ -n "$$(docker volume ls -q --filter dangling=true)" ]; then \
		docker volume rm $$(docker volume ls -q --filter dangling=true); \
	else \
		echo "No dangling volumes to remove."; \
	fi
	@echo "\033[93mAll the images have been deleted.\033[0m"

reset: down build
re: fclean build

.PHONY: all check_env build down clean fclean re
