//
// Copyright 2024 Signal Messenger, LLC.
// SPDX-License-Identifier: AGPL-3.0-only
//

package org.signal.libsignal.net;

import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.MoreExecutors;
import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;
import io.grpc.ManagedChannel;
import io.grpc.okhttp.OkHttpChannelBuilder;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.concurrent.ExecutionException;

import kt_query.KeyTransparencyQueryServiceGrpc;
import kt_query.KtQuery;
import org.jetbrains.annotations.NotNull;
import org.signal.libsignal.internal.CompletableFuture;
import org.signal.libsignal.internal.Native;
import org.signal.libsignal.keytrans.Store;
import org.signal.libsignal.net.KeyTransparency.MonitorMode;
import org.signal.libsignal.protocol.IdentityKey;
import org.signal.libsignal.protocol.ServiceId;
import org.signal.libsignal.zkgroup.internal.ByteArray;

import signal.keytrans.Wire;
import transparency.Transparency;

/**
 * Typed API to access the key transparency subsystem using an existing unauthenticated chat
 * connection.
 *
 * <p>Unlike {@link ChatConnection}, key transparency client does not export "raw" send/receive
 * APIs, and instead uses them internally to implement high-level operations.
 *
 * <p>Note: {@code Store} APIs may be invoked concurrently. Here are possible strategies to make
 * sure there are no thread safety violations:
 *
 * <ul>
 *   <li>Types implementing {@code Store} can be made thread safe
 *   <li>{@link KeyTransparencyClient} operations-completed asynchronous calls-can be serialized.
 * </ul>
 *
 * <p>Example usage:
 *
 * <pre>
 * var net = new Network(Network.Environment.STAGING, "key-transparency-example");
 * var chat = net.connectUnauthChat(new Listener()).get();
 * chat.start();
 *
 * KeyTransparencyClient client = chat.keyTransparencyClient();
 *
 * client.search(aci, identityKey, null, null, null, KT_DATA_STORE).get();
 *
 * </pre>
 */
public class KeyTransparencyClientGrpc {
  // FIXME: tends to be orphaned (Previous channel {0} was garbage collected without being shut down)
  private final ManagedChannel channel;
  private final KeyTransparencyQueryServiceGrpc.KeyTransparencyQueryServiceFutureStub stub;
  private static final String LOCAL_KT_SERVER_HOST = "localhost";
  private static final int LOCAL_KT_SERVER_PORT = 8080;
  // TODO think about a way to maintain a KeyTransparencyStore (Store.java)

  public KeyTransparencyClientGrpc() {
    this(LOCAL_KT_SERVER_HOST, LOCAL_KT_SERVER_PORT);
  }

  public KeyTransparencyClientGrpc(
    String host,
    int port) {
    this.channel = OkHttpChannelBuilder.forAddress(host, port).usePlaintext().build();
    this.stub = KeyTransparencyQueryServiceGrpc.newFutureStub(channel);
  }

  public CompletableFuture<Void> searchGrpc(
    /* @NotNull */ final ServiceId.Aci aci,
    /* @NotNull */ final IdentityKey aciIdentityKey,
                   final String e164,
                   final byte[] unidentifiedAccessKey,
                   final byte[] usernameHash,
                   final Store store) throws InvalidProtocolBufferException, ExecutionException, InterruptedException {

    Optional<byte[]> lastDistinguishedTreeHead = store.getLastDistinguishedTreeHead();
    if (lastDistinguishedTreeHead.isEmpty()) {
      return this.updateDistinguishedGrpc(store)
        .thenCompose(
          (ignored) ->
          {
            try {
              return this.searchGrpc(
                aci, aciIdentityKey, e164, unidentifiedAccessKey, usernameHash, store);
            } catch (InvalidProtocolBufferException | ExecutionException | InterruptedException e) {
              throw new RuntimeException(e);
            }
          });
    }

    KtQuery.SearchRequest request = KtQuery.SearchRequest.newBuilder()
      .setAci(ByteString.copyFrom(aci.toServiceIdBinary()))
      .setAciIdentityKey(ByteString.copyFrom(aciIdentityKey.serialize()))
//      .setUsernameHash(ByteString.copyFrom(usernameHash))
      .setConsistency(transparency.Transparency.Consistency.newBuilder().build())

      .build();
    ListenableFuture<KtQuery.SearchResponse> guavaFuture = stub.search(request);
    CompletableFuture<KtQuery.SearchResponse> future = new CompletableFuture<>();

    Futures.addCallback(guavaFuture, new FutureCallback<>() {
      @Override
      public void onSuccess(KtQuery.SearchResponse result) {
        future.complete(result);
      }

      @Override
      public void onFailure(Throwable t) {
        future.completeExceptionally(t);
      }
    }, MoreExecutors.directExecutor());

    return future.thenApply(searchResponse -> {
      try {
        verifySearchResponse(aciIdentityKey, searchResponse);

        store.setLastDistinguishedTreeHead(searchResponse.toByteArray());
        // Throwing everything into the store. Might contain unnecessary contents, but for now it must just work
        store.setAccountData(aci, searchResponse.toByteArray());
      } catch (Exception e) {
        throw new RuntimeException(e);
      }
      return null;
    });
  }

  private void verifySearchResponse(IdentityKey identityKey, KtQuery.SearchResponse searchResponse) {
    // fun Verify_Search(
    // aci_key: ByteArray?,
    // fullSearchResponseBytes: ByteArray?,
    // lthBytes: ByteArray?,
    // ldthBytes: ByteArray?,
    // mdBytes: ByteArray?,
    // forceMonitor: Boolean
    Store store;
    byte @NotNull [] result = Native.Verify_Search(identityKey.serialize(),
      searchResponse.toByteArray(),
      // LastTreeHead and LastDistinguishedTreeHead to be added
      null,
      // LDTH would come from the store
      null,
      null,
      false);
  }

  public CompletableFuture<KtQuery.DistinguishedResponse> updateDistinguishedGrpc(Store store) throws ExecutionException, InterruptedException, InvalidProtocolBufferException {
    KtQuery.DistinguishedRequest request;
    if (store.getLastDistinguishedTreeHead().isPresent()) {
      var lastSize = KtQuery.DistinguishedResponse.parseFrom(store.getLastDistinguishedTreeHead().get());

      request = KtQuery
        .DistinguishedRequest.newBuilder()
        .setLast(lastSize.getTreeHead().getTreeHead().getTreeSize())
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
        store.setLastDistinguishedTreeHead(distinguishedResponse.toByteArray());
      } catch (IOException e) {
        throw new RuntimeException(e);
      }
      return distinguishedResponse;
    });
  }

  public void verifyDistinguishedResponse(KtQuery.DistinguishedResponse distinguishedResponse, Store store) throws IOException {
    // all the needed checks (Equality, Consistency Proofs, ...) happen in Rust
    if (store.getLastDistinguishedTreeHead().isEmpty()) {
      Native.Verify_Distinguished(
        distinguishedResponse.getTreeHead().toByteArray(),
        null,
        0);
    } else {
      KtQuery.DistinguishedResponse trustedDthRes = KtQuery.DistinguishedResponse.parseFrom(store.getLastDistinguishedTreeHead().get());
      // TODO Check if the provided values are correct (Cross-check with KTClient in Go)
      Native.Verify_Distinguished(
        distinguishedResponse.getTreeHead().toByteArray(),
        trustedDthRes.getTreeHead().toByteArray(),
        trustedDthRes.getTreeHead().getTreeHead().getTreeSize());
    }
  }

  public CompletableFuture<Void> monitorGrpc(
    /* @NotNull */ final MonitorMode mode,
                   final ServiceId.Aci aci,
    /* @NotNull */ final IdentityKey aciIdentityKey,
                   final String e164,
                   final byte[] unidentifiedAccessKey,
                   final byte[] usernameHash,
                   final Store store) throws IOException, ExecutionException, InterruptedException {
    if (store.getLastDistinguishedTreeHead().isEmpty()) {
      return this.updateDistinguishedGrpc(store)
        .thenCompose(ignored -> {
          try {
            return this.monitorGrpc(mode, aci, aciIdentityKey, e164, unidentifiedAccessKey, usernameHash, store);
          } catch (ExecutionException | InterruptedException | IOException e) {
            throw new RuntimeException(e);
          }
        });
    }

    if (store.getAccountData(aci).isEmpty()) {
      return this.searchGrpc(aci, aciIdentityKey, e164, unidentifiedAccessKey, usernameHash, store).thenCompose(ignored -> {
        try {
          return this.monitorGrpc(mode, aci, aciIdentityKey, e164, unidentifiedAccessKey, usernameHash, store);
        } catch (ExecutionException | InterruptedException | IOException e) {
          throw new RuntimeException(e);
        }
      });
    }

    KtQuery.SearchResponse searchResponse = KtQuery.SearchResponse.parseFrom(store.getAccountData(aci).get());
    ByteString vrfProof = searchResponse.getAci().getVrfProof();

    // For the commitment index, I need the VRF public key
    // But how do I get the VRF public key? --> this happens in Rust...
//    ByteString commitmentIndex = ByteString.copyFrom(Hex.fromStringCondensedAssert("577a5742301f34c4551327a6c992c360328c7e877872f2c5f2a244524a0d0116"));
    ByteString commitmentIndex = ByteString.copyFrom(verifyAndGetIndex(aci, vrfProof));
    long entryPosition = searchResponse.getAci().getSearch().getPos();

    KtQuery.AciMonitorRequest aciMonitorRequest = KtQuery.AciMonitorRequest.newBuilder()
      .setAci(ByteString.copyFrom(aci.toServiceIdBinary()))
      .setEntryPosition(entryPosition)
      .setCommitmentIndex(commitmentIndex)
      .build();

    KtQuery.MonitorRequest request = KtQuery.MonitorRequest.newBuilder()
      .setAci(aciMonitorRequest)
//      .setUsernameHash(KtQuery.UsernameHashMonitorRequest.parseFrom(usernameHash))
//      .setE164(kt_query.KtQuery.E164MonitorRequest.newBuilder().setE164(e164))
      .setConsistency(Transparency.Consistency.newBuilder().build())
      .build();

    ListenableFuture<KtQuery.MonitorResponse> guavaFuture = stub.monitor(request);
    CompletableFuture<KtQuery.MonitorResponse> future = new CompletableFuture<>();

    Futures.addCallback(guavaFuture, new FutureCallback<>() {
      @Override public void onSuccess(KtQuery.MonitorResponse result) { future.complete(result); }
      @Override public void onFailure(Throwable t) { future.completeExceptionally(t); }
    }, MoreExecutors.directExecutor());

    return future.thenApply(response -> {
      // TODO check if providing the request object in this case is risky in terms of JNI bridging
      try {
        verifyMonitorResponse(request, response);
        return null;
      } catch (InvalidProtocolBufferException e) {
        throw new RuntimeException(e);
      }
    });
  }

  public void verifyMonitorResponse(KtQuery.MonitorRequest request, KtQuery.MonitorResponse response) throws InvalidProtocolBufferException {
    // kt_query <-> wire diff
    // aci, (optional) username_hash, (optional) e164 <-> all part of repeated MonitorKey keys
    // consistency (4) <-> consistency (2)
    Wire.MonitorRequest newReq = Wire.MonitorRequest.newBuilder()
      .addKeys(Wire.MonitorKey.parseFrom(request.getAci().toByteArray()))
      .setConsistency(Wire.Consistency.parseFrom(request.getConsistency().toByteArray()))
      .build();

    // kt_query <-> wire diff
    // aci <-> not present as own field (but as form of proofs)
    // username_hash & e164 <-> not present as own field (but as form of proofs)
    // inclusion <-> same type, different ID (5 <-> 4)
    Wire.MonitorResponse newRes = Wire.MonitorResponse.newBuilder()
      .setTreeHead(Wire.FullTreeHead.parseFrom(response.getTreeHead().toByteString()))
      .addProofs(Wire.MonitorProof.parseFrom(response.getAci().toByteArray()))
      .addAllInclusion(response.getInclusionList())
      .build();

    // TODO Find appropriate values
    Native.Verify_Monitor(
      newReq.toByteArray(),
      newRes.toByteArray(),
      null,
      null,
      null,
      System.currentTimeMillis()
    );
  }
  public static byte[] verifyAndGetIndex(ServiceId.Aci aci, ByteString vrfProof) {
    return Native.Verify_And_Get_Commitment_Index(aci.toServiceIdBinary(), vrfProof.toByteArray());
  }

  /**
   * Needed to insert new values
   * @return
   */
  public CompletableFuture<Transparency.UpdateResponse> updateGrpc(ServiceId.Aci aci, byte[] identityKey, Store store) {
    ByteString updateKey = ByteString.copyFrom("a", StandardCharsets.UTF_8).concat(ByteString.copyFrom(aci.toServiceIdBinary()));

    Transparency.UpdateRequest request = Transparency.UpdateRequest.newBuilder()
      .setSearchKey(updateKey)
//      .setValue("")
      .setConsistency(Transparency.Consistency.newBuilder().build())
      .build();

//    ListenableFuture<Transparency.UpdateResponse> guavaFuture = stub.(request);
    CompletableFuture<Transparency.UpdateResponse> future = new CompletableFuture<>();
//
//    Futures.addCallback(guavaFuture, new FutureCallback<>() {
//      @Override
//      public void onSuccess(Transparency.UpdateResponse result) {
//        future.complete(result);
//      }
//
//      @Override
//      public void onFailure(Throwable t) {
//        future.completeExceptionally(t);
//      }
//    }, MoreExecutors.directExecutor());

    return future;
  }

}
