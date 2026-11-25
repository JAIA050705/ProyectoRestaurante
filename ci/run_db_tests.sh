#!/usr/bin/env bash
# Runs the database state tests against a MySQL server and fails (exit 1)
# if any of them fails. Used by the GitLab pipeline, but it also works on a
# laptop with the mysql client installed.
#
# Needed environment variables:
#   MYSQL_HOST          host of the server            (default: 127.0.0.1)
#   MYSQL_ROOT_PASSWORD password of the root user
# Optional:
#   SCHEMA_FILE         path of the schema script     (default: database/restaurant_review_schema.sql)
set -euo pipefail

HOST="${MYSQL_HOST:-127.0.0.1}"
SCHEMA_FILE="${SCHEMA_FILE:-database/restaurant_review_schema.sql}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/db-tests"

mysql_run() { mysql --host="$HOST" --user=root --password="$MYSQL_ROOT_PASSWORD" "$@"; }

echo "== Loading schema and sample data"
mysql_run < "$SCHEMA_FILE"

echo "== Test 1: empty tables"
mysql_run < "$DIR/01_empty_tables.sql"
EMPTY_ROWS=$(mysql_run -N -e "SELECT (SELECT COUNT(*) FROM restaurant_review_db.users) + (SELECT COUNT(*) FROM restaurant_review_db.restaurants) + (SELECT COUNT(*) FROM restaurant_review_db.reviews) + (SELECT COUNT(*) FROM restaurant_review_db.favorites)")
if [ "$EMPTY_ROWS" != "0" ]; then
    echo "FAIL: the tables are not empty ($EMPTY_ROWS rows left)"; exit 1
fi
echo "PASS: all tables are empty"

echo "== Test 2: edge cases and constraints"
mysql_run < "$DIR/02_edge_cases.sql"
FAILED=$(mysql_run -N -e "SELECT COUNT(*) FROM restaurant_review_db.qa_results WHERE result = 'FAIL'")
TOTAL=$(mysql_run -N -e "SELECT COUNT(*) FROM restaurant_review_db.qa_results")
mysql_run -e "SELECT test_name, result FROM restaurant_review_db.qa_results ORDER BY test_number"
if [ "$TOTAL" = "0" ] || [ "$FAILED" != "0" ]; then
    echo "FAIL: $FAILED of $TOTAL constraint tests failed"; exit 1
fi
echo "PASS: $TOTAL of $TOTAL constraint tests passed"

echo "== Test 3: massive data"
mysql_run < "$DIR/03_massive_data.sql"
REVIEWS=$(mysql_run -N -e "SELECT COUNT(*) FROM restaurant_review_db.reviews WHERE comment LIKE 'Load test review %'")
if [ "$REVIEWS" != "25000" ]; then
    echo "FAIL: expected 25000 load reviews, found $REVIEWS"; exit 1
fi
echo "PASS: 25000 reviews loaded"

echo "== Cleaning up and restoring the sample data"
mysql_run < "$DIR/04_cleanup_test_data.sql"
mysql_run < "$SCHEMA_FILE"
echo "All database tests passed"
