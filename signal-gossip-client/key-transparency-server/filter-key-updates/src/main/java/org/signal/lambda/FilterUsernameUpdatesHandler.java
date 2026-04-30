/*
 * Copyright 2026 Signal Messenger, LLC
 * SPDX-License-Identifier: AGPL-3.0-only
 */

package org.signal.lambda;

import com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue;
import com.google.common.annotations.VisibleForTesting;
import software.amazon.awssdk.services.kinesis.KinesisClient;

import javax.annotation.Nullable;
import java.util.Map;

/**
 * Filters DynamoDb username hash record updates for the subset relevant to key transparency, outputting them to Kinesis
 */
public class FilterUsernameUpdatesHandler extends AbstractUpdatesHandler<UsernameConstraint> {

  public FilterUsernameUpdatesHandler() {
    super();
  }

  @VisibleForTesting
  FilterUsernameUpdatesHandler(final KinesisClient kinesisClient, final String kinesisOutputStream) {
    super(kinesisClient, kinesisOutputStream);
  }

  UsernameConstraint fromDynamoDbImage(final Map<String, AttributeValue> image) {
    return UsernameConstraint.fromItem(image);
  }

  KinesisRecord<UsernameConstraint> toKinesisRecord(final @Nullable UsernameConstraint prev, final @Nullable UsernameConstraint next) {
    return new UsernameConstraint.Pair(prev, next);
  }
}

