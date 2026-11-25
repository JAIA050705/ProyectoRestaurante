package com.restaurantreview.model;
 
import java.util.LinkedHashMap;
import java.util.Map;
 
/**
 * Rating statistics of one restaurant, built from its reviews.
 * averageRating is 0.0 and totalReviews is 0 when it has no reviews yet.
 * ratingCounts says how many reviews gave 1, 2, 3, 4 and 5 stars.
 */
public class RatingSummary {
 
    private int restaurantId;
    private String restaurantName;
    private double averageRating;
    private int totalReviews;
    private Map<String, Integer> ratingCounts = new LinkedHashMap<>();
 
    // Empty constructor required for JSON conversion
    public RatingSummary() {
    }
 
    /**
     * Builds the summary from "how many reviews have each rating".
     * Pure logic (no database), so it is easy to unit test later.
     *
     * @param countsByRating key = rating (1 to 5), value = number of reviews
     */
    public static RatingSummary fromCounts(int restaurantId,
                                           Map<Integer, Integer> countsByRating) {
        RatingSummary summary = new RatingSummary();
        summary.restaurantId = restaurantId;
 
        int total = 0;
        int sumOfRatings = 0;
        for (int rating = 1; rating <= 5; rating++) {
            int count = countsByRating.getOrDefault(rating, 0);
            summary.ratingCounts.put(String.valueOf(rating), count);
            total += count;
            sumOfRatings += rating * count;
        }
 
        summary.totalReviews = total;
        if (total > 0) {
            // Round to 2 decimals, e.g. 4.67
            summary.averageRating = Math.round(sumOfRatings * 100.0 / total) / 100.0;
        }
        return summary;
    }
 
    public int getRestaurantId() {
        return restaurantId;
    }
 
    public void setRestaurantId(int restaurantId) {
        this.restaurantId = restaurantId;
    }
 
    public String getRestaurantName() {
        return restaurantName;
    }
 
    public void setRestaurantName(String restaurantName) {
        this.restaurantName = restaurantName;
    }
 
    public double getAverageRating() {
        return averageRating;
    }
 
    public void setAverageRating(double averageRating) {
        this.averageRating = averageRating;
    }
 
    public int getTotalReviews() {
        return totalReviews;
    }
 
    public void setTotalReviews(int totalReviews) {
        this.totalReviews = totalReviews;
    }
 
    public Map<String, Integer> getRatingCounts() {
        return ratingCounts;
    }
 
    public void setRatingCounts(Map<String, Integer> ratingCounts) {
        this.ratingCounts = ratingCounts;
    }
}