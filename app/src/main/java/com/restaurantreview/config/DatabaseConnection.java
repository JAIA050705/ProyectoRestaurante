package com.restaurantreview.config;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/**
 * Creates connections to the MySQL database.
 * Simple version using DriverManager. Later it can be replaced by a
 * GlassFish connection pool without touching the DAO classes.
 *
 * The connection data is NOT written in the code. It is read from
 * environment variables (or JVM system properties with the same name):
 *   DB_PASSWORD  password of the MySQL user   (required, no default on purpose)
 *   DB_USER      MySQL user                   (default: dev)
 *   DB_URL       JDBC url of the database     (default: local MySQL)
 */
public class DatabaseConnection {

    private static final String DEFAULT_URL =
            "jdbc:mysql://localhost:3306/restaurant_review_db"
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";
    private static final String DEFAULT_USER = "dev";

    private static final String URL = setting("DB_URL", DEFAULT_URL);
    private static final String USER = setting("DB_USER", DEFAULT_USER);
    private static final String PASSWORD = setting("DB_PASSWORD", null);

    private DatabaseConnection() {
        // Utility class, no instances
    }

    public static Connection getConnection() throws SQLException {
        if (PASSWORD == null) {
            // Clear message in server.log instead of a confusing "Access denied"
            throw new SQLException("The environment variable DB_PASSWORD is not set. "
                    + "Set it and restart GlassFish.");
        }
        try {
            // Needed inside application servers so the driver is registered
            Class.forName("com.mysql.cj.jdbc.Driver");
        } catch (ClassNotFoundException e) {
            throw new SQLException("MySQL driver not found", e);
        }
        return DriverManager.getConnection(URL, USER, PASSWORD);
    }

    /** Looks for a JVM property first, then an environment variable, then the default. */
    private static String setting(String name, String defaultValue) {
        String value = System.getProperty(name);
        if (value == null || value.isEmpty()) {
            value = System.getenv(name);
        }
        return (value == null || value.isEmpty()) ? defaultValue : value;
    }
}