package com.restaurantreview.api;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.endsWith;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.everyItem;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.is;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import io.restassured.response.Response;

/**
 * GET /reviews (+ filters), GET /reviews/{id}, POST /reviews, PUT /reviews/{id}
 * Status codes checked: 200, 201, 400, 401, 403, 404, 409.
 */
class ReviewApiTest extends ApiTestBase {

    // ------------------------------------------------------------------- GET

    @Test
    void getAll_isPublic_returns200() {
        api().get("/reviews")
                .then()
                .statusCode(200)
                .body("size()", greaterThanOrEqualTo(0));
    }

    @Test
    void getAll_filterByRestaurant_returnsOnlyThatRestaurant() {
        TestUser user = newUser();
        int restaurantId = newRestaurant(user.token);
        newReview(user, restaurantId, 4);

        api().queryParam("restaurantId", restaurantId).get("/reviews")
                .then()
                .statusCode(200)
                .body("size()", is(1))
                .body("restaurantId", everyItem(equalTo(restaurantId)));
    }

    @Test
    void getAll_filterByUser_returnsOnlyThatUser() {
        TestUser user = newUser();
        newReview(user, newRestaurant(user.token), 3);

        api().queryParam("userId", user.id).get("/reviews")
                .then()
                .statusCode(200)
                .body("size()", is(1))
                .body("userId", everyItem(equalTo(user.id)));
    }

    @Test
    void getAll_filterByMinRating_hidesTheLowerOnes() {
        TestUser low = newUser();
        TestUser high = newUser();
        int restaurantId = newRestaurant(low.token);
        newReview(low, restaurantId, 2);
        newReview(high, restaurantId, 5);

        api().queryParam("restaurantId", restaurantId).queryParam("minRating", 4)
                .get("/reviews")
                .then()
                .statusCode(200)
                .body("size()", is(1))
                .body("rating", everyItem(greaterThanOrEqualTo(4)));
    }

    @Test
    void getAll_filterWithNoResults_returns200_andAnEmptyList() {
        api().queryParam("restaurantId", 999999999).get("/reviews")
                .then()
                .statusCode(200)
                .body("size()", is(0));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, 6, -3})
    void getAll_minRatingOutsideOneToFive_returns400(int minRating) {
        api().queryParam("minRating", minRating).get("/reviews")
                .then()
                .statusCode(400)
                .body("error", equalTo("minRating must be between 1 and 5"));
    }

    @Test
    void getById_existing_returns200() {
        TestUser user = newUser();
        int reviewId = newReview(user, newRestaurant(user.token), 5);

        api().get("/reviews/" + reviewId)
                .then()
                .statusCode(200)
                .body("id", equalTo(reviewId))
                .body("userId", equalTo(user.id))
                .body("username", equalTo(user.username))
                .body("rating", equalTo(5));
    }

    @Test
    void getById_missing_returns404() {
        api().get("/reviews/999999999")
                .then()
                .statusCode(404)
                .body("error", equalTo("Review 999999999 not found"));
    }

    // ------------------------------------------------------------------ POST

    @Test
    void create_withoutToken_returns401() {
        api().body(reviewBody(1, 5, "no token")).post("/reviews")
                .then()
                .statusCode(401);
    }

    @Test
    void create_valid_returns201_withLocation_andTheLoggedUserAsAuthor() {
        TestUser user = newUser();
        int restaurantId = newRestaurant(user.token);

        Response response = api(user.token).body(reviewBody(restaurantId, 5, "Excellent"))
                .post("/reviews")
                .then()
                .statusCode(201)
                .body("userId", equalTo(user.id))
                .body("username", equalTo(user.username))
                .body("restaurantId", equalTo(restaurantId))
                .body("rating", equalTo(5))
                .extract().response();

        int id = response.path("id");
        assertThat(response.getHeader("Location"), endsWith("/reviews/" + id));
    }

    @Test
    void create_userIdInTheBodyIsIgnored_theAuthorIsTheTokenUser() {
        TestUser me = newUser();
        TestUser victim = newUser();
        int restaurantId = newRestaurant(me.token);

        Map<String, Object> body = reviewBody(restaurantId, 1, "I am pretending to be someone else");
        body.put("userId", victim.id);

        api(me.token).body(body).post("/reviews")
                .then()
                .statusCode(201)
                .body("userId", equalTo(me.id))
                .body("username", equalTo(me.username));
    }

    @Test
    void create_secondReviewOfTheSameRestaurant_returns409() {
        TestUser user = newUser();
        int restaurantId = newRestaurant(user.token);
        newReview(user, restaurantId, 4);

        api(user.token).body(reviewBody(restaurantId, 5, "again")).post("/reviews")
                .then()
                .statusCode(409)
                .body("error", equalTo("This user already reviewed this restaurant"));
    }

    @Test
    void create_restaurantThatDoesNotExist_returns400() {
        TestUser user = newUser();

        api(user.token).body(reviewBody(999999999, 5, "ghost")).post("/reviews")
                .then()
                .statusCode(400)
                .body("error", equalTo("userId or restaurantId does not exist"));
    }

    @Test
    void create_withoutRestaurantId_returns400() {
        TestUser user = newUser();
        Map<String, Object> body = new HashMap<>();
        body.put("rating", 5);

        api(user.token).body(body).post("/reviews")
                .then()
                .statusCode(400);
    }

    @ParameterizedTest
    @ValueSource(ints = {0, 6, -1, 100})
    void create_ratingOutsideOneToFive_returns400(int rating) {
        TestUser user = newUser();
        int restaurantId = newRestaurant(user.token);

        api(user.token).body(reviewBody(restaurantId, rating, "bad rating")).post("/reviews")
                .then()
                .statusCode(400)
                .body("errors[0]", equalTo("rating must be between 1 and 5"));
    }

    @ParameterizedTest
    @ValueSource(ints = {1, 5})
    void create_ratingAtTheLimits_returns201(int rating) {
        TestUser user = newUser();

        api(user.token).body(reviewBody(newRestaurant(user.token), rating, "limit"))
                .post("/reviews")
                .then()
                .statusCode(201);
    }

    @Test
    void create_withoutComment_returns201() {
        TestUser user = newUser();

        api(user.token).body(reviewBody(newRestaurant(user.token), 3, null))
                .post("/reviews")
                .then()
                .statusCode(201);
    }

    @Test
    void create_commentWithExactlyMaxLength_returns201() {
        TestUser user = newUser();

        api(user.token).body(reviewBody(newRestaurant(user.token), 3, repeat('c', 1000)))
                .post("/reviews")
                .then()
                .statusCode(201);
    }

    @Test
    void create_commentOneCharacterTooLong_returns400() {
        TestUser user = newUser();

        api(user.token).body(reviewBody(newRestaurant(user.token), 3, repeat('c', 1001)))
                .post("/reviews")
                .then()
                .statusCode(400);
    }

    @Test
    void create_massiveComment_returns400_notA500() {
        TestUser user = newUser();

        api(user.token).body(reviewBody(newRestaurant(user.token), 3, repeat('c', 1_000_000)))
                .post("/reviews")
                .then()
                .statusCode(400);
    }

    @Test
    void create_malformedJson_returns400() {
        TestUser user = newUser();

        raw(user.token, "POST", "/reviews", "{\"restaurantId\": 1, \"rating\": ")
                .then()
                .statusCode(400);
    }

    // ------------------------------------------------------------------- PUT

    @Test
    void update_withoutToken_returns401() {
        api().body(reviewBody(1, 4, "x")).put("/reviews/1")
                .then()
                .statusCode(401);
    }

    @Test
    void update_ownReview_returns200_andSavesTheChange() {
        TestUser user = newUser();
        int reviewId = newReview(user, newRestaurant(user.token), 3);

        Map<String, Object> change = new HashMap<>();
        change.put("rating", 5);
        change.put("comment", "Changed my mind");

        api(user.token).body(change).put("/reviews/" + reviewId)
                .then()
                .statusCode(200)
                .body("rating", equalTo(5))
                .body("comment", equalTo("Changed my mind"));

        api().get("/reviews/" + reviewId).then().statusCode(200).body("rating", equalTo(5));
    }

    @Test
    void update_someoneElsesReview_returns403_andDoesNotChangeIt() {
        TestUser author = newUser();
        TestUser intruder = newUser();
        int reviewId = newReview(author, newRestaurant(author.token), 4);

        Map<String, Object> change = new HashMap<>();
        change.put("rating", 1);
        change.put("comment", "Hacked");

        api(intruder.token).body(change).put("/reviews/" + reviewId)
                .then()
                .statusCode(403)
                .body("error", equalTo("You can only edit your own reviews"));

        api().get("/reviews/" + reviewId).then().statusCode(200).body("rating", equalTo(4));
    }

    @Test
    void update_missingReview_returns404() {
        TestUser user = newUser();
        Map<String, Object> change = new HashMap<>();
        change.put("rating", 4);

        api(user.token).body(change).put("/reviews/999999999")
                .then()
                .statusCode(404);
    }

    @Test
    void update_invalidRating_returns400() {
        TestUser user = newUser();
        int reviewId = newReview(user, newRestaurant(user.token), 3);
        Map<String, Object> change = new HashMap<>();
        change.put("rating", 0);

        api(user.token).body(change).put("/reviews/" + reviewId)
                .then()
                .statusCode(400);
    }

    @Test
    void update_cannotMoveTheReviewToAnotherRestaurantOrUser() {
        TestUser user = newUser();
        TestUser other = newUser();
        int restaurantId = newRestaurant(user.token);
        int otherRestaurantId = newRestaurant(user.token);
        int reviewId = newReview(user, restaurantId, 3);

        Map<String, Object> change = new HashMap<>();
        change.put("rating", 4);
        change.put("restaurantId", otherRestaurantId);
        change.put("userId", other.id);

        api(user.token).body(change).put("/reviews/" + reviewId)
                .then()
                .statusCode(200)
                .body("restaurantId", equalTo(restaurantId))
                .body("userId", equalTo(user.id));
    }
}
