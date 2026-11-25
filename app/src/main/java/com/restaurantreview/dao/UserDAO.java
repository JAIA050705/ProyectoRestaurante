package com.restaurantreview.dao;
 
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Timestamp;

import com.restaurantreview.config.DatabaseConnection;
import com.restaurantreview.model.User;

/**
 * Data access for the users table.
 */
public class UserDAO {

    /**
     * What the login needs from the database: id, username and password hash.
     * It is NOT a model sent to clients, so the hash can never leak in a response.
     */
    public static final class Credentials {
        private final int id;
        private final String username;
        private final String passwordHash;

        public Credentials(int id, String username, String passwordHash) {
            this.id = id;
            this.username = username;
            this.passwordHash = passwordHash;
        }

        public int getId() {
            return id;
        }

        public String getUsername() {
            return username;
        }

        public String getPasswordHash() {
            return passwordHash;
        }
    }

    /** Returns true if a user with the given id exists. */
    public boolean exists(int id) throws SQLException {
        String sql = "SELECT 1 FROM users WHERE id = ?";

        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {

            statement.setInt(1, id);
            try (ResultSet resultSet = statement.executeQuery()) {
                return resultSet.next();
            }
        }
    }

    /** Returns the public data of a user, or null if it does not exist. */
    public User findById(int id) throws SQLException {
        String sql = "SELECT id, username, email, created_at FROM users WHERE id = ?";

        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {

            statement.setInt(1, id);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    Timestamp createdAt = resultSet.getTimestamp("created_at");
                    return new User(
                            resultSet.getInt("id"),
                            resultSet.getString("username"),
                            resultSet.getString("email"),
                            createdAt == null ? null : createdAt.toLocalDateTime());
                }
            }
        }
        return null;
    }

    /** Returns the login data of a username, or null if it does not exist. */
    public Credentials findCredentials(String username) throws SQLException {
        String sql = "SELECT id, username, password_hash FROM users WHERE username = ?";

        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {

            statement.setString(1, username);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return new Credentials(
                            resultSet.getInt("id"),
                            resultSet.getString("username"),
                            resultSet.getString("password_hash"));
                }
            }
        }
        return null;
    }

    /**
     * Inserts a new user and returns its generated id.
     * MySQL error 1062 (username or email already registered) is thrown as
     * SQLException; the resource turns it into a 409 response.
     */
    public int create(String username, String email, String passwordHash) throws SQLException {
        String sql = "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)";

        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement =
                     connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {

            statement.setString(1, username);
            statement.setString(2, email);
            statement.setString(3, passwordHash);
            statement.executeUpdate();

            try (ResultSet keys = statement.getGeneratedKeys()) {
                if (keys.next()) {
                    return keys.getInt(1);
                }
            }
        }
        throw new SQLException("User was inserted but no id was returned");
    }
}
