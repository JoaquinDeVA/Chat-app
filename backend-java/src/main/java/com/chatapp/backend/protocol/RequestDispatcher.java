package com.chatapp.backend.protocol;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Routes a raw message ({@code RequestName{json}}) to the matching {@link RequestHandler}.
 *
 * <p>It never throws: malformed or unknown requests and unexpected failures are answered with a
 * valid JSON error object, so the peer always gets a reply it can parse.
 */
@Component
public class RequestDispatcher {

  private static final Logger log = LoggerFactory.getLogger(RequestDispatcher.class);

  private final Map<String, RequestHandler> handlers;
  private final ObjectMapper mapper;

  public RequestDispatcher(List<RequestHandler> handlers, ObjectMapper mapper) {
    this.handlers =
        handlers.stream()
            .collect(
                Collectors.toMap(
                    handler -> handler.requestName().toUpperCase(Locale.ROOT),
                    Function.identity()));
    this.mapper = mapper;
  }

  /**
   * Answers a message.
   *
   * @param raw the message without its end-of-transmission byte
   * @return the JSON reply
   */
  public String dispatch(String raw) {
    int bodyStart = raw.indexOf('{');
    if (bodyStart < 0) {
      return error("Invalid format: expected RequestName{json}");
    }

    String name = raw.substring(0, bodyStart).trim().toUpperCase(Locale.ROOT);
    RequestHandler handler = handlers.get(name);
    if (handler == null) {
      return error("Unknown request: " + raw.substring(0, bodyStart).trim());
    }

    try {
      return handler.handle(raw.substring(bodyStart));
    } catch (JsonProcessingException e) {
      log.warn("Invalid body for {}: {}", name, e.getOriginalMessage());
      return error("Invalid request body");
    } catch (RuntimeException e) {
      log.error("Request {} failed", name, e); // the body is not logged: it may hold a password
      return error("Internal error");
    }
  }

  private String error(String message) {
    try {
      return mapper.writeValueAsString(new Responses.Error(message));
    } catch (JsonProcessingException e) {
      return "{\"error\":\"Internal error\"}";
    }
  }
}
