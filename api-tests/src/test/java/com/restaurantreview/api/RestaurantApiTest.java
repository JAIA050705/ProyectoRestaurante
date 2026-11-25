package com.restaurantreview.api;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.endsWith;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import io.restassured.path.json.JsonPath;
import io.restassured.response.Response;

/**
 * GET /restaurants, GET /restaurants/{id}, GET /restaurants/{id}/rating,
 * POST /restaurants
 * Status codes checked: 200, 201, 400, 401, 404, 409.
 */
class RestaurantApiTest extends ApiTestBase {

    // ------------------------------------------------------------------- GET

    @Test
    void getAll_isPublic_returns200_andAList() {
        api().get("/restaurants")
                .then()
                .statusCode(200)
                .body("size()", greaterThanOrEqualTo(0));
    }

    @Test
    void getById_existing_returns200() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        int id = api(user.token).body(body).post("/restaurants")
                .then().statusCode(201).extract().path("id");

        api().get("/restaurants/" + id)
                .then()
                .statusCode(200)
                .body("id", equalTo(id))
                .body("name", equalTo(body.get("name")))
                .body("priceRange", equalTo(2));
    }

    @Test
    void getById_missing_returns404() {
        api().get("/restaurants/999999999")
                .then()
                .statusCode(404)
                .body("error", equalTo("Restaurant 999999999 not found"));
    }

    @Test
    void getById_notANumber_returns404() {
        // JAX-RS answers 404 when the id in the path cannot be converted to int
        api().get("/restaurants/abc")
                .then()
                .statusCode(404);
    }

    // ------------------------------------------------------------------ POST

    @Test
    void create_withoutToken_returns401() {
        api().body(restaurantBody()).post("/restaurants")
                .then()
                .statusCode(401);
    }

    @Test
    void create_valid_returns201_withLocationHeader() {
        TestUser user = newUser();

        Response response = api(user.token).body(restaurantBody()).post("/restaurants")
                .then()
                .statusCode(201)
                .body("id", greaterThan(0))
                .extract().response();

        int id = response.path("id");
        // Location points to the new resource, e.g. .../api/restaurants/7
        assertThat(response.getHeader("Location"), endsWith("/restaurants/" + id));

        api().get("/restaurants/" + id).then().statusCode(200);
    }

    @Test
    void create_sameNameAndAddress_returns409() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        api(user.token).body(body).post("/restaurants").then().statusCode(201);

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(409)
                .body("error", equalTo("A restaurant with this name and address already exists"));
    }

    @Test
    void create_sameNameDifferentAddress_returns201() {
        TestUser user = newUser();
        Map<String, Object> first = restaurantBody();
        api(user.token).body(first).post("/restaurants").then().statusCode(201);

        Map<String, Object> second = restaurantBody();
        second.put("name", first.get("name"));
        api(user.token).body(second).post("/restaurants").then().statusCode(201);
    }

    @Test
    void create_everythingInvalid_returns400_withTheListOfErrors() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        body.put("name", "   ");
        body.put("priceRange", 9);

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(400)
                .body("errors.size()", equalTo(2));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, 5, -1, 100})
    void create_priceRangeOutsideOneToFour_returns400(int priceRange) {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        body.put("priceRange", priceRange);

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(400);
    }

    @ParameterizedTest
    @ValueSource(ints = {1, 4})
    void create_priceRangeAtTheLimits_returns201(int priceRange) {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        body.put("priceRange", priceRange);

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(201);
    }

    @Test
    void create_nameWithExactlyMaxLength_returns201() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        body.put("name", repeat('N', 100));

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(201);
    }

    @Test
    void create_nameOneCharacterTooLong_returns400() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        body.put("name", repeat('N', 101));

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(400);
    }

    @Test
    void create_massiveField_returns400_notA500() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        body.put("address", repeat('A', 1_000_000));   // about 1 MB of text

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(400);
    }

    @Test
    void create_withAccents_returns201_andKeepsThem() {
        TestUser user = newUser();
        Map<String, Object> body = restaurantBody();
        String name = "Taquería Ñandú " + unique();
        body.put("name", name);

        api(user.token).body(body).post("/restaurants")
                .then()
                .statusCode(201)
                .body("name", equalTo(name));
    }

    @Test
    void create_malformedJson_returns400() {
        TestUser user = newUser();

        raw(user.token, "POST", "/restaurants", "JSON: {\"name\":\"x\"}")
                .then()
                .statusCode(400)
                .body("error", equalTo("Request body is not valid JSON"));
    }

    // ---------------------------------------------------------------- rating

    @Test
    void rating_restaurantWithoutReviews_returns200_withZeros() {
        TestUser user = newUser();
        int restaurantId = newRestaurant(user.token);

        JsonPath json = api().get("/restaurants/" + restaurantId + "/rating")
                .then().statusCode(200).extract().jsonPath();

        assertEquals(0, json.getInt("totalReviews"));
        assertEquals(0.0, json.getDouble("averageRating"), 0.001);
    }

    @Test
    void rating_withTwoReviews_returnsTheAverage() {
        TestUser first = newUser();
        TestUser second = newUser();
        int restaurantId = newRestaurant(first.token);
        newReview(first, restaurantId, 5);
        newReview(second, restaurantId, 4);

        JsonPath json = api().get("/restaurants/" + restaurantId + "/rating")
                .then().statusCode(200).extract().jsonPath();

        assertEquals(2, json.getInt("totalReviews"));
        assertEquals(4.5, json.getDouble("averageRating"), 0.001);
        Map<String, Object> counts = json.getMap("ratingCounts");
        assertEquals(1, ((Number) counts.get("5")).intValue());
        assertEquals(1, ((Number) counts.get("4")).intValue());
    }

    @Test
    void rating_missingRestaurant_returns404() {
        api().get("/restaurants/999999999/rating")
                .then()
                .statusCode(404);
    }
}
