package com.restaurantreview.dao;
 
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
 
import com.restaurantreview.config.DatabaseConnection;
import com.restaurantreview.model.Restaurant;
 
/**
 * Data access for the restaurants table. All SQL for restaurants lives here.
 */
public class RestaurantDAO {
 
    private static final String SELECT_COLUMNS =
            "SELECT id, name, cuisine, price_range, city, address FROM restaurants";
 
    /** Returns every restaurant, ordered by name. */
    public List<Restaurant> findAll() throws SQLException {
        List<Restaurant> restaurants = new ArrayList<>();
        String sql = SELECT_COLUMNS + " ORDER BY name";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql);
             ResultSet resultSet = statement.executeQuery()) {
 
            while (resultSet.next()) {
                restaurants.add(mapRow(resultSet));
            }
        }
        return restaurants;
    }
 
    /** Returns the restaurant with the given id, or null if it does not exist. */
    public Restaurant findById(int id) throws SQLException {
        String sql = SELECT_COLUMNS + " WHERE id = ?";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
 
            statement.setInt(1, id);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return mapRow(resultSet);
                }
            }
        }
        return null;
    }
 
    /**
     * Inserts a new restaurant and returns its generated id.
     * MySQL error 1062 (same name + address already exists) is thrown as
     * SQLException; the resource turns it into a 409 response.
     */
    public int create(Restaurant restaurant) throws SQLException {
        String sql = "INSERT INTO restaurants (name, cuisine, price_range, city, address) "
                + "VALUES (?, ?, ?, ?, ?)";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement =
                     connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
 
            statement.setString(1, restaurant.getName());
            statement.setString(2, restaurant.getCuisine());
            statement.setInt(3, restaurant.getPriceRange());
            statement.setString(4, restaurant.getCity());
            statement.setString(5, restaurant.getAddress());
            statement.executeUpdate();
 
            try (ResultSet keys = statement.getGeneratedKeys()) {
                if (keys.next()) {
                    return keys.getInt(1);
                }
            }
        }
        throw new SQLException("Restaurant was inserted but no id was returned");
    }
 
    private Restaurant mapRow(ResultSet resultSet) throws SQLException {
        return new Restaurant(
                resultSet.getInt("id"),
                resultSet.getString("name"),
                resultSet.getString("cuisine"),
                resultSet.getInt("price_range"),
                resultSet.getString("city"),
                resultSet.getString("address"));
    }
}
 