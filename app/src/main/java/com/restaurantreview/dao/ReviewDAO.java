package com.restaurantreview.dao;
 
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
 
import com.restaurantreview.config.DatabaseConnection;
import com.restaurantreview.model.RatingSummary;
import com.restaurantreview.model.Review;
 
/**
 * Data access for the reviews table. All SQL for reviews lives here.
 * Reviews are joined with users and restaurants to also return the
 * username and the restaurant name.
 * Note: there is no delete method on purpose, reviews are never removed.
 */
public class ReviewDAO {
 
    private static final String SELECT_BASE =
            "SELECT rv.id, rv.user_id, u.username, rv.restaurant_id, "
            + "r.name AS restaurant_name, rv.rating, rv.comment, "
            + "rv.created_at, rv.updated_at "
            + "FROM reviews rv "
            + "JOIN users u ON u.id = rv.user_id "
            + "JOIN restaurants r ON r.id = rv.restaurant_id";
 
    /**
     * Returns reviews, newest first. Every filter is optional:
     * pass null to ignore it.
     */
    public List<Review> findAll(Integer restaurantId, Integer userId, Integer minRating)
            throws SQLException {
 
        StringBuilder sql = new StringBuilder(SELECT_BASE).append(" WHERE 1 = 1");
        List<Object> parameters = new ArrayList<>();
 
        if (restaurantId != null) {
            sql.append(" AND rv.restaurant_id = ?");
            parameters.add(restaurantId);
        }
        if (userId != null) {
            sql.append(" AND rv.user_id = ?");
            parameters.add(userId);
        }
        if (minRating != null) {
            sql.append(" AND rv.rating >= ?");
            parameters.add(minRating);
        }
        sql.append(" ORDER BY rv.created_at DESC, rv.id DESC");
 
        List<Review> reviews = new ArrayList<>();
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql.toString())) {
 
            for (int i = 0; i < parameters.size(); i++) {
                statement.setObject(i + 1, parameters.get(i));
            }
            try (ResultSet resultSet = statement.executeQuery()) {
                while (resultSet.next()) {
                    reviews.add(mapRow(resultSet));
                }
            }
        }
        return reviews;
    }
 
    /** Returns the review with the given id, or null if it does not exist. */
    public Review findById(int id) throws SQLException {
        String sql = SELECT_BASE + " WHERE rv.id = ?";
 
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
     * Inserts a new review and returns its generated id.
     * MySQL error 1062 (duplicate user + restaurant) and 1452 (user or
     * restaurant does not exist) are thrown as SQLException; the resource
     * turns them into 409 and 400 responses.
     */
    public int create(Review review) throws SQLException {
        String sql = "INSERT INTO reviews (user_id, restaurant_id, rating, comment) "
                + "VALUES (?, ?, ?, ?)";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement =
                     connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
 
            statement.setInt(1, review.getUserId());
            statement.setInt(2, review.getRestaurantId());
            statement.setInt(3, review.getRating());
            statement.setString(4, review.getComment());
            statement.executeUpdate();
 
            try (ResultSet keys = statement.getGeneratedKeys()) {
                if (keys.next()) {
                    return keys.getInt(1);
                }
            }
        }
        throw new SQLException("Review was inserted but no id was returned");
    }
 
    /** Updates only the rating and the comment of an existing review. */
    public void update(int id, int rating, String comment) throws SQLException {
        String sql = "UPDATE reviews SET rating = ?, comment = ? WHERE id = ?";
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
 
            statement.setInt(1, rating);
            statement.setString(2, comment);
            statement.setInt(3, id);
            statement.executeUpdate();
        }
    }
 
    /**
     * Returns the rating statistics of a restaurant (average, total and how
     * many reviews gave each star). A restaurant without reviews gives 0 / 0.0.
     * The restaurantName is filled by the resource.
     */
    public RatingSummary getRatingSummary(int restaurantId) throws SQLException {
        String sql = "SELECT rating, COUNT(*) AS total FROM reviews "
                + "WHERE restaurant_id = ? GROUP BY rating";
        Map<Integer, Integer> countsByRating = new HashMap<>();
 
        try (Connection connection = DatabaseConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
 
            statement.setInt(1, restaurantId);
            try (ResultSet resultSet = statement.executeQuery()) {
                while (resultSet.next()) {
                    countsByRating.put(resultSet.getInt("rating"), resultSet.getInt("total"));
                }
            }
        }
        return RatingSummary.fromCounts(restaurantId, countsByRating);
    }
 
    private Review mapRow(ResultSet resultSet) throws SQLException {
        Review review = new Review();
        review.setId(resultSet.getInt("id"));
        review.setUserId(resultSet.getInt("user_id"));
        review.setUsername(resultSet.getString("username"));
        review.setRestaurantId(resultSet.getInt("restaurant_id"));
        review.setRestaurantName(resultSet.getString("restaurant_name"));
        review.setRating(resultSet.getInt("rating"));
        review.setComment(resultSet.getString("comment"));
 
        Timestamp createdAt = resultSet.getTimestamp("created_at");
        Timestamp updatedAt = resultSet.getTimestamp("updated_at");
        review.setCreatedAt(createdAt == null ? null : createdAt.toLocalDateTime());
        review.setUpdatedAt(updatedAt == null ? null : updatedAt.toLocalDateTime());
        return review;
    }
}