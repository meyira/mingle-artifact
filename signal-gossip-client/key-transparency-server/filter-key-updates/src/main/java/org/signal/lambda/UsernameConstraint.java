/*
 * Copyright 2026 Signal Messenger, LLC
 * SPDX-License-Identifier: AGPL-3.0-only
 */

package org.signal.lambda;

import com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.base.Preconditions;

import javax.annotation.Nullable;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Map;

record UsernameConstraint(
    byte[] usernameHash,
    byte[] aci) {

  @VisibleForTesting
  static final String KEY_USERNAME_HASH = "N";
  @VisibleForTesting
  static final String ATTR_ACCOUNT_UUID = "U";

  @Override
  public boolean equals(final Object o) {
    if (this == o)
      return true;
    if (o == null || getClass() != o.getClass())
      return false;
    UsernameConstraint usernameConstraint = (UsernameConstraint) o;
    return Arrays.equals(usernameHash, usernameConstraint.usernameHash) &&
        Arrays.equals(aci, usernameConstraint.aci);
  }

  public record Pair(@Nullable UsernameConstraint prev, @Nullable UsernameConstraint next) implements KinesisRecord<UsernameConstraint> {

    /** Return a partition key used by Kinesis to group distributed updates.
     *
     * @return a string that Kinesis uses to group distributed updates. Updates to the
     * same username hash are ordered. Updates to different username hashes may go to different shards in the case
     * where our Kinesis output is sharded, and ordering across shards cannot be guaranteed.
     */
    public String partitionKey() {
      final byte[] usernameHash = prev != null ? prev.usernameHash : next.usernameHash;
      return HexFormat.of().formatHex(usernameHash);
    }
  }

  static UsernameConstraint fromItem(Map<String, AttributeValue> item) {
    Preconditions.checkNotNull(item.get(KEY_USERNAME_HASH));
    Preconditions.checkNotNull(item.get(ATTR_ACCOUNT_UUID));

    final byte[] usernameHash = new byte[32];

    final AttributeValue usernameHashAv = item.get(KEY_USERNAME_HASH);
    usernameHashAv.getB().get(usernameHash);

    final byte[] uuid = new byte[16];
    item.get(ATTR_ACCOUNT_UUID).getB().get(uuid);

    return new UsernameConstraint(usernameHash, uuid);
  }
}
