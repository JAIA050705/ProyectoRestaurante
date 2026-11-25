package com.restaurantreview.resource;
 
import java.net.URI;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.restaurantreview.dao.FavoriteDAO;
import com.restaurantreview.dao.RestaurantDAO;
import com.restaurantreview.dao.UserDAO;
import com.restaurantreview.model.Restaurant;
import com.restaurantreview.security.Secured;
import com.restaurantreview.security.SecurityUtil;

import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;

/**
 * REST resource for the favorite restaurants of a user.
 *   GET    /api/users/{userId}/favorites                  -> list favorites (404 if no user)
 *   POST   /api/users/{userId}/favorites/{restaurantId}   -> add a favorite (201, 404, 409)
 *   DELETE /api/users/{userId}/favorites/{restaurantId}   -> remove it (204, 404)
 * All three need a token, and the {userId} in the URL must be the logged user:
 * nobody can read or change another user's favorites (403). This prevents BOLA/IDOR.
 * This is the DELETE web service of the project. Reviews are never deleted.
 */
@Path("/users/{userId}/favorites")
@Secured
@Produces(MediaType.APPLICATION_JSON)
public class FavoriteResource {

    private static final Logger LOGGER =
            Logger.getLogger(FavoriteResource.class.getName());

    // MySQL error code for a duplicate entry (already a favorite)
    private static final int MYSQL_DUPLICATE_ENTRY = 1062;

    private final FavoriteDAO favoriteDAO = new FavoriteDAO();
    private final UserDAO userDAO = new UserDAO();
    private final RestaurantDAO restaurantDAO = new RestaurantDAO();

    @GET
    public Response getFavorites(@PathParam("userId") int userId,
                                 @Context SecurityContext securityContext) {
        if (!isOwner(userId, securityContext)) {
            return forbidden();
        }
        try {
            if (!userDAO.exists(userId)) {
                return error(Response.Status.NOT_FOUND, "User " + userId + " not found");
            }
            List<Restaurant> favorites = favoriteDAO.findRestaurantsByUser(userId);
            return Response.ok(favorites).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @POST
    @Path("/{restaurantId}")
    public Response addFavorite(@PathParam("userId") int userId,
                                @PathParam("restaurantId") int restaurantId,
                                @Context SecurityContext securityContext) {
        if (!isOwner(userId, securityContext)) {
            return forbidden();
        }
        try {
            if (!userDAO.exists(userId)) {
                return error(Response.Status.NOT_FOUND, "User " + userId + " not found");
            }
            Restaurant restaurant = restaurantDAO.findById(restaurantId);
            if (restaurant == null) {
                return error(Response.Status.NOT_FOUND,
                        "Restaurant " + restaurantId + " not found");
            }

            favoriteDAO.add(userId, restaurantId);
            // Relative URI: resolved against the API base
            return Response.created(
                            URI.create("users/" + userId + "/favorites/" + restaurantId))
                    .entity(restaurant)
                    .build();
        } catch (SQLException e) {
            if (e.getErrorCode() == MYSQL_DUPLICATE_ENTRY) {
                return error(Response.Status.CONFLICT,
                        "This restaurant is already in the user's favorites");
            }
            return serverError(e);
        }
    }

    @DELETE
    @Path("/{restaurantId}")
    public Response removeFavorite(@PathParam("userId") int userId,
                                   @PathParam("restaurantId") int restaurantId,
                                   @Context SecurityContext securityContext) {
        if (!isOwner(userId, securityContext)) {
            return forbidden();
        }
        try {
            if (!favoriteDAO.remove(userId, restaurantId)) {
                return error(Response.Status.NOT_FOUND,
                        "This restaurant is not in the user's favorites");
            }
            return Response.noContent().build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    /** True if the {userId} of the URL is the logged user. */
    private boolean isOwner(int userId, SecurityContext securityContext) {
        return userId == SecurityUtil.getUserId(securityContext);
    }

    private Response forbidden() {
        return error(Response.Status.FORBIDDEN, "You can only access your own favorites");
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
