/*
 * Copyright 2026 Signal Messenger, LLC
 * SPDX-License-Identifier: AGPL-3.0-only
 */

package org.signal.lambda;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.events.DynamodbEvent;
import com.amazonaws.services.lambda.runtime.events.StreamsEventResponse;
import com.amazonaws.services.lambda.runtime.tests.EventLoader;
import java.io.IOException;
import java.util.Base64;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.mockito.ArgumentCaptor;
import software.amazon.awssdk.core.SdkBytes;
import software.amazon.awssdk.services.kinesis.KinesisClient;
import software.amazon.awssdk.services.kinesis.model.PutRecordRequest;

// Modeled after https://aws.amazon.com/blogs/opensource/testing-aws-lambda-functions-written-in-java/
class FilterUsernameUpdatesHandlerTest {
  private static byte[] b64(String b) {
    return Base64.getDecoder().decode(b);
  }

  static final byte[] PREV_ACI = b64("IiIiIiIiIiIiIiIiIiIiIg==");
  static final byte[] NEXT_ACI = b64("BbBbBbBbBbBbBbBbBbBbBg==");
  static final byte[] USERNAME_HASH = b64("EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE=");;

  @ParameterizedTest
  @MethodSource
  void handleRequest(final String filename, final UsernameConstraint.Pair expected) {
    final DynamodbEvent event = EventLoader.loadDynamoDbEvent(filename);
    KinesisClient mockClient = mock(KinesisClient.class);
    FilterUsernameUpdatesHandler handler = new FilterUsernameUpdatesHandler(mockClient, "mystream");
    Context contextMock = mock(Context.class);
    final StreamsEventResponse streamsEventResponse = handler.handleRequest(event, contextMock);
    assertTrue(streamsEventResponse.getBatchItemFailures().isEmpty());
    ArgumentCaptor<PutRecordRequest> captor = ArgumentCaptor.forClass(PutRecordRequest.class);
    verify(mockClient, times(expected == null ? 0 : 1)).putRecord(captor.capture());
    if (expected != null) {
      List<UsernameConstraint.Pair> usernamePairs = captor.getAllValues().stream().map(c -> mapWithoutException(c.data())).toList();
      assertEquals(expected, usernamePairs.get(0));
    }
  }

  private static Stream<Arguments> handleRequest() {
    return Stream.of(
        Arguments.of(
            "username/testevent_creation.json",
            new UsernameConstraint.Pair(
                null,
                new UsernameConstraint(USERNAME_HASH, PREV_ACI))),
        Arguments.of(
            "username/testevent_deletion.json",
            new UsernameConstraint.Pair(
                new UsernameConstraint(USERNAME_HASH, PREV_ACI),
                null)),
        Arguments.of(
            "username/testevent_nochange.json", null),
        Arguments.of(
            "username/testevent_modify.json",
            new UsernameConstraint.Pair(
                new UsernameConstraint(USERNAME_HASH, PREV_ACI),
                new UsernameConstraint(USERNAME_HASH, NEXT_ACI))));
  }

  UsernameConstraint.Pair mapWithoutException(SdkBytes in) {
    try {
      return FilterE164UpdatesHandler.OBJECT_MAPPER.readValue(in.asInputStream(), UsernameConstraint.Pair.class);
    } catch (IOException e) {
      throw new RuntimeException("mapping", e);
    }
  }
}
