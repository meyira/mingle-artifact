//
// Copyright 2024 Signal Messenger, LLC.
// SPDX-License-Identifier: AGPL-3.0-only
//

package org.signal.libsignal.net;

import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.MoreExecutors;
import com.google.protobuf.InvalidProtocolBufferException;
import io.grpc.ManagedChannel;
import io.grpc.okhttp.OkHttpChannelBuilder;

import java.io.IOException;
import java.util.concurrent.ExecutionException;

import kt_query.KeyTransparencyQueryServiceGrpc;
import kt_query.KtQuery;
import org.signal.libsignal.internal.CompletableFuture;
import org.signal.libsignal.internal.Native;
import org.signal.libsignal.keytrans.Store;

public class KeyTransparencyClientGrpc {
  // FIXME: tends to be orphaned (Previous channel {0} was garbage collected without being shut down)
  private final ManagedChannel channel;
  private final KeyTransparencyQueryServiceGrpc.KeyTransparencyQueryServiceFutureStub stub;
  private static final String LOCAL_KT_SERVER_HOST = "localhost";
  private static final int LOCAL_KT_SERVER_PORT = 8080;

  public KeyTransparencyClientGrpc() {
    this(LOCAL_KT_SERVER_HOST, LOCAL_KT_SERVER_PORT);
  }

  public KeyTransparencyClientGrpc(
    String host,
    int port) {
    this.channel = OkHttpChannelBuilder.forAddress(host, port).usePlaintext().build();
    this.stub = KeyTransparencyQueryServiceGrpc.newFutureStub(channel);
  }
  public CompletableFuture<KtQuery.DistinguishedResponse> fetchDistinguishedGrpc(Store store)
    throws ExecutionException, InterruptedException, InvalidProtocolBufferException {
    KtQuery.DistinguishedRequest request;
    if (store.getLastDistinguishedTreeHead().isPresent()) {
      var lastSize = signal.keytrans.Store.StoredTreeHead.parseFrom(store.getLastDistinguishedTreeHead().get());

      request = KtQuery
        .DistinguishedRequest.newBuilder()
        .setLast(lastSize.getTreeHead().getTreeSize())
        .build();
    } else {
      request = KtQuery
        .DistinguishedRequest.newBuilder()
        .build();
    }

    ListenableFuture<KtQuery.DistinguishedResponse> guavaFuture = stub.distinguished(request);
    CompletableFuture<KtQuery.DistinguishedResponse> future = new CompletableFuture<>();

    Futures.addCallback(guavaFuture, new FutureCallback<>() {
      @Override
      public void onSuccess(KtQuery.DistinguishedResponse result) {
        future.complete(result);
      }

      @Override
      public void onFailure(Throwable t) {
        future.completeExceptionally(t);
      }
    }, MoreExecutors.directExecutor());

    return future.thenApply(distinguishedResponse -> {
      try {
        verifyDistinguishedResponse(distinguishedResponse, store);
      } catch (IOException e) {
        throw new RuntimeException(e);
      }
      return distinguishedResponse;
    });
  }

  /**
   * Calls the verification methods residing in libsignal-keytrans/verify.rs and saves it in the Store as StoredTreeHead
   * @param distinguishedResponse
   * @param store
   * @throws IOException
   */
  public void verifyDistinguishedResponse(KtQuery.DistinguishedResponse distinguishedResponse, Store store)
    throws IOException {
    var distinguishedResponseBytes = distinguishedResponse.toByteArray();

    var storedTreeHeadBytes = Native.Verify_Distinguished_Response(
      distinguishedResponseBytes,
      store.getLastDistinguishedTreeHead().orElse(null)
    );

    var sth = signal.keytrans.Store.StoredTreeHead.parseFrom(storedTreeHeadBytes);
    // only temporarily asserting directly for demonstration purposes
    assert !sth.getRoot().isEmpty();

    store.setLastDistinguishedTreeHead(sth.toByteArray().clone());

    var consistencyProofSize = distinguishedResponse.getTreeHead().getLastList().stream()
      .mapToInt(com.google.protobuf.ByteString::size)
      .sum();

    System.out.println("Size of consistency proofs (w/o sth): " + consistencyProofSize); // mostly larger than the STH (400+ bytes)
    System.out.println("Stored tree head: " + storedTreeHeadBytes.length); // around 252 bytes
    System.out.println("root hash + size: " + sth.getRoot().size() + " + " + Long.BYTES); // 40 bytes.
  }
}
