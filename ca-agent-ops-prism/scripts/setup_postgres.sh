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

NUKE_DB=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --nuke) NUKE_DB=true ;;
    esac
    shift
done

# Detect OS to handle command differences
OS_TYPE=$(uname -s)

if [[ "$OS_TYPE" == "Darwin" ]]; then
    echo "Detected macOS..."
    # macOS/Homebrew: Current user is usually the superuser
    # We connect to 'postgres' database to perform admin tasks
    PG_SUPER_CMD="psql -d postgres"
    SOCKET_DIR="/tmp"  # Standard Homebrew socket location
else
    echo "Detected Linux..."
    # Linux: 'postgres' system user is the superuser
    PG_SUPER_CMD="sudo -u postgres psql"
    SOCKET_DIR="/var/run/postgresql" # Standard Linux socket location
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

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo "Error: psql is not installed."
    echo "  - macOS: brew install postgresql"
    echo "  - Linux: sudo apt-get install postgresql"
    exit 1
fi

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
# If DB_HOST is empty, we default to the detected socket directory
HOST_ARG=""
if [[ -n "$DB_HOST" ]]; then
    HOST_ARG="-h $DB_HOST"
fi

# Try connecting
if ! PGPASSWORD=$DB_PASS psql -p "$DB_PORT" $HOST_ARG -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1 as connected;" &>/dev/null; then
    echo "Warning: Could not connect as user '$DB_USER'. Trying to fix pg_hba.conf is beyond this script's scope."
    echo "Please ensure your pg_hba.conf allows local connections."
else 
    echo "  > Connection successful."
fi

# ==========================================
# 3. Update .env
# ==========================================

echo "2. Updating .env file..."
DOTENV_FILE=".env"

# Construct URL based on OS socket location or explicit host
if [[ -n "$DB_HOST" ]]; then
    # Network or explicit socket path
    NEW_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
else
    # Auto-detected local socket
    NEW_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/$DB_NAME?host=$SOCKET_DIR"
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
else
    echo "  > Creating new $DOTENV_FILE..."
    cat <<EOF > "$DOTENV_FILE"
DATABASE_URL=${NEW_DATABASE_URL}
PRISM_GENAI_CLIENT_LOCATION=us-central1
PRISM_GENAI_CLIENT_PROJECT=your-gcp-project-id
PRISM_GDA_PROJECTS=
EOF
fi

# ==========================================
# 4. Run Migrations
# ==========================================

echo "3. Initializing database schema (Alembic)..."
UV_BIN=$(command -v uv || echo "$HOME/.local/bin/uv")

if [[ -x "$UV_BIN" ]]; then
    echo "  > Running migrations via uv..."
    $UV_BIN run alembic upgrade head
else
    echo "  > Error: 'uv' not found. Please install uv to run migrations."
    echo "    See: https://github.com/astral-sh/uv"
    exit 1
fi

echo "========================================================"
echo "Setup Complete!"
echo "========================================================"
