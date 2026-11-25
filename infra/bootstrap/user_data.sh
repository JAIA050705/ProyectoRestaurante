#!/bin/bash
# =====================================================================
# Runs ONCE, as root, when the EC2 instance boots for the first time.
# deploy.py fills in the bucket, region and versions before sending it to AWS.
# Everything it prints goes to /var/log/rr-bootstrap.log
# =====================================================================
set -euxo pipefail
exec > >(tee -a /var/log/rr-bootstrap.log) 2>&1

BUCKET="@@BUCKET@@"
REGION="@@REGION@@"
PARAM_PREFIX="@@PARAM_PREFIX@@"
GF_VERSION="@@GF_VERSION@@"
CONNECTOR_VERSION="@@CONNECTOR_VERSION@@"
CONTEXT="@@CONTEXT@@"
export AWS_DEFAULT_REGION="$REGION"

echo "== 1. Swap (safety net for a 2 GB machine)"
if [ ! -f /swapfile ]; then
    dd if=/dev/zero of=/swapfile bs=1M count=1024
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== 2. Packages"
dnf -y install java-25-amazon-corretto-headless docker nginx unzip
systemctl enable --now docker

echo "== 3. Secrets from Parameter Store (never written in the code)"
get_param() {
    aws ssm get-parameter --name "$PARAM_PREFIX/$1" --with-decryption \
        --query Parameter.Value --output text
}
DB_PASSWORD="$(get_param db_password)"
DB_ROOT_PASSWORD="$(get_param db_root_password)"
JWT_SECRET="$(get_param jwt_secret)"

echo "== 4. Data disk for MySQL"
ROOT_SRC="$(findmnt -n -o SOURCE /)"
ROOT_DISK="/dev/$(lsblk -no pkname "$ROOT_SRC" | head -n1)"
DATA_DISK="$(lsblk -dpno NAME,TYPE | awk '$2=="disk"{print $1}' | grep -v "^${ROOT_DISK}$" | head -n1)"
mkdir -p /data/mysql
if [ -n "$DATA_DISK" ]; then
    if ! blkid "$DATA_DISK" >/dev/null 2>&1; then
        mkfs -t xfs "$DATA_DISK"
    fi
    DATA_UUID="$(blkid -s UUID -o value "$DATA_DISK")"
    echo "UUID=$DATA_UUID /data xfs defaults,nofail 0 2" >> /etc/fstab
    mkdir -p /data
    mount /data
    mkdir -p /data/mysql
fi

echo "== 5. MySQL 8.4 in Docker (restarts by itself)"
mkdir -p /etc/rr /var/lib/rr
umask 077
cat > /etc/rr/mysql.env <<ENVEOF
MYSQL_ROOT_PASSWORD=$DB_ROOT_PASSWORD
MYSQL_DATABASE=restaurant_review_db
MYSQL_USER=dev
MYSQL_PASSWORD=$DB_PASSWORD
ENVEOF
umask 022
docker run -d --name rr-mysql --restart unless-stopped \
    --env-file /etc/rr/mysql.env \
    -p 127.0.0.1:3306:3306 \
    -v /data/mysql:/var/lib/mysql \
    mysql:8.4

echo "waiting for MySQL..."
# The first start of the MySQL image runs a temporary server that only listens on
# a socket and then restarts. A ping over the socket succeeds too early, so we
# ping over TCP (only the final server listens there) and need 3 answers in a row.
ok=0
for i in $(seq 1 120); do
    if docker exec rr-mysql sh -c 'mysqladmin ping -h127.0.0.1 -P3306 -uroot -p"$MYSQL_ROOT_PASSWORD" --silent' >/dev/null 2>&1; then
        ok=$((ok + 1))
        [ "$ok" -ge 3 ] && break
    else
        ok=0
    fi
    sleep 3
done
if [ "$ok" -lt 3 ]; then
    echo "MySQL did not become ready"; docker logs --tail 50 rr-mysql; exit 1
fi

echo "== 6. Load the data: last backup if there is one, otherwise the schema"
if aws s3 ls "s3://$BUCKET/backups/latest.sql.gz" >/dev/null 2>&1; then
    echo "restoring the latest backup"
    aws s3 cp "s3://$BUCKET/backups/latest.sql.gz" - | gunzip \
        | docker exec -i rr-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
else
    echo "no backup found: loading the schema and the sample data"
    aws s3 cp "s3://$BUCKET/db/schema.sql" - \
        | docker exec -i rr-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
fi

echo "== 7. GlassFish $GF_VERSION"
curl -fSL "https://repo1.maven.org/maven2/org/glassfish/main/distributions/glassfish/$GF_VERSION/glassfish-$GF_VERSION.zip" \
    -o /tmp/glassfish.zip
unzip -q /tmp/glassfish.zip -d /opt
GF_DIR="$(find /opt -maxdepth 1 -type d -name 'glassfish*' | head -n1)"
ln -sfn "$GF_DIR" /opt/glassfish
# Safety net: the JDBC driver in the server too (same version that the WAR should carry)
curl -fSL "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/$CONNECTOR_VERSION/mysql-connector-j-$CONNECTOR_VERSION.jar" \
    -o "/opt/glassfish/glassfish/domains/domain1/lib/mysql-connector-j.jar"
useradd -r -m -d /home/glassfish glassfish || true
chown -R glassfish:glassfish "$GF_DIR"

umask 077
cat > /etc/rr/app.env <<ENVEOF
DB_URL=jdbc:mysql://127.0.0.1:3306/restaurant_review_db?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
DB_USER=dev
DB_PASSWORD=$DB_PASSWORD
JWT_SECRET=$JWT_SECRET
ENVEOF
umask 022

cat > /etc/systemd/system/glassfish.service <<'UNITEOF'
[Unit]
Description=GlassFish application server
After=network.target docker.service

[Service]
User=glassfish
EnvironmentFile=/etc/rr/app.env
ExecStart=/opt/glassfish/bin/asadmin start-domain --verbose domain1
ExecStop=/opt/glassfish/bin/asadmin stop-domain domain1
Restart=always
RestartSec=5
LimitNOFILE=65536
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
UNITEOF

echo "== 8. nginx in front (port 80 -> GlassFish 8080)"
cat > /etc/nginx/nginx.conf <<'NGINXEOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /var/log/nginx/access.log;
    sendfile on;
    server_tokens off;
    gzip on;
    gzip_types text/css application/javascript application/json;

    # at most 5 login attempts per second per address (slows down password guessing)
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/s;

    server {
        listen 80 default_server;
        server_name _;
        client_max_body_size 2m;

        location = / { return 302 /@@CONTEXT@@/; }

        location = /@@CONTEXT@@/api/auth/login {
            limit_req zone=login burst=10 nodelay;
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 60s;
        }
    }
}
NGINXEOF

echo "== 9. WAR deployer: checks Parameter Store every minute and deploys a new WAR"
cat > /usr/local/bin/rr-deploy-war <<'DEPLOYEOF'
#!/bin/bash
# Deploys the WAR named in the parameter war_key when it is not the one already running.
# Protections: (1) a file that is not a WAR is rejected before touching the running app,
# (2) if GlassFish cannot deploy the new WAR, the previous one is deployed again.
# Rollback by hand = point war_key to an older WAR. No SSH needed.
set -uo pipefail
export AWS_DEFAULT_REGION="@@REGION@@"
BUCKET="@@BUCKET@@"
STATE=/var/lib/rr
log() { echo "$(date -u +%FT%TZ) $*"; }

KEY="$(aws ssm get-parameter --name "@@PARAM_PREFIX@@/war_key" --query Parameter.Value --output text)" || exit 0
CURRENT="$(cat $STATE/current_war_key 2>/dev/null || true)"
REJECTED="$(cat $STATE/rejected_war_key 2>/dev/null || true)"
[ "$KEY" = "$CURRENT" ] && exit 0
[ "$KEY" = "$REJECTED" ] && exit 0

# GlassFish may still be starting: wait for the next run instead of judging the WAR
if ! runuser -u glassfish -- /opt/glassfish/bin/asadmin list-applications >/dev/null 2>&1; then
    log "GlassFish is not ready yet, will retry"; exit 1
fi

# returns 10 = download failed, 11 = not a valid WAR, 12 = GlassFish could not deploy it
deploy_key() {
    local file=/tmp/rr-candidate.war
    aws s3 cp "s3://$BUCKET/$1" "$file" || return 10
    if ! unzip -tqq "$file" >/dev/null 2>&1 || ! unzip -l "$file" | grep -q 'WEB-INF/'; then
        return 11
    fi
    chmod 644 "$file"
    runuser -u glassfish -- /opt/glassfish/bin/asadmin deploy --force=true \
        --name "@@CONTEXT@@" --contextroot "@@CONTEXT@@" "$file" || return 12
}

log "deploying $KEY"
rc=0
deploy_key "$KEY" || rc=$?
if [ "$rc" -eq 0 ]; then
    echo "$KEY" > $STATE/current_war_key
    log "deployed $KEY"
    exit 0
fi

case "$rc" in
    10) log "could not download $KEY, will retry"; exit 1 ;;
    11) log "REJECTED $KEY: it is not a valid WAR; the running version was not touched"
        echo "$KEY" > $STATE/rejected_war_key; exit 1 ;;
    *)  log "FAILED to deploy $KEY (GlassFish error)"
        if [ -n "$CURRENT" ]; then
            # there is a good version to go back to, so this WAR is the problem: do not retry it
            echo "$KEY" > $STATE/rejected_war_key
            log "restoring the previous version $CURRENT"
            if deploy_key "$CURRENT"; then log "previous version restored"; else log "COULD NOT restore $CURRENT"; fi
        fi
        exit 1 ;;
esac
DEPLOYEOF
chmod +x /usr/local/bin/rr-deploy-war

cat > /etc/systemd/system/rr-deploy.service <<'UNITEOF'
[Unit]
Description=Deploy the WAR named in Parameter Store
After=glassfish.service
[Service]
Type=oneshot
ExecStart=/usr/local/bin/rr-deploy-war
UNITEOF
cat > /etc/systemd/system/rr-deploy.timer <<'UNITEOF'
[Unit]
Description=Check for a new WAR every minute
[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
[Install]
WantedBy=timers.target
UNITEOF

echo "== 10. Database backup to S3 every 6 hours"
cat > /usr/local/bin/rr-backup <<'BACKUPEOF'
#!/bin/bash
set -euo pipefail
export AWS_DEFAULT_REGION="@@REGION@@"
BUCKET="@@BUCKET@@"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="/tmp/rr-backup.sql.gz"
docker exec rr-mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --databases restaurant_review_db' | gzip > "$FILE"
[ -s "$FILE" ]
aws s3 cp "$FILE" "s3://$BUCKET/backups/rr-$STAMP.sql.gz"
aws s3 cp "$FILE" "s3://$BUCKET/backups/latest.sql.gz"
rm -f "$FILE"
echo "backup $STAMP done"
BACKUPEOF
chmod +x /usr/local/bin/rr-backup
cat > /etc/systemd/system/rr-backup.service <<'UNITEOF'
[Unit]
Description=Back up the database to S3
After=docker.service
[Service]
Type=oneshot
ExecStart=/usr/local/bin/rr-backup
UNITEOF
cat > /etc/systemd/system/rr-backup.timer <<'UNITEOF'
[Unit]
Description=Database backup every 6 hours
[Timer]
OnCalendar=*-*-* 00/6:00:00
Persistent=true
[Install]
WantedBy=timers.target
UNITEOF

echo "== 11. Start everything"
systemctl daemon-reload
systemctl enable --now glassfish.service
systemctl enable --now nginx.service
systemctl enable --now rr-deploy.timer rr-backup.timer
echo "== bootstrap finished: $(date -u +%FT%TZ)"
touch /var/lib/rr/bootstrap_done
