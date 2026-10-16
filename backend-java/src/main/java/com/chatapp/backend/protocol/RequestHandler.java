package com.chatapp.backend.protocol;

import com.fasterxml.jackson.core.JsonProcessingException;

/** Handles one kind of request: parses its JSON body, runs it and returns the JSON reply. */
public interface RequestHandler {

  /** Name that selects this handler (the header before the JSON body), compared in upper case. */
  String requestName();

  /**
   * Handles a request.
   *
   * @param json the JSON body of the request
   * @return the JSON reply
   * @throws JsonProcessingException if the body is not valid for this request
   */
  String handle(String json) throws JsonProcessingException;
}
