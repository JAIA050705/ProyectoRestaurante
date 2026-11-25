package com.restaurantreview.security;

import java.security.Principal;
import java.util.Map;

import jakarta.annotation.Priority;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.core.HttpHeaders; 
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import jakarta.ws.rs.ext.Provider;

/**
 * Runs before every method marked with @Secured.
 * Reads the header  Authorization: Bearer <token>, validates the JWT and
 * stores the user id in the SecurityContext. If anything is wrong it stops
 * the request with 401 Unauthorized.
 */
@Secured
@Provider
@Priority(Priorities.AUTHENTICATION)
public class AuthenticationFilter implements ContainerRequestFilter {

    private static final String BEARER_PREFIX = "Bearer ";

    @Override
    public void filter(ContainerRequestContext requestContext) {
        String header = requestContext.getHeaderString(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith(BEARER_PREFIX)) {
            reject(requestContext, "Missing or malformed Authorization header");
            return;
        }

        Integer userId = JwtService.verifyToken(header.substring(BEARER_PREFIX.length()).trim());
        if (userId == null) {
            reject(requestContext, "Invalid or expired token");
            return;
        }

        final int authenticatedUserId = userId;
        final SecurityContext original = requestContext.getSecurityContext();
        requestContext.setSecurityContext(new SecurityContext() {
            @Override
            public Principal getUserPrincipal() {
                return () -> String.valueOf(authenticatedUserId);
            }

            @Override
            public boolean isUserInRole(String role) {
                return false;   // roles are not used yet
            }

            @Override
            public boolean isSecure() {
                return original != null && original.isSecure();
            }

            @Override
            public String getAuthenticationScheme() {
                return "Bearer";
            }
        });
    }

    private void reject(ContainerRequestContext requestContext, String message) {
        requestContext.abortWith(Response.status(Response.Status.UNAUTHORIZED)
                .header(HttpHeaders.WWW_AUTHENTICATE, "Bearer")
                .type(MediaType.APPLICATION_JSON)
                .entity(Map.of("error", message))
                .build());
    }
}