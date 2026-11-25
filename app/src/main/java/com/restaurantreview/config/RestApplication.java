package com.restaurantreview.config;
 
import jakarta.ws.rs.ApplicationPath;
import jakarta.ws.rs.core.Application;
 
/**
 * Entry point of the REST API.
 * Every resource class annotated with @Path is published under /api.
 */
@ApplicationPath("/api")
public class RestApplication extends Application {
}
 