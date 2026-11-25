package com.restaurantreview.model;

/**
 * Answer of a successful login: the JWT and who it belongs to.
 * The client sends the token in every protected request:
 *   Authorization: Bearer <token>
 */
public class LoginResponse {

    private String token;
    private String tokenType = "Bearer";
    private long expiresIn;      // seconds until the token expires
    private User user;

    // Empty constructor required for JSON conversion
    public LoginResponse() {
    }

    public LoginResponse(String token, long expiresIn, User user) {
        this.token = token;
        this.expiresIn = expiresIn;
        this.user = user;
    }

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }

    public String getTokenType() {
        return tokenType;
    }

    public void setTokenType(String tokenType) {
        this.tokenType = tokenType;
    }

    public long getExpiresIn() {
        return expiresIn;
    }

    public void setExpiresIn(long expiresIn) {
        this.expiresIn = expiresIn;
    }

    public User getUser() {
        return user;
    }

    public void setUser(User user) {
        this.user = user;
    }
}
