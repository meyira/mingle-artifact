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
 * Filters DynamoDb E164 record updates for the subset relevant to key transparency, outputting them to Kinesis
 */
public class FilterE164UpdatesHandler extends AbstractUpdatesHandler<E164Constraint> {

  public FilterE164UpdatesHandler() {
    super();
  }

  @VisibleForTesting
  FilterE164UpdatesHandler(final KinesisClient kinesisClient, final String kinesisOutputStream) {
    super(kinesisClient, kinesisOutputStream);
  }

  E164Constraint fromDynamoDbImage(final Map<String, AttributeValue> image) {
    return E164Constraint.fromItem(image);
  }

  KinesisRecord<E164Constraint> toKinesisRecord(final @Nullable E164Constraint prev, final @Nullable E164Constraint next) {
    return new E164Constraint.Pair(prev, next);
  }
}

