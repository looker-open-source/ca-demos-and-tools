#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

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
    NEW_DATABASE_URL="postgresql:///$DB_NAME?host=/var/run/postgresql&port=$DB_PORT"
else
    NEW_DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
fi

if [[ -f "$DOTENV_FILE" ]]; then
    echo "Updating existing $DOTENV_FILE..."
    # Backup
    cp "$DOTENV_FILE" "$DOTENV_FILE.bak"
    
    # Update or append DATABASE_URL
    if grep -q "^DATABASE_URL=" "$DOTENV_FILE"; then
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${NEW_DATABASE_URL}|" "$DOTENV_FILE"
    else
        echo "DATABASE_URL=${NEW_DATABASE_URL}" >> "$DOTENV_FILE"
    fi
else
    echo "Creating new $DOTENV_FILE..."
    cat <<EOF > "$DOTENV_FILE"
DATABASE_URL=${NEW_DATABASE_URL}
PRISM_VERTEX_LOCATION=global
PRISM_VERTEX_PROJECT=your-gcp-project-id
PRISM_GDA_PROJECTS=
EOF
fi
echo ".env file updated with local PostgreSQL configuration."

echo "3. Initializing database schema (Alembic)..."
VENV_PATH="$HOME/prism_venv"
if [[ -f "$VENV_PATH/bin/activate" ]]; then
    source "$VENV_PATH/bin/activate"
elif [[ -f "prism_venv/bin/activate" ]]; then
    source "prism_venv/bin/activate"
fi

if [[ -n "$VIRTUAL_ENV" ]]; then
    echo "Using virtual environment at $VIRTUAL_ENV"
    alembic upgrade head
else
    echo "Warning: Virtual environment not found. Please run migrations manually."
fi

echo "========================================================"
echo "Setup Complete!"
echo "========================================================"
