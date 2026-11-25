package com.restaurantreview.util;
 
import java.util.ArrayList;
import java.util.List;
 
import com.restaurantreview.model.Restaurant;
 
/**
 * Business rules for restaurants. Pure logic (no database, no server), so it
 * is easy to unit test later.
 * Returns the list of problems found; an empty list means valid.
 * Limits match the column sizes of the restaurants table.
 */
public final class RestaurantValidator {
 
    public static final int MAX_NAME_LENGTH = 100;
    public static final int MAX_CUISINE_LENGTH = 50;
    public static final int MAX_CITY_LENGTH = 80;
    public static final int MAX_ADDRESS_LENGTH = 150;
    public static final int MIN_PRICE_RANGE = 1;
    public static final int MAX_PRICE_RANGE = 4;
 
    private RestaurantValidator() {
        // Utility class, no instances
    }
 
    public static List<String> validateForCreate(Restaurant restaurant) {
        List<String> errors = new ArrayList<>();
        checkText(errors, "name", restaurant.getName(), MAX_NAME_LENGTH);
        checkText(errors, "cuisine", restaurant.getCuisine(), MAX_CUISINE_LENGTH);
        checkText(errors, "city", restaurant.getCity(), MAX_CITY_LENGTH);
        checkText(errors, "address", restaurant.getAddress(), MAX_ADDRESS_LENGTH);
 
        if (restaurant.getPriceRange() < MIN_PRICE_RANGE
                || restaurant.getPriceRange() > MAX_PRICE_RANGE) {
            errors.add("priceRange must be between " + MIN_PRICE_RANGE
                    + " and " + MAX_PRICE_RANGE);
        }
        return errors;
    }
 
    /** A required text field: not null, not blank, not longer than the limit. */
    private static void checkText(List<String> errors, String field,
                                  String value, int maxLength) {
        if (value == null || value.trim().isEmpty()) {
            errors.add(field + " is required");
        } else if (value.trim().length() > maxLength) {
            errors.add(field + " cannot be longer than " + maxLength + " characters");
        }
    }
}
 