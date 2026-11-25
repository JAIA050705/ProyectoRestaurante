package com.restaurantreview.model;
 
import java.time.LocalDateTime;
 
/**
 * A review written by a user about a restaurant.
 * rating goes from 1 to 5.
 * username and restaurantName are read-only extras filled by the DAO
 * (JOIN) so a client app does not need extra requests to show them.
 */
public class Review {
 
    private int id;
    private int userId;
    private String username;
    private int restaurantId;
    private String restaurantName;
    private int rating;
    private String comment;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
 
    // Empty constructor required for JSON conversion
    public Review() {
    }
 
    public int getId() {
        return id;
    }
 
    public void setId(int id) {
        this.id = id;
    }
 
    public int getUserId() {
        return userId;
    }
 
    public void setUserId(int userId) {
        this.userId = userId;
    }
 
    public String getUsername() {
        return username;
    }
 
    public void setUsername(String username) {
        this.username = username;
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
 
    public int getRating() {
        return rating;
    }
 
    public void setRating(int rating) {
        this.rating = rating;
    }
 
    public String getComment() {
        return comment;
    }
 
    public void setComment(String comment) {
        this.comment = comment;
    }
 
    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
 
    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
 
    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
 
    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
 