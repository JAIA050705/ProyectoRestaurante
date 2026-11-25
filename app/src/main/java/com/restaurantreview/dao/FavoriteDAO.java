package com.restaurantreview.dao;
 
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
 
import com.restaurantreview.config.DatabaseConnection;
import com.restaurantreview.model.Restaurant;
 
/**
 * Data access for the favorites table (restaurants a user saved).
 */
public class FavoriteDAO {
 
    /** Returns the favorite restaurants of a user, most recently saved first. */
    public List<Restaurant> findRestaurantsByUser(int userId) throws SQLException {
        String sql = "SELECT r.id, r.name, r.cuisine, r.price_range, r.city, r.address "
                + "FROM favorites f "
                + "JOIN restaurants r ON r.id = f.restaurant_id "
                + "WHERE f.user_id = ? "
                + "ORDER BY f.created_at DESC, r.name";
 
        List<Restaurant> restaurants = new ArrayList<>();
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
 
            statement.setInt(1, userId);
            try (ResultSet resultSet = statement.executeQuery()) {
                while (resultSet.next()) {
                    restaurants.add(new Restaurant(
                            resultSet.getInt("id"),
                            resultSet.getString("name"),
                            resultSet.getString("cuisine"),
                            resultSet.getInt("price_range"),
                            resultSet.getString("city"),
                            resultSet.getString("address")));
                }
            }
        }
        return restaurants;
    }
 
    /**
     * Saves a restaurant as favorite of a user.
     * MySQL error 1062 (already a favorite) is thrown as SQLException; the
     * resource turns it into a 409 response.
     */
    public void add(int userId, int restaurantId) throws SQLException {
        String sql = "INSERT INTO favorites (user_id, restaurant_id) VALUES (?, ?)";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
 
            statement.setInt(1, userId);
            statement.setInt(2, restaurantId);
            statement.executeUpdate();
        }
    }
 
    /**
     * Removes a restaurant from the favorites of a user.
     * Returns true if it was a favorite, false if there was nothing to remove.
     */
    public boolean remove(int userId, int restaurantId) throws SQLException {
        String sql = "DELETE FROM favorites WHERE user_id = ? AND restaurant_id = ?";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
 
            statement.setInt(1, userId);
            statement.setInt(2, restaurantId);
            return statement.executeUpdate() > 0;
        }
    }
}