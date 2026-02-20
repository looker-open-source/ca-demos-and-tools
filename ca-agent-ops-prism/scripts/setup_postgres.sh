#!/bin/bash
set -e

# ==========================================
# 0. Environment & OS Detection
# ==========================================

# Ensure we are in the project root
cd "$(dirname "$0")/.."

CURRENT_USER=$(whoami)
DB_NAME=${DB_NAME:-"prism"}
DB_USER=${DB_USER:-"$CURRENT_USER"}
DB_PASS=${DB_PASS:-""} 
DB_PORT=${DB_PORT:-"5432"}

USE_DOCKER=true
USE_SUDO_DOCKER=false
NUKE_DB=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --nuke) NUKE_DB=true ;;
        --no-docker) USE_DOCKER=false ;;
        --sudo) USE_SUDO_DOCKER=true ;;
    esac
    shift
done

DOCKER_BIN="docker"
if [[ "$USE_SUDO_DOCKER" == true ]]; then
    DOCKER_BIN="sudo docker"
fi

# Detect OS to handle command differences
OS_TYPE=$(uname -s)

if [[ "$USE_DOCKER" == true ]]; then
    if ! command -v docker &> /dev/null; then
        echo "Error: docker is not installed. Please install docker or use --no-docker for local Postgres."
        exit 1
    fi
    echo "Using Dockerized Postgres..."
    CONTAINER_NAME="postgres_local"
    DB_HOST="localhost"
    DB_PASS="mysecretpassword"
    
    # Check if container exists
    if ! $DOCKER_BIN ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Creating and starting Docker container: $CONTAINER_NAME..."
        $DOCKER_BIN run --pull=always \
            -e "POSTGRES_PASSWORD=$DB_PASS" \
            -p "${DB_PORT}:5432" --name "$CONTAINER_NAME" -d \
            postgres:latest
        
        # Give it a moment to start up
        echo "Waiting for Postgres to be ready..."
        sleep 5
    elif ! $DOCKER_BIN ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Starting existing Docker container: $CONTAINER_NAME..."
        $DOCKER_BIN start "$CONTAINER_NAME"
        sleep 2
    else
        echo "Docker container $CONTAINER_NAME is already running."
    fi

    PG_SUPER_CMD="$DOCKER_BIN exec -i $CONTAINER_NAME psql -U postgres"
    SOCKET_DIR="" # Not used for Docker
else
    # Non-Docker mode requires psql on the host
    if ! command -v psql &> /dev/null; then
        echo "Error: psql is not installed. Please install it to use local Postgres."
        if [[ "$(uname -s)" == "Darwin" ]]; then
            echo "Try: brew install postgresql"
        else
            echo "Try: sudo apt-get install postgresql"
        fi
        exit 1
    fi

    if [[ "$OS_TYPE" == "Darwin" ]]; then
        echo "Detected macOS..."
        PG_SUPER_CMD="psql -d postgres"
        SOCKET_DIR="/tmp"
    else
        echo "Detected Linux..."
        PG_SUPER_CMD="sudo -u postgres psql"
        SOCKET_DIR="/var/run/postgresql"
    fi
fi

# Override SOCKET_DIR if DB_HOST is set manually to a file path
if [[ -n "$DB_HOST" && "$DB_HOST" == /* ]]; then
    SOCKET_DIR="$DB_HOST"
fi

# Function to handle 'sed' differences between GNU (Linux) and BSD (macOS)
safe_sed() {
    if [[ "$OS_TYPE" == "Darwin" ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

echo "========================================================"
echo "Prism Universal PostgreSQL Setup (Port: $DB_PORT)"
echo "========================================================"


# ==========================================
# 1. Database & User Creation (Idempotent)
# ==========================================

echo "1. Configuring Database Roles and Schemas..."

# Helper function to run SQL as superuser
run_sql_as_super() {
    $PG_SUPER_CMD -p "$DB_PORT" -c "$1"
}

# Nuke existing databases if requested
if [ "$NUKE_DB" = true ]; then
    echo "Nuking existing databases..."
    run_sql_as_super "DROP DATABASE IF EXISTS \"$DB_NAME\";"
    run_sql_as_super "DROP DATABASE IF EXISTS \"${DB_NAME}_test\";"
fi

# Create User (Idempotent: Checks if role exists first)
run_sql_as_super "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE ROLE \"$DB_USER\" WITH LOGIN;
    END IF;
END
\$\$;"

# Set/Update Password if provided
if [[ -n "$DB_PASS" ]]; then
    run_sql_as_super "ALTER ROLE \"$DB_USER\" WITH PASSWORD '$DB_PASS';"
fi

# Create Databases (Idempotent: catch error if exists)
# We suppress stderr here because CREATE DATABASE cannot run inside a DO block transaction
$PG_SUPER_CMD -p "$DB_PORT" -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";" 2>/dev/null || echo "  > Database '$DB_NAME' already exists or could not be created."
$PG_SUPER_CMD -p "$DB_PORT" -c "CREATE DATABASE \"${DB_NAME}_test\" OWNER \"$DB_USER\";" 2>/dev/null || echo "  > Database '${DB_NAME}_test' already exists or could not be created."

# Grant Privileges
echo "  > Granting privileges..."
run_sql_as_super "GRANT ALL PRIVILEGES ON DATABASE \"$DB_NAME\" TO \"$DB_USER\";"
run_sql_as_super "GRANT ALL PRIVILEGES ON DATABASE \"${DB_NAME}_test\" TO \"$DB_USER\";"

# Schema Permissions
for DBN in "$DB_NAME" "${DB_NAME}_test"; do
    # We allow this to fail silently if the DB doesn't exist (though it should)
    $PG_SUPER_CMD -p "$DB_PORT" -d "$DBN" -c "ALTER SCHEMA public OWNER TO \"$DB_USER\";" 2>/dev/null || true
    $PG_SUPER_CMD -p "$DB_PORT" -d "$DBN" -c "GRANT ALL ON SCHEMA public TO \"$DB_USER\";" 2>/dev/null || true
done

# ==========================================
# 2. Connection Verification
# ==========================================

echo "Verifying connection..."

# Internal check (via superuser command)
if ! $PG_SUPER_CMD -d "$DB_NAME" -c "SELECT 1 as connected;" &>/dev/null; then
    echo "Error: Could not verify connection to '$DB_NAME' via superuser."
    exit 1
fi
echo "  > Internal connection (superuser) verified."

# External check (via user connection)
if [[ "$USE_DOCKER" == true ]]; then
    # In Docker mode, verify we can connect *into* the container as the user
    if ! $DOCKER_BIN exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
        echo "Error: Could not connect to container as user '$DB_USER'."
        exit 1
    fi
     echo "  > Container connection (user '$DB_USER') verified."
fi

# Host-side check (Optional: only if psql is installed on host)
if command -v psql &> /dev/null; then
    HOST_ARG=""
    if [[ -n "$DB_HOST" ]]; then
        HOST_ARG="-h $DB_HOST"
    fi

    if ! PGPASSWORD=$DB_PASS psql -p "$DB_PORT" $HOST_ARG -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
        echo "Warning: Could not connect from host as user '$DB_USER'."
        if [[ "$USE_DOCKER" == true ]]; then
             echo "This is likely because the container's port $DB_PORT is not accessible from the host,"
             echo "but internal setup succeeded. Check your local firewall/VPN."
        else
            echo "Check your pg_hba.conf and local Postgres connectivity."
        fi
    else 
        echo "  > Host-side connection verified."
    fi
else
    echo "  > Skipping host-side verification (psql not installed on host)."
fi

# ==========================================
# 3. Update .env
# ==========================================

echo "2. Updating .env file..."
DOTENV_FILE=".env"

# Construct URLs based on OS socket location or explicit host
if [[ -n "$DB_HOST" ]]; then
    # Network or explicit socket path
    NEW_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
    NEW_TEST_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/${DB_NAME}_test"
else
    # Auto-detected local socket
    NEW_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/$DB_NAME?host=$SOCKET_DIR"
    NEW_TEST_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/${DB_NAME}_test?host=$SOCKET_DIR"
fi

if [[ -f "$DOTENV_FILE" ]]; then
    echo "  > Updating existing $DOTENV_FILE..."
    # Backup
    cp "$DOTENV_FILE" "$DOTENV_FILE.bak"
    
    # Update or append DATABASE_URL using the safe_sed function
    if grep -q "^DATABASE_URL=" "$DOTENV_FILE"; then
        safe_sed "s|^DATABASE_URL=.*|DATABASE_URL=${NEW_DATABASE_URL}|" "$DOTENV_FILE"
    else
        echo "DATABASE_URL=${NEW_DATABASE_URL}" >> "$DOTENV_FILE"
    fi

    # Update or append TEST_DATABASE_URL
    if grep -q "^TEST_DATABASE_URL=" "$DOTENV_FILE"; then
        safe_sed "s|^TEST_DATABASE_URL=.*|TEST_DATABASE_URL=${NEW_TEST_DATABASE_URL}|" "$DOTENV_FILE"
    else
        echo "TEST_DATABASE_URL=${NEW_TEST_DATABASE_URL}" >> "$DOTENV_FILE"
    fi
else
    echo "  > Creating new $DOTENV_FILE..."
    cat <<EOF > "$DOTENV_FILE"
DATABASE_URL=${NEW_DATABASE_URL}
TEST_DATABASE_URL=${NEW_TEST_DATABASE_URL}
PRISM_GENAI_CLIENT_LOCATION=us-central1
PRISM_GENAI_CLIENT_PROJECT=your-gcp-project-id
PRISM_GDA_PROJECTS=
EOF
fi

# ==========================================
# 4. Run Migrations
# ==========================================

echo "3. Initializing database schema (Alembic)..."
echo "  > Running migrations via uv..."
uv run alembic upgrade head

echo "========================================================"
echo "Setup Complete!"
echo "========================================================"
