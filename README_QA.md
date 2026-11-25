# QA & Testing - Restaurant Review Platform API

Three kinds of tests, one for each point of the QA requirement.

## 1. REST API testing (JUnit 5 + RestAssured) - `api-tests/`

`mvn test` runs 5 classes against a RUNNING API (GlassFish + MySQL):

| Class | Endpoints | Status codes checked |
|---|---|---|
| `AuthApiTest` | register, login, me | 200, 201, 400, 401, 409 |
| `RestaurantApiTest` | GET list / by id / rating, POST | 200, 201, 400, 401, 404, 409 |
| `ReviewApiTest` | GET list + filters / by id, POST, PUT | 200, 201, 400, 401, 403, 404, 409 |
| `FavoriteApiTest` | GET list, POST, DELETE | 200, 201, 204, 401, 403, 404, 409 |

Every test creates its own random users and restaurants, so it does not depend on the
existing data and can run many times. The API address is `-Dapi.baseUrl=...`
(default `http://localhost:8080/RestaurantReviewAPI/api`).

Security checks included: no token (401), token of another user (403), tampered or garbage
token (401), `userId` in the body ignored, password/hash never returned, SQL injection text
rejected, same error for unknown user and wrong password.

## 2. Database state testing - `db-tests/`

| Script | What it does |
|---|---|
| `01_empty_tables.sql` | Empties all tables (API must answer 200 `[]` or 404, never 500) |
| `02_edge_cases.sql` | Inserts rows on the limits and runs 18 invalid operations that MySQL must reject; prints PASS/FAIL |
| `03_massive_data.sql` | Loads 5,000 users, 1,000 restaurants, 25,000 reviews |
| `04_cleanup_test_data.sql` | Removes only the test rows |

To restore the sample data run `restaurant_review_schema.sql` again.

## 3. GitLab automation - `.gitlab-ci.yml`

Stages `build` -> `database-tests` -> `api-tests`. Any failing test fails the job and the
pipeline. JUnit reports are attached to the pipeline page.
