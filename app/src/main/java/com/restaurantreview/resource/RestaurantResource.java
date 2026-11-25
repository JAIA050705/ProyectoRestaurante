package com.restaurantreview.resource;
 
import java.net.URI;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.restaurantreview.dao.RestaurantDAO;
import com.restaurantreview.dao.ReviewDAO;
import com.restaurantreview.model.RatingSummary;
import com.restaurantreview.model.Restaurant;
import com.restaurantreview.security.Secured;
import com.restaurantreview.util.RestaurantValidator;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

/**
 * REST resource for restaurants.
 *   GET  /api/restaurants       -> list all restaurants
 *   GET  /api/restaurants/{id}  -> one restaurant (404 if not found)
 *   GET  /api/restaurants/{id}/rating -> average rating and star counts (404 if not found)
 *   POST /api/restaurants       -> create a restaurant (201, 400, 401, 409). Needs a token.
 */
@Path("/restaurants")
@Produces(MediaType.APPLICATION_JSON)
public class RestaurantResource {

    private static final Logger LOGGER =
            Logger.getLogger(RestaurantResource.class.getName());

    // MySQL error code for a duplicate entry (unique constraint)
    private static final int MYSQL_DUPLICATE_ENTRY = 1062;

    private final RestaurantDAO restaurantDAO = new RestaurantDAO();
    private final ReviewDAO reviewDAO = new ReviewDAO();

    @GET
    public Response getAllRestaurants() {
        try {
            List<Restaurant> restaurants = restaurantDAO.findAll();
            return Response.ok(restaurants).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @GET
    @Path("/{id}")
    public Response getRestaurantById(@PathParam("id") int id) {
        try {
            Restaurant restaurant = restaurantDAO.findById(id);
            if (restaurant == null) {
                return error(Response.Status.NOT_FOUND, "Restaurant " + id + " not found");
            }
            return Response.ok(restaurant).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @GET
    @Path("/{id}/rating")
    public Response getRestaurantRating(@PathParam("id") int id) {
        try {
            Restaurant restaurant = restaurantDAO.findById(id);
            if (restaurant == null) {
                return error(Response.Status.NOT_FOUND, "Restaurant " + id + " not found");
            }
            RatingSummary summary = reviewDAO.getRatingSummary(id);
            summary.setRestaurantName(restaurant.getName());
            return Response.ok(summary).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @POST
    @Secured
    @Consumes(MediaType.APPLICATION_JSON)
    public Response createRestaurant(Restaurant restaurant) {
        if (restaurant == null) {
            return error(Response.Status.BAD_REQUEST, "Request body is required");
        }
        List<String> problems = RestaurantValidator.validateForCreate(restaurant);
        if (!problems.isEmpty()) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(Map.of("errors", problems))
                    .build();
        }

        // Remove accidental spaces at the start/end before saving
        restaurant.setName(restaurant.getName().trim());
        restaurant.setCuisine(restaurant.getCuisine().trim());
        restaurant.setCity(restaurant.getCity().trim());
        restaurant.setAddress(restaurant.getAddress().trim());

        try {
            int newId = restaurantDAO.create(restaurant);
            Restaurant created = restaurantDAO.findById(newId);
            // Relative URI: resolved against the API base, e.g. /api/restaurants/7
            return Response.created(URI.create("restaurants/" + newId))
                    .entity(created)
                    .build();
        } catch (SQLException e) {
            if (e.getErrorCode() == MYSQL_DUPLICATE_ENTRY) {
                return error(Response.Status.CONFLICT,
                        "A restaurant with this name and address already exists");
            }
            return serverError(e);
        }
    }

    private Response error(Response.Status status, String message) {
        return Response.status(status)
                .entity(Map.of("error", message))
                .build();
    }

    private Response serverError(SQLException e) {
        // The real error goes to the server log, not to the client
        LOGGER.log(Level.SEVERE, "Database error", e);
        return error(Response.Status.INTERNAL_SERVER_ERROR, "Internal server error");
    }
}
