package com.restaurantreview.api;

import static org.hamcrest.Matchers.greaterThan;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import io.restassured.http.ContentType;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;

import static io.restassured.RestAssured.given;

/**
 * Shared helpers for all the API tests.
 *
 * Every test creates its OWN users and restaurants with random names, so the
 * tests do not depend on the data that is already in the database and can be
 * run many times in a row (no "already exists" collisions).
 */
public abstract class ApiTestBase {

    protected static final String BASE_URL =
            System.getProperty("api.baseUrl", "http://localhost:8080/RestaurantReviewAPI/api");

    protected static final String PASSWORD = "Password123!";

    /** A user that registered and logged in during the test. */
    protected static final class TestUser {
        public final int id;
        public final String username;
        public final String email;
        public final String token;

        TestUser(int id, String username, String email, String token) {
            this.id = id;
            this.username = username;
            this.email = email;
            this.token = token;
        }
    }

    /** Request without token (public endpoints or to test the 401 answers). */
    protected static RequestSpecification api() {
        return given()
                .baseUri(BASE_URL)
                .contentType(ContentType.JSON)
                .accept(ContentType.JSON);
    }

    /** Request with the header  Authorization: Bearer <token>. */
    protected static RequestSpecification api(String token) {
        return api().header("Authorization", "Bearer " + token);
    }

    protected static String unique() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 12);
    }

    /** Registers a new random user, logs in and returns it with its JWT. */
    protected static TestUser newUser() {
        String username = "qa_" + unique();
        String email = username + "@test.com";

        Map<String, Object> register = new HashMap<>();
        register.put("username", username);
        register.put("email", email);
        register.put("password", PASSWORD);

        int id = api().body(register).post("/auth/register")
                .then().statusCode(201)
                .extract().path("id");

        Map<String, Object> login = new HashMap<>();
        login.put("username", username);
        login.put("password", PASSWORD);

        String token = api().body(login).post("/auth/login")
                .then().statusCode(200)
                .body("token", org.hamcrest.Matchers.not(org.hamcrest.Matchers.emptyOrNullString()))
                .extract().path("token");

        return new TestUser(id, username, email, token);
    }

    /** Body of a valid restaurant with a random name (so it never collides). */
    protected static Map<String, Object> restaurantBody() {
        Map<String, Object> body = new HashMap<>();
        body.put("name", "QA Bistro " + unique());
        body.put("cuisine", "Test");
        body.put("priceRange", 2);
        body.put("city", "Tonala");
        body.put("address", "Calle QA " + unique());
        return body;
    }

    /** Creates a restaurant (needs a token) and returns its id. */
    protected static int newRestaurant(String token) {
        return api(token).body(restaurantBody()).post("/restaurants")
                .then().statusCode(201)
                .body("id", greaterThan(0))
                .extract().path("id");
    }

    protected static Map<String, Object> reviewBody(int restaurantId, int rating, String comment) {
        Map<String, Object> body = new HashMap<>();
        body.put("restaurantId", restaurantId);
        body.put("rating", rating);
        if (comment != null) {
            body.put("comment", comment);
        }
        return body;
    }

    /** Creates a review as the given user and returns its id. */
    protected static int newReview(TestUser user, int restaurantId, int rating) {
        return api(user.token).body(reviewBody(restaurantId, rating, "QA review"))
                .post("/reviews")
                .then().statusCode(201)
                .extract().path("id");
    }

    protected static String repeat(char c, int times) {
        return String.valueOf(c).repeat(times);
    }

    protected static Response raw(String token, String method, String path, String body) {
        RequestSpecification spec = token == null ? api() : api(token);
        return spec.body(body).request(method, path);
    }
}
