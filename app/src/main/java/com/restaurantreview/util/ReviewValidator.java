package com.restaurantreview.util;
 
import java.util.ArrayList;
import java.util.List;
 
import com.restaurantreview.model.Review;
 
/**
 * Business rules for reviews. Pure logic (no database, no server), so it is
 * easy to unit test later.
 * Each method returns the list of problems found; an empty list means valid.
 */
public final class ReviewValidator {
 
    public static final int MIN_RATING = 1;
    public static final int MAX_RATING = 5;
    public static final int MAX_COMMENT_LENGTH = 1000;
 
    private ReviewValidator() {
        // Utility class, no instances
    }
 
    /** Rules for a new review: who wrote it, about what, plus the content. */
    public static List<String> validateForCreate(Review review) {
        List<String> errors = new ArrayList<>();
        if (review.getUserId() <= 0) {
            errors.add("userId is required and must be a positive number");
        }
        if (review.getRestaurantId() <= 0) {
            errors.add("restaurantId is required and must be a positive number");
        }
        errors.addAll(validateContent(review));
        return errors;
    }
 
    /** Rules for an update: only the rating and the comment can change. */
    public static List<String> validateForUpdate(Review review) {
        return validateContent(review);
    }
 
    private static List<String> validateContent(Review review) {
        List<String> errors = new ArrayList<>();
        if (review.getRating() < MIN_RATING || review.getRating() > MAX_RATING) {
            errors.add("rating must be between " + MIN_RATING + " and " + MAX_RATING);
        }
        if (review.getComment() != null
                && review.getComment().length() > MAX_COMMENT_LENGTH) {
            errors.add("comment cannot be longer than " + MAX_COMMENT_LENGTH + " characters");
        }
        return errors;
    }
}
 