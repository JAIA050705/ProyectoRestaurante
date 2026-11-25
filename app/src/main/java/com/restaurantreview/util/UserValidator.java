package com.restaurantreview.util;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

import com.restaurantreview.model.RegisterRequest;

/**
 * Business rules for registering a user. Pure logic (no database, no server),
 * so it is easy to unit test later.
 * Returns the list of problems found; an empty list means valid.
 */
public final class UserValidator {

    public static final int MIN_PASSWORD_LENGTH = 8;
    public static final int MAX_PASSWORD_LENGTH = 128;
    public static final int MAX_EMAIL_LENGTH = 100;

    // 3 to 50 letters, digits or underscores (no spaces, no quotes)
    private static final Pattern USERNAME = Pattern.compile("^[A-Za-z0-9_]{3,50}$");
    private static final Pattern EMAIL = Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");

    private UserValidator() {
        // Utility class, no instances
    }

    public static List<String> validateForRegister(RegisterRequest request) {
        List<String> errors = new ArrayList<>();

        String username = request.getUsername();
        if (username == null || !USERNAME.matcher(username).matches()) {
            errors.add("username must have 3 to 50 characters: letters, digits or underscore");
        }

        String email = request.getEmail() == null ? null : request.getEmail().trim();
        if (email == null || email.isEmpty()) {
            errors.add("email is required");
        } else if (email.length() > MAX_EMAIL_LENGTH || !EMAIL.matcher(email).matches()) {
            errors.add("email is not valid");
        }

        String password = request.getPassword();
        if (password == null || password.length() < MIN_PASSWORD_LENGTH
                || password.length() > MAX_PASSWORD_LENGTH) {
            errors.add("password must have " + MIN_PASSWORD_LENGTH + " to "
                    + MAX_PASSWORD_LENGTH + " characters");
        }
        return errors;
    }
}
