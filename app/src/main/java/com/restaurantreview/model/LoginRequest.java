package com.restaurantreview.model;

/**
 * Body of POST /auth/login.
 */
public class LoginRequest {

    private String username;
    private String password;

    // Empty constructor required for JSON conversion
    public LoginRequest() {
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }
}
