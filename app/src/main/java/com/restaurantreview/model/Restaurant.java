package com.restaurantreview.model;
 
/**
 * A restaurant that can be reviewed.
 * priceRange: 1 = $, 2 = $$, 3 = $$$, 4 = $$$$
 */
public class Restaurant {
 
    private int id;
    private String name;
    private String cuisine;
    private int priceRange;
    private String city;
    private String address;
 
    // Empty constructor required for JSON conversion
    public Restaurant() {
    }
 
    public Restaurant(int id, String name, String cuisine, int priceRange,
                      String city, String address) {
        this.id = id;
        this.name = name;
        this.cuisine = cuisine;
        this.priceRange = priceRange;
        this.city = city;
        this.address = address;
    }
 
    public int getId() {
        return id;
    }
 
    public void setId(int id) {
        this.id = id;
    }
 
    public String getName() {
        return name;
    }
 
    public void setName(String name) {
        this.name = name;
    }
 
    public String getCuisine() {
        return cuisine;
    }
 
    public void setCuisine(String cuisine) {
        this.cuisine = cuisine;
    }
 
    public int getPriceRange() {
        return priceRange;
    }
 
    public void setPriceRange(int priceRange) {
        this.priceRange = priceRange;
    }
 
    public String getCity() {
        return city;
    }
 
    public void setCity(String city) {
        this.city = city;
    }
 
    public String getAddress() {
        return address;
    }
 
    public void setAddress(String address) {
        this.address = address;
    }
}