package com.restaurantreview.resource;
 
import java.net.URI;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.restaurantreview.dao.ReviewDAO;
import com.restaurantreview.model.Review;
import com.restaurantreview.security.Secured;
import com.restaurantreview.security.SecurityUtil;
import com.restaurantreview.util.ReviewValidator;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;

/**
 * REST resource for reviews.
 *   GET  /api/reviews       -> list reviews (optional filters:
 *                              ?restaurantId=, ?userId=, ?minRating=)
 *   GET  /api/reviews/{id}  -> one review (404 if not found)
 *   POST /api/reviews       -> create a review (201, 400, 401, 409). Needs a token:
 *                              the author is the logged user, not the body.
 *   PUT  /api/reviews/{id}  -> edit rating and comment (200, 400, 401, 403, 404).
 *                              Needs a token; only the author can edit.
 * There is no DELETE: reviews are never removed.
 */
@Path("/reviews")
@Produces(MediaType.APPLICATION_JSON)
public class ReviewResource {

    private static final Logger LOGGER =
            Logger.getLogger(ReviewResource.class.getName());

    // MySQL error codes
    private static final int MYSQL_DUPLICATE_ENTRY = 1062;
    private static final int MYSQL_FOREIGN_KEY_FAILS = 1452;

    private final ReviewDAO reviewDAO = new ReviewDAO();

    @GET
    public Response getAllReviews(@QueryParam("restaurantId") Integer restaurantId,
                                  @QueryParam("userId") Integer userId,
                                  @QueryParam("minRating") Integer minRating) {

        if (minRating != null && (minRating < 1 || minRating > 5)) {
            return error(Response.Status.BAD_REQUEST,
                    "minRating must be between 1 and 5");
        }

        try {
            List<Review> reviews = reviewDAO.findAll(restaurantId, userId, minRating);
            return Response.ok(reviews).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @GET
    @Path("/{id}")
    public Response getReviewById(@PathParam("id") int id) {
        try {
            Review review = reviewDAO.findById(id);
            if (review == null) {
                return error(Response.Status.NOT_FOUND, "Review " + id + " not found");
            }
            return Response.ok(review).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @POST
    @Secured
    @Consumes(MediaType.APPLICATION_JSON)
    public Response createReview(Review review, @Context SecurityContext securityContext) {
        if (review == null) {
            return error(Response.Status.BAD_REQUEST, "Request body is required");
        }
        // The author is always the logged user: a userId sent in the body is ignored
        review.setUserId(SecurityUtil.getUserId(securityContext));
        List<String> problems = ReviewValidator.validateForCreate(review);
        if (!problems.isEmpty()) {
            return validationError(problems);
        }

        try {
            int newId = reviewDAO.create(review);
            Review created = reviewDAO.findById(newId);
            // Relative URI: resolved against the API base, e.g. /api/reviews/13
            return Response.created(URI.create("reviews/" + newId))
                    .entity(created)
                    .build();
        } catch (SQLException e) {
            if (e.getErrorCode() == MYSQL_DUPLICATE_ENTRY) {
                return error(Response.Status.CONFLICT,
                        "This user already reviewed this restaurant");
            }
            if (e.getErrorCode() == MYSQL_FOREIGN_KEY_FAILS) {
                return error(Response.Status.BAD_REQUEST,
                        "userId or restaurantId does not exist");
            }
            return serverError(e);
        }
    }

    @PUT
    @Path("/{id}")
    @Secured
    @Consumes(MediaType.APPLICATION_JSON)
    public Response updateReview(@PathParam("id") int id, Review review,
                                 @Context SecurityContext securityContext) {
        if (review == null) {
            return error(Response.Status.BAD_REQUEST, "Request body is required");
        }
        List<String> problems = ReviewValidator.validateForUpdate(review);
        if (!problems.isEmpty()) {
            return validationError(problems);
        }

        try {
            Review existing = reviewDAO.findById(id);
            if (existing == null) {
                return error(Response.Status.NOT_FOUND, "Review " + id + " not found");
            }
            // Only the author can edit (403 = logged in, but not allowed)
            if (existing.getUserId() != SecurityUtil.getUserId(securityContext)) {
                return error(Response.Status.FORBIDDEN, "You can only edit your own reviews");
            }
            reviewDAO.update(id, review.getRating(), review.getComment());
            return Response.ok(reviewDAO.findById(id)).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    private Response error(Response.Status status, String message) {
        return Response.status(status)
                .entity(Map.of("error", message))
                .build();
    }

    private Response validationError(List<String> problems) {
        return Response.status(Response.Status.BAD_REQUEST)
                .entity(Map.of("errors", problems))
                .build();
    }

    private Response serverError(SQLException e) {
        // The real error goes to the server log, not to the client
        LOGGER.log(Level.SEVERE, "Database error", e);
        return error(Response.Status.INTERNAL_SERVER_ERROR, "Internal server error");
    }
}
