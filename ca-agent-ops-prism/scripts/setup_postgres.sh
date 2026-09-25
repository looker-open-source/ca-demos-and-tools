#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

cd "$(dirname "$0")/.."

CURRENT_USER=$(whoami)
DB_NAME=${DB_NAME:-"prism"}
DB_USER=${DB_USER:-"$CURRENT_USER"}
DB_PASS=${DB_PASS:-""}
DB_PORT=${DB_PORT:-"5432"}

usage() {
    echo "Usage: $(basename "$0") [--nuke] [--no-docker] [--sudo]"
    echo "  --nuke       drop the $DB_NAME and ${DB_NAME}_test databases first (asks)"
    echo "  --no-docker  use a PostgreSQL installed on the host"
    echo "  --sudo       run the docker commands under sudo"
}

USE_DOCKER=true
USE_SUDO_DOCKER=false
NUKE_DB=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --nuke) NUKE_DB=true ;;
        --no-docker) USE_DOCKER=false ;;
        --sudo) USE_SUDO_DOCKER=true ;;
        *)
            # Without this arm a typo'd flag was accepted and ignored, so
            # --nuk left the old databases in place and said nothing.
            echo "Error: unknown option '$1'."
            usage
            exit 1
            ;;
    esac
    shift
done

DOCKER_BIN="docker"
if [[ "$USE_SUDO_DOCKER" == true ]]; then
    DOCKER_BIN="sudo docker"
fi

OS_TYPE=$(uname -s)

# The migrations at the end run under uv. Check for it here, so the script
# cannot create the databases and then stop short of the schema.
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install it: https://astral.sh/uv"
    exit 1
fi

if [[ "$USE_DOCKER" == true ]]; then
    if ! command -v docker &> /dev/null; then
        echo "Error: docker is not installed. Please install docker or use --no-docker for local Postgres."
        exit 1
    fi
    echo "Using Dockerized Postgres..."
    CONTAINER_NAME="postgres_local"
    # A named volume, so the data lives outside the container. Several branches
    # below recreate the container, and a recreate is a `docker rm -f`, which
    # takes the writable layer with it. Without this every local database went
    # with it too.
    VOLUME_NAME="postgres_local_data"
    # Respect a DB_HOST the caller exported. Overwriting it sent the URLs
    # written into .env to localhost no matter what the caller asked for.
    DB_HOST=${DB_HOST:-"localhost"}
    # A placeholder, not a password. It is the same in every checkout, which
    # is only tolerable because the port below is bound to loopback. Set
    # DB_PASS to use your own, and never carry this value into a deployment.
    DB_PASS=${DB_PASS:-"CHANGEME-local-only"}

    # docker puts its arguments in `ps`, where any user on the machine can
    # read them, so the password goes in a file instead of in -e.
    PG_ENV_FILE=$(mktemp)
    trap 'rm -f "$PG_ENV_FILE"' EXIT
    printf 'POSTGRES_PASSWORD=%s\n' "$DB_PASS" > "$PG_ENV_FILE"

    # Poll rather than sleep a fixed five seconds: a cold pull takes longer
    # than that, and a container that is already up is ready at once. The
    # -h forces a TCP check, so the temporary server the image runs during
    # initdb, which listens on the socket only, does not read as ready.
    wait_for_postgres() {
        local deadline=$((SECONDS + 120))
        echo "Waiting for Postgres to be ready..."
        while (( SECONDS < deadline )); do
            if $DOCKER_BIN exec "$CONTAINER_NAME" \
                pg_isready -h 127.0.0.1 -U postgres -q; then
                return 0
            fi
            sleep 1
        done
        echo "Error: Postgres in $CONTAINER_NAME was not ready within 120s."
        exit 1
    }

    create_container() {
        $DOCKER_BIN run --pull=always \
            --env-file "$PG_ENV_FILE" \
            -v "$VOLUME_NAME:/var/lib/postgresql/data" \
            -p "127.0.0.1:${DB_PORT}:5432" --name "$CONTAINER_NAME" -d \
            postgres:17
    }

    # True when the existing container already keeps its data in the volume.
    # Anything created before the volume landed does not, so recreating it
    # destroys the databases.
    container_has_volume() {
        $DOCKER_BIN inspect \
            --format='{{range .Mounts}}{{.Name}} {{end}}' "$CONTAINER_NAME" \
            2>/dev/null | grep -qw "$VOLUME_NAME"
    }

    # Say what is about to happen, and ask first when it cannot be undone.
    recreate_container() {
        local reply=""
        if container_has_volume; then
            echo "Recreating $CONTAINER_NAME. Its databases are in the"
            echo "$VOLUME_NAME volume and survive this."
        else
            echo "Recreating $CONTAINER_NAME means removing it, and it predates"
            echo "the $VOLUME_NAME volume, so its databases do not come across."
            echo "The replacement starts empty. Dump anything you want to keep"
            echo "first:"
            echo "  $DOCKER_BIN exec $CONTAINER_NAME pg_dumpall -U postgres > dump.sql"
            read -r -p "Destroy the contents of $CONTAINER_NAME? [y/N] " reply || true
            if [[ "$reply" != [yY] ]]; then
                echo "Left $CONTAINER_NAME as it was. Nothing has changed."
                exit 1
            fi
        fi
        $DOCKER_BIN rm -f "$CONTAINER_NAME"
        create_container
    }

    if ! $DOCKER_BIN ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Creating and starting Docker container: $CONTAINER_NAME..."
        create_container
    else
        EXPOSED_PORT=$($DOCKER_BIN inspect --format='{{(index (index .HostConfig.PortBindings "5432/tcp") 0).HostPort}}' "$CONTAINER_NAME" 2>/dev/null || echo "")
        ACTIVE_PORT=$($DOCKER_BIN inspect --format='{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}' "$CONTAINER_NAME" 2>/dev/null || echo "")
        EXPOSED_IP=$($DOCKER_BIN inspect --format='{{(index (index .HostConfig.PortBindings "5432/tcp") 0).HostIp}}' "$CONTAINER_NAME" 2>/dev/null || echo "")

        # Containers created before this script bound to loopback are still on
        # every interface, with the default password. Say so rather than
        # recreating: a rebind is not urgent enough to do to someone's data
        # without asking, and this branch has no prompt.
        if [[ -n "$EXPOSED_PORT" && "$EXPOSED_IP" != "127.0.0.1" ]]; then
            echo "Warning: $CONTAINER_NAME publishes port $EXPOSED_PORT on all interfaces,"
            echo "so anyone who can reach this machine can reach the database."
            echo "To rebind it to localhost, remove it and re-run this script."
            echo "A container that predates the $VOLUME_NAME volume does not"
            echo "carry its databases across, so dump them before you do:"
            echo "  $DOCKER_BIN exec $CONTAINER_NAME pg_dumpall -U postgres > dump.sql"
            echo "  $DOCKER_BIN rm -f $CONTAINER_NAME"
        fi

        if [[ "$EXPOSED_PORT" != "$DB_PORT" ]]; then
            echo "Container exists but port mapping is incorrect ($EXPOSED_PORT != $DB_PORT)."
            recreate_container
        elif ! $DOCKER_BIN ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo "Starting existing Docker container: $CONTAINER_NAME..."
            $DOCKER_BIN start "$CONTAINER_NAME"
            wait_for_postgres

            ACTIVE_PORT=$($DOCKER_BIN inspect --format='{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}' "$CONTAINER_NAME" 2>/dev/null || echo "")
            if [[ -z "$ACTIVE_PORT" ]]; then
                echo "Container started but is not exposing ports correctly."
                recreate_container
            fi
        else
            if [[ -z "$ACTIVE_PORT" ]]; then
                echo "Container is running but not exposing ports correctly (zombie state)."
                recreate_container
            else
                echo "Docker container $CONTAINER_NAME is already running with correct ports."
            fi
        fi
    fi

    # Every branch above either created, recreated or started the container,
    # and one of them found it already up. All four have to be ready before
    # the first psql, so the wait lives here and not in each branch.
    wait_for_postgres

    # No -p. This psql runs inside the container, where the server always
    # listens on 5432. DB_PORT is the host side of the -p mapping above, so
    # passing it here breaks every superuser call whenever DB_PORT isn't 5432.
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
        PG_SUPER_CMD="psql -p $DB_PORT -d postgres"
        SOCKET_DIR="/tmp"
    else
        echo "Detected Linux..."
        PG_SUPER_CMD="sudo -u postgres psql -p $DB_PORT"
        SOCKET_DIR="/var/run/postgresql"
    fi
fi

# GNU sed (Linux) and BSD sed (macOS) disagree about -i.
safe_sed() {
    if [[ "$OS_TYPE" == "Darwin" ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# DB_NAME, DB_USER and DB_PASS come from the environment, and a role or
# database name is an identifier, which no client can bind as a parameter. So
# quote them the way PostgreSQL does, by doubling any quote inside the value,
# instead of splicing them in as they are.
sql_ident() {
    local escaped=${1//'"'/'""'}
    printf '"%s"' "$escaped"
}

sql_literal() {
    local escaped=${1//"'"/"''"}
    printf "'%s'" "$escaped"
}

# DB_USER and DB_PASS are spliced into the database URLs at the end. In a URL
# the characters :, @, /, ? and # all mean something, so a password holding one
# truncated the URL or moved the host. Percent-encode both instead. The client
# decodes them back on the way in.
url_encode() {
    local LC_ALL=C
    local string=$1
    local out="" i char encoded
    for ((i = 0; i < ${#string}; i++)); do
        char=${string:i:1}
        case "$char" in
            [a-zA-Z0-9.~_-])
                out+=$char
                ;;
            *)
                printf -v encoded '%%%02X' "'$char"
                out+=$encoded
                ;;
        esac
    done
    printf '%s' "$out"
}

# The URLs also go through safe_sed below, as the replacement half of an
# s|...|...| expression. sed reads & there as the whole match and \ as an
# escape, and | is the delimiter, so all three have to be escaped first.
sed_escape_replacement() {
    printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'
}

DB_NAME_IDENT=$(sql_ident "$DB_NAME")
DB_TEST_NAME_IDENT=$(sql_ident "${DB_NAME}_test")
DB_USER_IDENT=$(sql_ident "$DB_USER")
DB_USER_LITERAL=$(sql_literal "$DB_USER")

echo "========================================================"
echo "Prism Universal PostgreSQL Setup (Port: $DB_PORT)"
echo "========================================================"

echo "1. Configuring Database Roles and Schemas..."

# What PG_SUPER_CMD carries depends on the mode. On the Docker path it is a
# `docker exec` into the container, so it carries no port at all: psql runs
# beside the server, which always listens on 5432, and DB_PORT is only the host
# side of the mapping. On both host paths it is a local psql with -p "$DB_PORT".
# Neither form names a database, so pass -d when the statement needs one.
run_sql_as_super() {
    $PG_SUPER_CMD -c "$1"
}

if [ "$NUKE_DB" = true ]; then
    echo "--nuke drops the databases '$DB_NAME' and '${DB_NAME}_test'."
    echo "Everything in them goes, and there is no undo."
    NUKE_REPLY=""
    read -r -p "Drop both databases? [y/N] " NUKE_REPLY || true
    if [[ "$NUKE_REPLY" != [yY] ]]; then
        echo "Left the databases alone. Nothing has changed."
        exit 1
    fi
    echo "Nuking existing databases..."
    run_sql_as_super "DROP DATABASE IF EXISTS $DB_NAME_IDENT;"
    run_sql_as_super "DROP DATABASE IF EXISTS $DB_TEST_NAME_IDENT;"
fi

run_sql_as_super "
DO \$\$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = $DB_USER_LITERAL
    ) THEN
        CREATE ROLE $DB_USER_IDENT WITH LOGIN;
    END IF;
END
\$\$;"

# CREATEDB is for run_e2e.sh, which derives a <name>_e2e database from
# TEST_DATABASE_URL and creates it on first run. It connects as this role, and
# without the attribute PostgreSQL answers "permission denied to create
# database" and the browser tier cannot start. Set unconditionally, because the
# block above skips a role that already exists.
run_sql_as_super "ALTER ROLE $DB_USER_IDENT CREATEDB;"

# Set/Update Password if provided. This one goes in on stdin, not with -c:
# `ps` shows the arguments of a running command, so a password there is
# readable by every user on the machine. ON_ERROR_STOP because psql exits 0
# on a failed script read from stdin, and set -e would not see it.
if [[ -n "$DB_PASS" ]]; then
    printf 'ALTER ROLE %s WITH PASSWORD %s;\n' \
        "$DB_USER_IDENT" "$(sql_literal "$DB_PASS")" \
        | $PG_SUPER_CMD -v ON_ERROR_STOP=1 > /dev/null
fi

# Not run_sql_as_super, because "already exists" is the expected outcome on a
# re-run. It is the only failure that is not a failure, so read the message
# rather than discarding stderr and calling everything an existing database.
# A wrong password or a role with no rights used to print the same line and
# then fall over further down with no clue where it started.
create_database() {
    local ident=$1
    local name=$2
    local output
    local status=0

    output=$($PG_SUPER_CMD -c "CREATE DATABASE $ident OWNER $DB_USER_IDENT;" 2>&1) \
        || status=$?
    if [[ $status -eq 0 ]]; then
        echo "  > Created database '$name'."
        return 0
    fi
    if [[ "$output" == *"already exists"* ]]; then
        echo "  > Database '$name' already exists."
        return 0
    fi
    echo "Error: could not create database '$name'."
    echo "$output"
    exit 1
}

create_database "$DB_NAME_IDENT" "$DB_NAME"
create_database "$DB_TEST_NAME_IDENT" "${DB_NAME}_test"

echo "  > Granting privileges..."
run_sql_as_super "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_IDENT TO $DB_USER_IDENT;"
run_sql_as_super "GRANT ALL PRIVILEGES ON DATABASE $DB_TEST_NAME_IDENT TO $DB_USER_IDENT;"

for DBN in "$DB_NAME" "${DB_NAME}_test"; do
    $PG_SUPER_CMD -d "$DBN" -c "ALTER SCHEMA public OWNER TO $DB_USER_IDENT;" 2>/dev/null || true
    $PG_SUPER_CMD -d "$DBN" -c "GRANT ALL ON SCHEMA public TO $DB_USER_IDENT;" 2>/dev/null || true
done

echo "Verifying connection..."

if ! $PG_SUPER_CMD -d "$DB_NAME" -c "SELECT 1 as connected;" &>/dev/null; then
    echo "Error: Could not verify connection to '$DB_NAME' via superuser."
    exit 1
fi
echo "  > Internal connection (superuser) verified."

# In Docker mode the user connects from inside the container, so check that
# before the host-side connection below.
if [[ "$USE_DOCKER" == true ]]; then
    if ! $DOCKER_BIN exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
        echo "Error: Could not connect to container as user '$DB_USER'."
        exit 1
    fi
    echo "  > Container connection (user '$DB_USER') verified."
fi

if command -v psql &> /dev/null; then
    HOST_ARG=""
    if [[ -n "$DB_HOST" ]]; then
        HOST_ARG="-h $DB_HOST"
    fi

    if ! PGPASSWORD="$DB_PASS" psql -p "$DB_PORT" $HOST_ARG -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
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

echo "2. Updating .env file..."
DOTENV_FILE=".env"

DB_USER_ENC=$(url_encode "$DB_USER")
DB_PASS_ENC=$(url_encode "$DB_PASS")

# A socket directory is a path, and a path cannot go in the authority: the
# leading / closes the host and the rest of the URL stops parsing. Exporting
# DB_HOST=/var/run/postgresql wrote a DATABASE_URL nothing could open. libpq
# takes the directory as a host query parameter, so both socket cases produce
# the same ?host= form and only a network host goes in the authority.
if [[ "$DB_HOST" == /* ]]; then
    URL_AUTHORITY="localhost:$DB_PORT"
    URL_QUERY="?host=$DB_HOST"
elif [[ -n "$DB_HOST" ]]; then
    URL_AUTHORITY="$DB_HOST:$DB_PORT"
    URL_QUERY=""
else
    URL_AUTHORITY="localhost:$DB_PORT"
    URL_QUERY="?host=$SOCKET_DIR"
fi

NEW_DATABASE_URL="postgresql://$DB_USER_ENC:$DB_PASS_ENC@$URL_AUTHORITY/$DB_NAME$URL_QUERY"
NEW_TEST_DATABASE_URL="postgresql://$DB_USER_ENC:$DB_PASS_ENC@$URL_AUTHORITY/${DB_NAME}_test$URL_QUERY"

if [[ -f "$DOTENV_FILE" ]]; then
    echo "  > Updating existing $DOTENV_FILE..."
    cp "$DOTENV_FILE" "$DOTENV_FILE.bak"

    DATABASE_URL_SED=$(sed_escape_replacement "$NEW_DATABASE_URL")
    TEST_DATABASE_URL_SED=$(sed_escape_replacement "$NEW_TEST_DATABASE_URL")

    if grep -q "^DATABASE_URL=" "$DOTENV_FILE"; then
        safe_sed "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL_SED}|" "$DOTENV_FILE"
    else
        echo "DATABASE_URL=${NEW_DATABASE_URL}" >> "$DOTENV_FILE"
    fi

    if grep -q "^TEST_DATABASE_URL=" "$DOTENV_FILE"; then
        safe_sed "s|^TEST_DATABASE_URL=.*|TEST_DATABASE_URL=${TEST_DATABASE_URL_SED}|" "$DOTENV_FILE"
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

echo "3. Initializing database schema (Alembic)..."
echo "  > Running migrations via uv..."
uv run alembic upgrade head

echo "========================================================"
echo "Setup Complete!"
echo "========================================================"
