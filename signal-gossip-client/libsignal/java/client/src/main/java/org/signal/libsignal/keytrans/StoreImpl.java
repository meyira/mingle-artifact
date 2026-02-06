package org.signal.libsignal.keytrans;

import com.google.protobuf.InvalidProtocolBufferException;
import kt_query.KtQuery;
import org.signal.libsignal.protocol.ServiceId;

import java.util.HashMap;
import java.util.Optional;

public class StoreImpl implements Store {

  private byte[] lastDistinguishedTreeHead;
  private HashMap<ServiceId.Aci, byte[]> accountData;

  public StoreImpl() {
    lastDistinguishedTreeHead = null;
    accountData = new HashMap<>();
  }

  @Override
  public Optional<byte[]> getLastDistinguishedTreeHead() {
    return Optional.ofNullable(lastDistinguishedTreeHead);
  }

  @Override
  public void setLastDistinguishedTreeHead(byte[] lastDistinguishedTreeHead) {
    if (lastDistinguishedTreeHead == null) {
      this.lastDistinguishedTreeHead = null;
      return;
    }

    try {
      KtQuery.DistinguishedResponse.parseFrom(lastDistinguishedTreeHead);
    } catch (InvalidProtocolBufferException e) {
      throw new RuntimeException(e);
    }
    this.lastDistinguishedTreeHead = lastDistinguishedTreeHead.clone();
  }

  @Override
  public Optional<byte[]> getAccountData(ServiceId.Aci aci) {
    return Optional.ofNullable(accountData.get(aci));
  }

  @Override
  public void setAccountData(ServiceId.Aci aci, byte[] data) {
    // Safeguard
    try {
      KtQuery.SearchResponse.parseFrom(data);
    } catch (InvalidProtocolBufferException e) {
      throw new RuntimeException(e);
    }

    accountData.put(aci, data);
  }
}
