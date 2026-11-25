package com.restaurantreview.security;

import jakarta.ws.rs.core.SecurityContext;

/**
 * Helper to read who is making the request. Only valid in methods marked
 * with @Secured, where the AuthenticationFilter already put the user there.
 */
public final class SecurityUtil {

    private SecurityUtil() {
        // Utility class, no instances
    }

    /** Returns the id of the authenticated user (taken from the JWT). */
    public static int getUserId(SecurityContext securityContext) {
        return Integer.parseInt(securityContext.getUserPrincipal().getName());
    }
}
