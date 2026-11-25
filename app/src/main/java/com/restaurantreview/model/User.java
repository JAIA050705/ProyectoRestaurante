package com.restaurantreview.model;

import java.time.LocalDateTime;

/**
 * Public view of a user. It never contains the password or its hash.
 */
public class User {

    private int id;
    private String username;
    private String email;
    private LocalDateTime createdAt;

    // Empty constructor required for JSON conversion
    public User() {
    }

    public User(int id, String username, String email, LocalDateTime createdAt) {
        this.id = id;
        this.username = username;
        this.email = email;
        this.createdAt = createdAt;
    }

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
