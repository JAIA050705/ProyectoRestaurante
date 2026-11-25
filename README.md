# Restaurant Review Platform API

RESTful API for restaurant reviews (Users, Restaurants, Reviews, Favorites) with JWT authentication and a plain
HTML/CSS/JS web UI served from the same WAR. Built with Java, Jakarta REST on GlassFish 8, and MySQL 8.4.

Two ways to run it, the same WAR in both:

| Where | How |
|---|---|
| Local | Eclipse + GlassFish 8 + MySQL (see "Run locally") |
| AWS | One Python script creates everything (see "Deploy on AWS") |

## Repository layout

```
app/          Eclipse project (Java source, webapp with the UI)
api-tests/    JUnit 5 + RestAssured suite
db-tests/     MySQL scripts: edge cases and massive data
database/     Schema and sample data (restaurant_review_schema.sql)
infra/        AWS deployment scripts (Python + boto3) and the server bootstrap
docs/         PDF documentation, diagrams and the resilience report
.gitlab-ci.yml  Pipeline: build, database tests, REST API tests
```

## Run locally

1. Create the database with `database/restaurant_review_schema.sql`.
2. Set the environment variables used by `DatabaseConnection`: `DB_URL`, `DB_USER`, `DB_PASSWORD`, and `JWT_SECRET`
   (secrets are never stored in the code).
3. Export the project as a WAR and deploy it to GlassFish. Open `http://localhost:8080/RestaurantReviewAPI/`.

Note: the sample users in the schema have placeholder password hashes. Register a new user from the UI.

## Deploy on AWS

Requirements: Python 3.10+, `pip install -r infra/requirements.txt`, and AWS credentials (AWS Academy Learner Lab
works). All commands run from `infra/`.

```
python preflight.py                              # read-only permission check
python deploy.py base --war RestaurantReviewAPI.war   # key pair, firewall, S3, secrets, uploads
python deploy.py server                          # EC2 + Elastic IP + alarms, waits for the API
python deploy.py status
```

Operations:

```
python deploy.py update --war NEW.war   # server deploys it by itself within a minute
python deploy.py rollback               # back to the previous WAR
python deploy.py stop / start           # save compute hours when unused
python resilience_tests.py              # fault-injection tests (add --include-server-loss for the destructive one)
python destroy.py                       # remove everything tagged Project=restaurant-review
```

Architecture: nginx (port 80) -> GlassFish (8080) -> MySQL 8.4 in Docker with data on a separate EBS volume.
WARs and backups live in S3, secrets in SSM Parameter Store, and two CloudWatch alarms restart or recover the
instance. See `docs/Documentacion_AWS.pdf` (Spanish) for the deployment guide, architecture diagram, design
decisions, cost analysis and resilience results.

Never commit `infra/*.pem`, `preflight_report.json`, or any credentials.
