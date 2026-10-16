package com.chatapp.backend.protocol;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.junit.jupiter.api.Test;

class RequestDispatcherTest {

  private final ObjectMapper mapper = new ObjectMapper();

  private RequestHandler handler(String name, java.util.function.Function<String, String> body) {
    return new RequestHandler() {
      @Override
      public String requestName() {
        return name;
      }

      @Override
      public String handle(String json) throws JsonProcessingException {
        return body.apply(json);
      }
    };
  }

  private JsonNode json(String reply) throws Exception {
    return mapper.readTree(reply); // fails the test if the reply is not valid JSON
  }

  @Test
  void routesByNameIgnoringCaseAndSurroundingSpaces() {
    RequestDispatcher dispatcher =
        new RequestDispatcher(List.of(handler("AddUserRequest", body -> "ok:" + body)), mapper);

    assertThat(dispatcher.dispatch("AddUserRequest{\"a\":1}")).isEqualTo("ok:{\"a\":1}");
    assertThat(dispatcher.dispatch("ADDUSERREQUEST {\"a\":1}")).isEqualTo("ok:{\"a\":1}");
    assertThat(dispatcher.dispatch("  adduserrequest\n{\"a\":1}")).isEqualTo("ok:{\"a\":1}");
  }

  @Test
  void aMessageWithoutABodyGetsAJsonError() throws Exception {
    RequestDispatcher dispatcher = new RequestDispatcher(List.of(), mapper);
    assertThat(json(dispatcher.dispatch("no body here")).get("error").asText()).contains("Invalid format");
  }

  @Test
  void anUnknownRequestGetsAJsonErrorEvenIfItsNameHasQuotes() throws Exception {
    // Regression: errors used to be built by string concatenation, which produced invalid JSON
    // whenever the text contained a quote.
    RequestDispatcher dispatcher = new RequestDispatcher(List.of(), mapper);
    JsonNode reply = json(dispatcher.dispatch("Evil\"Name{\"a\":1}"));
    assertThat(reply.get("error").asText()).isEqualTo("Unknown request: Evil\"Name");
  }

  @Test
  void anInvalidBodyGetsAJsonError() throws Exception {
    RequestDispatcher dispatcher =
        new RequestDispatcher(
            List.of(handler("X", body -> { throw new IllegalStateException("never"); })), mapper);
    RequestDispatcher parsing =
        new RequestDispatcher(
            List.of(new JsonHandler<>("Y", Requests.Auth.class, request -> request, mapper)), mapper);
    assertThat(json(parsing.dispatch("Y{not json}")).get("error").asText()).isEqualTo("Invalid request body");
    assertThat(dispatcher).isNotNull();
  }

  @Test
  void anUnexpectedFailureIsReportedWithoutLeakingDetails() throws Exception {
    RequestDispatcher dispatcher =
        new RequestDispatcher(
            List.of(handler("Boom", body -> { throw new IllegalStateException("secret detail: \"x\""); })),
            mapper);
    JsonNode reply = json(dispatcher.dispatch("Boom{}"));
    assertThat(reply.get("error").asText()).isEqualTo("Internal error");
  }
}
