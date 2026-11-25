package com.restaurantreview.exception;
 
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
 
import jakarta.ws.rs.ProcessingException;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;
 
/**
 * Turns a request body that is not valid JSON into a 400 Bad Request
 * instead of a 500 Internal Server Error.
 * Any other processing problem still answers 500 and is written to the log.
 */
@Provider
public class MalformedJsonMapper implements ExceptionMapper<ProcessingException> {
 
    private static final Logger LOGGER =
            Logger.getLogger(MalformedJsonMapper.class.getName());
 
    @Override
    public Response toResponse(ProcessingException exception) {
        if (causedByJsonParsing(exception)) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .type(MediaType.APPLICATION_JSON)
                    .entity(Map.of("error", "Request body is not valid JSON"))
                    .build();
        }
        LOGGER.log(Level.SEVERE, "Request processing error", exception);
        return Response.status(Response.Status.INTERNAL_SERVER_ERROR)
                .type(MediaType.APPLICATION_JSON)
                .entity(Map.of("error", "Internal server error"))
                .build();
    }
 
    /** True if any exception in the chain comes from a JSON library (jakarta.json.*). */
    private boolean causedByJsonParsing(Throwable throwable) {
        Throwable current = throwable;
        while (current != null) {
            if (current.getClass().getName().startsWith("jakarta.json")) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }
}