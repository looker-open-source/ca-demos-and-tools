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

# Reads .env into the environment. Source this, do not run it.
#
# The runners used to `source` .env under `set -o allexport`. A value in .env
# is literal text, but source hands it to the shell, so a backtick or a
# $(...) in a database password ran as a command. This parses the file line by
# line instead, and nothing in a value is expanded.
#
# A variable already in the environment wins, which is what python-dotenv does
# for the application, so PORT=9000 ./scripts/run_prod.sh still overrides the
# file.
load_dotenv() {
    local file=$1
    local line key value

    if [[ ! -f "$file" ]]; then
        return 0
    fi

    # The || on read picks up a last line with no trailing newline.
    while IFS= read -r line || [[ -n "$line" ]]; do
        line=${line#"${line%%[![:space:]]*}"}
        if [[ -z "$line" || "$line" == "#"* || "$line" != *=* ]]; then
            continue
        fi
        line=${line#export }
        key=${line%%=*}
        value=${line#*=}
        key=${key%"${key##*[![:space:]]}"}
        if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            continue
        fi
        # One layer of matching quotes comes off, as python-dotenv does it.
        # It also drops an inline comment, meaning whitespace then # to the end
        # of the line, from an unquoted value only. Without that, a
        # DB_NAME=prism  # local in .env set DB_NAME to "prism  # local" here
        # while the application read "prism", and the two tiers went to
        # different databases.
        if [[ "$value" =~ ^\"([^\"]*)\"[[:space:]]*(#.*)?$ ]]; then
            value=${BASH_REMATCH[1]}
        elif [[ "$value" =~ ^\'([^\']*)\'[[:space:]]*(#.*)?$ ]]; then
            value=${BASH_REMATCH[1]}
        else
            value=${value%%[[:space:]]#*}
            value=${value%"${value##*[![:space:]]}"}
        fi
        if [[ -n "${!key+set}" ]]; then
            continue
        fi
        export "$key=$value"
    done < "$file"
}
