package com.restaurantreview.api;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.emptyOrNullString;
import static org.hamcrest.Matchers.nullValue;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;

/**
 * POST /auth/register, POST /auth/login, GET /auth/me
 * Status codes checked: 200, 201, 400, 401, 409.
 */
class AuthApiTest extends ApiTestBase {

    private static Map<String, Object> registerBody(String username, String email, String password) {
        Map<String, Object> body = new HashMap<>();
        body.put("username", username);
        body.put("email", email);
        body.put("password", password);
        return body;
    }

    private static Map<String, Object> loginBody(String username, String password) {
        Map<String, Object> body = new HashMap<>();
        body.put("username", username);
        body.put("password", password);
        return body;
    }

    // ---------------------------------------------------------------- register

    @Test
    void register_validData_returns201_andNeverShowsThePassword() {
        String username = "qa_" + unique();

        api().body(registerBody(username, username + "@test.com", PASSWORD))
                .post("/auth/register")
                .then()
                .statusCode(201)
                .body("id", greaterThan(0))
                .body("username", equalTo(username))
                .body("email", equalTo(username + "@test.com"))
                .body("password", nullValue())
                .body("passwordHash", nullValue())
                .body("password_hash", nullValue());
    }

    @Test
    void register_duplicateUsername_returns409() {
        String username = "qa_" + unique();
        api().body(registerBody(username, username + "@test.com", PASSWORD))
                .post("/auth/register").then().statusCode(201);

        api().body(registerBody(username, "other_" + username + "@test.com", PASSWORD))
                .post("/auth/register")
                .then()
                .statusCode(409)
                .body("error", equalTo("Username or email is already registered"));
    }

    @Test
    void register_duplicateEmail_returns409() {
        String username = "qa_" + unique();
        String email = username + "@test.com";
        api().body(registerBody(username, email, PASSWORD))
                .post("/auth/register").then().statusCode(201);

        api().body(registerBody("qa_" + unique(), email, PASSWORD))
                .post("/auth/register")
                .then()
                .statusCode(409);
    }

    @Test
    void register_everythingInvalid_returns400_withOneErrorPerField() {
        api().body(registerBody("ab", "not-an-email", "short"))
                .post("/auth/register")
                .then()
                .statusCode(400)
                .body("errors", hasSize(3));
    }

    @Test
    void register_passwordTooShort_returns400() {
        api().body(registerBody("qa_" + unique(), "x" + unique() + "@test.com", "1234567"))
                .post("/auth/register")
                .then()
                .statusCode(400);
    }

    @Test
    void register_sqlInjectionInUsername_returns400() {
        api().body(registerBody("x'; DROP TABLE users;--", "x" + unique() + "@test.com", PASSWORD))
                .post("/auth/register")
                .then()
                .statusCode(400);
    }

    @Test
    void register_malformedJson_returns400() {
        raw(null, "POST", "/auth/register", "{this is not json")
                .then()
                .statusCode(400)
                .body("error", equalTo("Request body is not valid JSON"));
    }

    // ------------------------------------------------------------------- login

    @Test
    void login_correctCredentials_returns200_withBearerToken() {
        String username = "qa_" + unique();
        api().body(registerBody(username, username + "@test.com", PASSWORD))
                .post("/auth/register").then().statusCode(201);

        api().body(loginBody(username, PASSWORD))
                .post("/auth/login")
                .then()
                .statusCode(200)
                .body("token", not(emptyOrNullString()))
                .body("tokenType", equalTo("Bearer"))
                .body("expiresIn", equalTo(3600))
                .body("user.username", equalTo(username));
    }

    @Test
    void login_wrongPassword_returns401() {
        TestUser user = newUser();

        api().body(loginBody(user.username, "WrongPassword1!"))
                .post("/auth/login")
                .then()
                .statusCode(401)
                .body("error", equalTo("Invalid username or password"));
    }

    @Test
    void login_unknownUser_returns401_withTheSameMessage() {
        // Same message as a wrong password: the API must not reveal which usernames exist
        api().body(loginBody("nobody_" + unique(), PASSWORD))
                .post("/auth/login")
                .then()
                .statusCode(401)
                .body("error", equalTo("Invalid username or password"));
    }

    @Test
    void login_missingFields_returns400() {
        api().body(new HashMap<String, Object>())
                .post("/auth/login")
                .then()
                .statusCode(400);
    }

    // --------------------------------------------------------------------- me

    @Test
    void me_withoutToken_returns401() {
        api().get("/auth/me")
                .then()
                .statusCode(401)
                .header("WWW-Authenticate", "Bearer")
                .body("error", equalTo("Missing or malformed Authorization header"));
    }

    @Test
    void me_withValidToken_returns200_andTheOwnData() {
        TestUser user = newUser();

        api(user.token).get("/auth/me")
                .then()
                .statusCode(200)
                .body("id", equalTo(user.id))
                .body("username", equalTo(user.username));
    }

    @Test
    void me_garbageToken_returns401() {
        api("this.is.not-a-jwt").get("/auth/me")
                .then()
                .statusCode(401)
                .body("error", equalTo("Invalid or expired token"));
    }

    @Test
    void me_tamperedToken_returns401() {
        TestUser user = newUser();
        String[] parts = user.token.split("\\.");
        // Change the first character of the signature: the signature no longer matches
        char first = parts[2].charAt(0);
        char changed = first == 'A' ? 'B' : 'A';
        String tampered = parts[0] + "." + parts[1] + "." + changed + parts[2].substring(1);

        api(tampered).get("/auth/me")
                .then()
                .statusCode(401);
    }

    @Test
    void me_wrongAuthorizationScheme_returns401() {
        api().header("Authorization", "Basic dXNlcjpwYXNz").get("/auth/me")
                .then()
                .statusCode(401);
    }
}
