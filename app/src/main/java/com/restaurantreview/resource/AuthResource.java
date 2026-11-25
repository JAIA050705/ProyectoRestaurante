package com.restaurantreview.resource;

import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.restaurantreview.dao.UserDAO;
import com.restaurantreview.model.LoginRequest;
import com.restaurantreview.model.LoginResponse;
import com.restaurantreview.model.RegisterRequest;
import com.restaurantreview.model.User;
import com.restaurantreview.security.JwtService;
import com.restaurantreview.security.PasswordHasher;
import com.restaurantreview.security.Secured;
import com.restaurantreview.security.SecurityUtil;
import com.restaurantreview.util.UserValidator;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;

/**
 * Authentication endpoints.
 *   POST /api/auth/register -> create an account (201, 400, 409)
 *   POST /api/auth/login    -> get a JWT (200, 400, 401)
 *   GET  /api/auth/me       -> who am I (200, 401). Needs a token.
 */
@Path("/auth")
@Produces(MediaType.APPLICATION_JSON)
public class AuthResource {

    private static final Logger LOGGER =
            Logger.getLogger(AuthResource.class.getName());

    // MySQL error code for a duplicate entry (unique username or email)
    private static final int MYSQL_DUPLICATE_ENTRY = 1062;

    private final UserDAO userDAO = new UserDAO();

    @POST
    @Path("/register")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response register(RegisterRequest request) {
        if (request == null) {
            return error(Response.Status.BAD_REQUEST, "Request body is required");
        }
        List<String> problems = UserValidator.validateForRegister(request);
        if (!problems.isEmpty()) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(Map.of("errors", problems))
                    .build();
        }

        try {
            String email = request.getEmail().trim();
            int newId = userDAO.create(request.getUsername(), email,
                    PasswordHasher.hash(request.getPassword()));
            User created = userDAO.findById(newId);
            return Response.status(Response.Status.CREATED).entity(created).build();
        } catch (SQLException e) {
            if (e.getErrorCode() == MYSQL_DUPLICATE_ENTRY) {
                return error(Response.Status.CONFLICT, "Username or email is already registered");
            }
            return serverError(e);
        }
    }

    @POST
    @Path("/login")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response login(LoginRequest request) {
        if (request == null || isBlank(request.getUsername()) || isBlank(request.getPassword())) {
            return error(Response.Status.BAD_REQUEST, "username and password are required");
        }

        try {
            UserDAO.Credentials credentials = userDAO.findCredentials(request.getUsername());

            boolean valid;
            if (credentials == null) {
                // Same work as a real check, so the response time does not reveal unknown users
                PasswordHasher.verify(request.getPassword(), PasswordHasher.DUMMY_HASH);
                valid = false;
            } else {
                valid = PasswordHasher.verify(request.getPassword(), credentials.getPasswordHash());
            }

            if (!valid) {
                // Same message for "unknown user" and "wrong password" on purpose
                return error(Response.Status.UNAUTHORIZED, "Invalid username or password");
            }

            String token = JwtService.createToken(credentials.getId(), credentials.getUsername());
            User user = userDAO.findById(credentials.getId());
            return Response.ok(new LoginResponse(token, JwtService.DEFAULT_TTL_SECONDS, user)).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    @GET
    @Path("/me")
    @Secured
    public Response me(@Context SecurityContext securityContext) {
        try {
            User user = userDAO.findById(SecurityUtil.getUserId(securityContext));
            if (user == null) {
                // The token is valid but the user was removed after it was issued
                return error(Response.Status.UNAUTHORIZED, "The user of this token no longer exists");
            }
            return Response.ok(user).build();
        } catch (SQLException e) {
            return serverError(e);
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
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
