#!/bin/bash
set -e

# Configuration
CURRENT_USER=$(whoami)
DB_NAME=${DB_NAME:-"prism"}
DB_USER=${DB_USER:-"$CURRENT_USER"}
DB_PASS=${DB_PASS:-""} # Not needed for Peer auth
DB_HOST=${DB_HOST:-""} # Empty host uses Unix socket (required for Peer)

# Auto-detect port from /var/run/postgresql (useful if 5432 is taken by proxy)
DETECTED_PORT=$(ls /var/run/postgresql/.s.PGSQL.* 2>/dev/null | head -n 1 | sed 's/.*\.//')
DB_PORT=${DB_PORT:-${DETECTED_PORT:-"5432"}}

echo "========================================================"
echo "Prism Local PostgreSQL Setup (Port: $DB_PORT)"
echo "========================================================"

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo "Error: psql is not installed. Please run 'sudo apt-get install postgresql' first."
    exit 1
fi

echo "1. Creating database and user (requires sudo/postgres privileges)..."
# We use sudo -u postgres to run these commands
sudo -u postgres psql -p $DB_PORT -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "Database $DB_NAME already exists."
sudo -u postgres psql -p $DB_PORT -c "CREATE DATABASE ${DB_NAME}_test;" 2>/dev/null || echo "Database ${DB_NAME}_test already exists."
sudo -u postgres psql -p $DB_PORT -c "CREATE ROLE $DB_USER WITH LOGIN;" 2>/dev/null || echo "Role $DB_USER already exists."
if [[ -n "$DB_PASS" ]]; then
    sudo -u postgres psql -p $DB_PORT -c "ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASS';"
fi
sudo -u postgres psql -p $DB_PORT -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -p $DB_PORT -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME}_test TO $DB_USER;"

# Initialize both schemas
for DBN in "$DB_NAME" "${DB_NAME}_test"; do
    echo "Initializing schema for $DBN..."
    sudo -u postgres psql -p $DB_PORT -d "$DBN" -c "ALTER SCHEMA public OWNER TO $DB_USER;"
    sudo -u postgres psql -p $DB_PORT -d "$DBN" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
done

echo "Verifying connection..."
if [[ -z "$DB_HOST" ]]; then
    # Peer auth verification
    if ! sudo -u $DB_USER psql -p $DB_PORT -d $DB_NAME -c "SELECT 1;" &>/dev/null; then
        echo "Error: Peer connection failed for $DB_USER on port $DB_PORT."
        exit 1
    fi
else
    # Password auth verification
    if ! PGPASSWORD=$DB_PASS psql -p $DB_PORT -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;" &>/dev/null; then
        echo "Error: Password connection failed for $DB_USER on port $DB_PORT."
        exit 1
    fi
fi

echo "2. Updating .env file..."
DOTENV_FILE=".env"

if [[ -z "$DB_HOST" ]]; then
    NEW_DB_URL="postgresql:///$DB_NAME?host=/var/run/postgresql&port=$DB_PORT"
else
    NEW_DB_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
fi

# Use Python to safely update the .env file without overwriting other variables
python3 - <<EOF
import os

env_file = "$DOTENV_FILE"
new_values = {
    "DATABASE_URL": "$NEW_DB_URL",
    "PRISM_GENAI_CLIENT_LOCATION": "us-central1",
    "PRISM_GENAI_CLIENT_PROJECT": "",
    "PRISM_GDA_PROJECTS": ""
}

current_env = {}
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                current_env[key] = value

# Update only if not present or specifically requested (here we always update DB_URL)
for key, value in new_values.items():
    if key == "DATABASE_URL" or key not in current_env:
        current_env[key] = value

with open(env_file, "w") as f:
    for key, value in current_env.items():
        f.write(f"{key}={value}\n")
EOF

echo ".env file updated with local PostgreSQL configuration."

echo "3. Initializing database schema (Alembic)..."
UV_BIN="$HOME/.local/bin/uv"

if [[ -f "$UV_BIN" ]]; then
    echo "  > Running migrations via uv..."
    $UV_BIN run alembic upgrade head
else
    echo "  > Warning: uv not found at $UV_BIN. Skipping migrations."
fi

echo "========================================================"
echo "Setup Complete!"
echo "You can now run the app with: ./scripts/run_app.sh"
echo "========================================================"
