package com.chatapp.backend.protocol;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.function.Function;

/**
 * {@link RequestHandler} built from a request type and a function: it deserializes the body,
 * applies the function and serializes the result.
 *
 * @param <Q> request body type
 */
public final class JsonHandler<Q> implements RequestHandler {

  private final String requestName;
  private final Class<Q> requestType;
  private final Function<Q, ?> action;
  private final ObjectMapper mapper;

  public JsonHandler(
      String requestName, Class<Q> requestType, Function<Q, ?> action, ObjectMapper mapper) {
    this.requestName = requestName;
    this.requestType = requestType;
    this.action = action;
    this.mapper = mapper;
  }

  @Override
  public String requestName() {
    return requestName;
  }

  @Override
  public String handle(String json) throws JsonProcessingException {
    Q request = mapper.readValue(json, requestType);
    return mapper.writeValueAsString(action.apply(request));
  }
}
