/*
 * Copyright 2026 Signal Messenger, LLC
 * SPDX-License-Identifier: AGPL-3.0-only
 */

package org.signal.lambda;


import javax.annotation.Nullable;

public interface KinesisRecord<T> {
  @Nullable
  T prev();
  @Nullable
  T next();

  String partitionKey();
}
