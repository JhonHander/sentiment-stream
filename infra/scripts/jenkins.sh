#!/usr/bin/env bash
# =============================================================================
# jenkins.sh — Helper script for Jenkins management
# =============================================================================
# Usage:
#   bash infra/scripts/jenkins.sh start    # Start Jenkins
#   bash infra/scripts/jenkins.sh stop     # Stop Jenkins
#   bash infra/scripts/jenkins.sh logs     # View Jenkins logs
#   bash infra/scripts/jenkins.sh password # Get initial admin password
#   bash infra/scripts/jenkins.sh status   # Check Jenkins status
# =============================================================================

set -euo pipefail

COMPOSE_FILE="infra/docker-compose.jenkins.yml"
PROJECT_NAME="sentiment-jenkins"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
header() { echo -e "${BLUE}=== $* ===${NC}"; }

case "${1:-help}" in
    start)
        header "Starting Jenkins"
        # Create jenkins_home directory on host if it doesn't exist (bind mount)
        mkdir -p infra/jenkins_home
        docker compose -f "$COMPOSE_FILE" up -d --build
        info "Jenkins is starting up..."
        info "Web UI: http://localhost:8082"
        info "Get password: bash infra/scripts/jenkins.sh password"
        ;;

    stop)
        header "Stopping Jenkins"
        docker compose -f "$COMPOSE_FILE" down
        info "Jenkins stopped."
        ;;

    restart)
        header "Restarting Jenkins"
        docker compose -f "$COMPOSE_FILE" restart
        info "Jenkins restarted."
        ;;

    logs)
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100
        ;;

    password)
        header "Initial Admin Password"
        docker compose -f "$COMPOSE_FILE" exec jenkins \
            cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || \
            warn "Jenkins may not be running yet. Try: bash infra/scripts/jenkins.sh start"
        ;;

    status)
        header "Jenkins Status"
        docker compose -f "$COMPOSE_FILE" ps
        echo ""
        if curl -sf http://localhost:8082/login >/dev/null 2>&1; then
            info "Jenkins is UP and running at http://localhost:8082"
        else
            warn "Jenkins is not responding on port 8082"
        fi
        ;;

    help|*)
        echo "Usage: bash infra/scripts/jenkins.sh {start|stop|restart|logs|password|status}"
        echo ""
        echo "Commands:"
        echo "  start     Build and start Jenkins"
        echo "  stop      Stop Jenkins"
        echo "  restart   Restart Jenkins"
        echo "  logs      Follow Jenkins logs"
        echo "  password  Get initial admin password"
        echo "  status    Check Jenkins status"
        ;;
esac
