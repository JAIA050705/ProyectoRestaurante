package com.restaurantreview.api;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;

import org.junit.jupiter.api.Test;

/**
 * GET /users/{userId}/favorites
 * POST and DELETE /users/{userId}/favorites/{restaurantId}
 * Status codes checked: 200, 201, 204, 401, 403, 404, 409.
 * Every call needs a token, and the {userId} of the URL must be the logged user.
 */
class FavoriteApiTest extends ApiTestBase {

    // ----------------------------------------------------------- no token (401)

    @Test
    void list_withoutToken_returns401() {
        api().get("/users/1/favorites").then().statusCode(401);
    }

    @Test
    void add_withoutToken_returns401() {
        api().post("/users/1/favorites/1").then().statusCode(401);
    }

    @Test
    void remove_withoutToken_returns401() {
        api().delete("/users/1/favorites/1").then().statusCode(401);
    }

    // ---------------------------------------------------- other user's data (403)

    @Test
    void list_ofAnotherUser_returns403() {
        TestUser me = newUser();
        TestUser other = newUser();

        api(me.token).get("/users/" + other.id + "/favorites")
                .then()
                .statusCode(403)
                .body("error", equalTo("You can only access your own favorites"));
    }

    @Test
    void add_toAnotherUser_returns403_andNothingIsSaved() {
        TestUser me = newUser();
        TestUser other = newUser();
        int restaurantId = newRestaurant(me.token);

        api(me.token).post("/users/" + other.id + "/favorites/" + restaurantId)
                .then()
                .statusCode(403);

        api(other.token).get("/users/" + other.id + "/favorites")
                .then()
                .statusCode(200)
                .body("size()", is(0));
    }

    @Test
    void remove_fromAnotherUser_returns403_andTheFavoriteSurvives() {
        TestUser owner = newUser();
        TestUser intruder = newUser();
        int restaurantId = newRestaurant(owner.token);
        api(owner.token).post("/users/" + owner.id + "/favorites/" + restaurantId)
                .then().statusCode(201);

        api(intruder.token).delete("/users/" + owner.id + "/favorites/" + restaurantId)
                .then()
                .statusCode(403);

        api(owner.token).get("/users/" + owner.id + "/favorites")
                .then()
                .statusCode(200)
                .body("id", hasItem(restaurantId));
    }

    @Test
    void list_ofAUserThatDoesNotExist_returns403_notRevealingWhoExists() {
        TestUser me = newUser();

        api(me.token).get("/users/999999999/favorites")
                .then()
                .statusCode(403);
    }

    // ------------------------------------------------------------ own data

    @Test
    void list_newUser_returns200_andAnEmptyList() {
        TestUser me = newUser();

        api(me.token).get("/users/" + me.id + "/favorites")
                .then()
                .statusCode(200)
                .body("size()", is(0));
    }

    @Test
    void add_returns201_andTheRestaurantAppearsInTheList() {
        TestUser me = newUser();
        int restaurantId = newRestaurant(me.token);

        api(me.token).post("/users/" + me.id + "/favorites/" + restaurantId)
                .then()
                .statusCode(201)
                .body("id", equalTo(restaurantId));

        api(me.token).get("/users/" + me.id + "/favorites")
                .then()
                .statusCode(200)
                .body("id", hasItem(restaurantId));
    }

    @Test
    void add_sameRestaurantTwice_returns409() {
        TestUser me = newUser();
        int restaurantId = newRestaurant(me.token);
        api(me.token).post("/users/" + me.id + "/favorites/" + restaurantId)
                .then().statusCode(201);

        api(me.token).post("/users/" + me.id + "/favorites/" + restaurantId)
                .then()
                .statusCode(409);
    }

    @Test
    void add_restaurantThatDoesNotExist_returns404() {
        TestUser me = newUser();

        api(me.token).post("/users/" + me.id + "/favorites/999999999")
                .then()
                .statusCode(404);
    }

    @Test
    void remove_returns204_andThenTheFavoriteIsGone() {
        TestUser me = newUser();
        int restaurantId = newRestaurant(me.token);
        api(me.token).post("/users/" + me.id + "/favorites/" + restaurantId)
                .then().statusCode(201);

        api(me.token).delete("/users/" + me.id + "/favorites/" + restaurantId)
                .then()
                .statusCode(204);

        api(me.token).get("/users/" + me.id + "/favorites")
                .then()
                .statusCode(200)
                .body("id", not(hasItem(restaurantId)));
    }

    @Test
    void remove_somethingThatIsNotAFavorite_returns404() {
        TestUser me = newUser();
        int restaurantId = newRestaurant(me.token);

        api(me.token).delete("/users/" + me.id + "/favorites/" + restaurantId)
                .then()
                .statusCode(404);
    }
}
