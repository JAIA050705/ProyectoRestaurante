package com.restaurantreview.security;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Base64;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * Creates and validates JSON Web Tokens (JWT) signed with HS256.
 *
 * A JWT has 3 parts separated by dots:  header.payload.signature
 *   header    = {"alg":"HS256","typ":"JWT"}
 *   payload   = claims: sub (user id), username, iat (issued at), exp (expires at)
 *   signature = HMAC-SHA256(secret, header + "." + payload)
 * Header and payload are only Base64URL encoded (anybody can read them), the
 * signature is what proves that nobody changed them.
 *
 * The secret is read from the JWT_SECRET system property or environment
 * variable. It must NOT be written in the code of a real deployment.
 */
public final class JwtService {

    private static final Logger LOGGER = Logger.getLogger(JwtService.class.getName());

    public static final long DEFAULT_TTL_SECONDS = 3600;   // tokens last 1 hour

    // Only for local development. Set JWT_SECRET (32+ characters) on a real server.
    private static final String DEV_SECRET = "dev-only-secret-change-me-before-deploying-1234567890";
    private static final byte[] SECRET = loadSecret();

    private static final String HEADER = base64Url("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
    private static final Pattern SUB = Pattern.compile("\"sub\":\"(\\d+)\"");
    private static final Pattern EXP = Pattern.compile("\"exp\":(\\d+)");

    private JwtService() {
        // Utility class, no instances
    }

    /** Creates a token for the user, valid for DEFAULT_TTL_SECONDS. */
    public static String createToken(int userId, String username) {
        return createToken(userId, username, DEFAULT_TTL_SECONDS);
    }

    /** Creates a token that expires in ttlSeconds (a negative value gives an already expired token). */
    public static String createToken(int userId, String username, long ttlSeconds) {
        long now = Instant.now().getEpochSecond();
        String safeUsername = username.replace("\\", "\\\\").replace("\"", "\\\"");
        String payload = "{\"sub\":\"" + userId + "\",\"username\":\"" + safeUsername
                + "\",\"iat\":" + now + ",\"exp\":" + (now + ttlSeconds) + "}";

        String signingInput = HEADER + "." + base64Url(payload.getBytes(StandardCharsets.UTF_8));
        return signingInput + "." + sign(signingInput);
    }

    /**
     * Validates the token and returns the user id it belongs to, or null if the
     * token is malformed, has a wrong signature or is expired.
     */
    public static Integer verifyToken(String token) {
        if (token == null) {
            return null;
        }
        String[] parts = token.split("\\.", -1);
        if (parts.length != 3) {
            return null;
        }
        // Only our own header is accepted (this also rejects "alg":"none" tokens)
        if (!HEADER.equals(parts[0])) {
            return null;
        }
        // Check the signature BEFORE trusting anything in the payload
        String expectedSignature = sign(parts[0] + "." + parts[1]);
        boolean validSignature = MessageDigest.isEqual(
                expectedSignature.getBytes(StandardCharsets.US_ASCII),
                parts[2].getBytes(StandardCharsets.US_ASCII));
        if (!validSignature) {
            return null;
        }

        try {
            String payload = new String(Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8);
            Matcher exp = EXP.matcher(payload);
            Matcher sub = SUB.matcher(payload);
            if (!exp.find() || !sub.find()) {
                return null;
            }
            if (Long.parseLong(exp.group(1)) <= Instant.now().getEpochSecond()) {
                return null;   // expired
            }
            return Integer.valueOf(sub.group(1));
        } catch (IllegalArgumentException e) {
            // Bad Base64 or a number that is too large
            return null;
        }
    }

    private static String sign(String signingInput) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(SECRET, "HmacSHA256"));
            return base64Url(mac.doFinal(signingInput.getBytes(StandardCharsets.UTF_8)));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("HMAC-SHA256 is not available", e);
        }
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static byte[] loadSecret() {
        String secret = System.getProperty("JWT_SECRET");
        if (secret == null || secret.isEmpty()) {
            secret = System.getenv("JWT_SECRET");
        }
        if (secret == null || secret.length() < 32) {
            LOGGER.warning("JWT_SECRET is missing or shorter than 32 characters: using the "
                    + "development secret. Do NOT deploy like this.");
            secret = DEV_SECRET;
        }
        return secret.getBytes(StandardCharsets.UTF_8);
    }
}
